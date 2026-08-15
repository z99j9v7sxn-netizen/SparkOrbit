"""学习日历与学习周报：聚合任务 / 作业 / 专注 / 签到 / 复习 / 训练数据。"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment, AssignmentSubmission
from app.models.exam import ExamMockRun, ExamPracticeLog
from app.models.mastery import PlanetMastery
from app.models.user import User
from app.models.zone_extras import DailyTaskRecord, FocusSession, SignInRecord

logger = logging.getLogger(__name__)


def _month_bounds(month: str) -> tuple[datetime, datetime, int]:
    """解析 YYYY-MM，返回 (月初, 下月初, 天数)。"""
    try:
        year_s, mon_s = month.split("-")
        year, mon = int(year_s), int(mon_s)
        if not (1 <= mon <= 12):
            raise ValueError
    except Exception as exc:  # noqa: BLE001
        raise ValueError("month 参数格式应为 YYYY-MM") from exc
    days = monthrange(year, mon)[1]
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=days)
    return start, end, days


def _date_key(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.date().isoformat()


async def month_calendar(session: AsyncSession, user: User, month: str) -> dict[str, Any]:
    start, end, days_in_month = _month_bounds(month)

    day_map: dict[str, dict[str, Any]] = {}
    for i in range(days_in_month):
        d = (start + timedelta(days=i)).date().isoformat()
        day_map[d] = {
            "date": d,
            "tasks_total": 0,
            "tasks_done": 0,
            "focus_minutes": 0,
            "signed_in": False,
            "practice_items": 0,
            "assignments_due": [],
        }

    tasks = (
        (
            await session.execute(
                select(DailyTaskRecord).where(
                    DailyTaskRecord.user_id == user.id,
                    DailyTaskRecord.created_at >= start,
                    DailyTaskRecord.created_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    for t in tasks:
        key = _date_key(t.created_at)
        if key in day_map:
            day_map[key]["tasks_total"] += 1
            if t.done:
                day_map[key]["tasks_done"] += 1

    focus_rows = (
        (
            await session.execute(
                select(FocusSession).where(
                    FocusSession.user_id == user.id,
                    FocusSession.created_at >= start,
                    FocusSession.created_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    for f in focus_rows:
        key = _date_key(f.created_at)
        if key in day_map:
            day_map[key]["focus_minutes"] += int(f.minutes or 0)

    signins = (
        (
            await session.execute(
                select(SignInRecord).where(
                    SignInRecord.user_id == user.id,
                    SignInRecord.created_at >= start,
                    SignInRecord.created_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    for s in signins:
        key = _date_key(s.created_at)
        if key in day_map:
            day_map[key]["signed_in"] = True

    practice_rows = (
        await session.execute(
            select(
                sa_func.date(ExamPracticeLog.created_at),
                sa_func.coalesce(sa_func.sum(ExamPracticeLog.total), 0),
            )
            .where(
                ExamPracticeLog.user_id == user.id,
                ExamPracticeLog.created_at >= start,
                ExamPracticeLog.created_at < end,
            )
            .group_by(sa_func.date(ExamPracticeLog.created_at))
        )
    ).all()
    for day_value, total in practice_rows:
        key = str(day_value)
        if key in day_map:
            day_map[key]["practice_items"] = int(total)

    if user.class_id:
        assignments = (
            (
                await session.execute(
                    select(Assignment).where(
                        Assignment.class_id == user.class_id,
                        Assignment.due_at.isnot(None),
                        Assignment.due_at >= start,
                        Assignment.due_at < end,
                    )
                )
            )
            .scalars()
            .all()
        )
        submitted_ids = set(
            (
                await session.execute(
                    select(AssignmentSubmission.assignment_id).where(
                        AssignmentSubmission.student_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        for a in assignments:
            key = _date_key(a.due_at)
            if key in day_map:
                day_map[key]["assignments_due"].append(
                    {"id": a.id, "title": a.title, "submitted": a.id in submitted_ids}
                )

    # 今日复习到期数（轻量，不刷新衰减）
    review_due = 0
    try:
        from app.services.review_queue import count_due

        review_due = await count_due(session, user.id)
    except Exception:  # noqa: BLE001
        logger.exception("count_due failed")

    return {
        "month": month,
        "review_due_today": review_due,
        "days": list(day_map.values()),
    }


async def weekly_report(session: AsyncSession, user: User) -> dict[str, Any]:
    """近 7 天学习周报。"""
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today - timedelta(days=6), time.min, tzinfo=timezone.utc)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)

    focus_rows = (
        (
            await session.execute(
                select(FocusSession).where(
                    FocusSession.user_id == user.id,
                    FocusSession.created_at >= start,
                    FocusSession.created_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    focus_minutes = sum(int(f.minutes or 0) for f in focus_rows)
    daily_focus: dict[str, int] = {}
    for i in range(7):
        daily_focus[(today - timedelta(days=6 - i)).isoformat()] = 0
    for f in focus_rows:
        key = _date_key(f.created_at)
        if key in daily_focus:
            daily_focus[key] += int(f.minutes or 0)

    lit_rows = (
        (
            await session.execute(
                select(PlanetMastery).where(
                    PlanetMastery.user_id == user.id,
                    PlanetMastery.lit_at.isnot(None),
                    PlanetMastery.lit_at >= start.replace(tzinfo=None),
                )
            )
        )
        .scalars()
        .all()
    )
    planets_lit = len(lit_rows)
    planets_permanent = sum(1 for r in lit_rows if r.is_permanent)

    practice_rows = (
        (
            await session.execute(
                select(ExamPracticeLog).where(
                    ExamPracticeLog.user_id == user.id,
                    ExamPracticeLog.created_at >= start,
                    ExamPracticeLog.created_at < end,
                )
            )
        )
        .scalars()
        .all()
    )
    reviews = [r for r in practice_rows if r.activity == "review"]
    drills = [r for r in practice_rows if r.activity != "review"]
    reviews_done = sum(r.total for r in reviews)
    reviews_remembered = sum(r.correct for r in reviews)
    drill_total = sum(r.total for r in drills)
    drill_correct = sum(r.correct for r in drills)

    mock_rows = (
        (
            await session.execute(
                select(ExamMockRun).where(
                    ExamMockRun.user_id == user.id,
                    ExamMockRun.status == "done",
                    ExamMockRun.finished_at >= start,
                )
            )
        )
        .scalars()
        .all()
    )
    mock_best = max((r.score for r in mock_rows), default=0.0)

    signin_days = (
        await session.execute(
            select(sa_func.count(sa_func.distinct(sa_func.date(SignInRecord.created_at)))).where(
                SignInRecord.user_id == user.id,
                SignInRecord.created_at >= start,
                SignInRecord.created_at < end,
            )
        )
    ).scalar_one()

    report: dict[str, Any] = {
        "week_start": (today - timedelta(days=6)).isoformat(),
        "week_end": today.isoformat(),
        "focus_minutes": focus_minutes,
        "focus_sessions": len(focus_rows),
        "daily_focus": [{"date": d, "minutes": m} for d, m in daily_focus.items()],
        "planets_lit": planets_lit,
        "planets_permanent": planets_permanent,
        "reviews_done": reviews_done,
        "remember_rate": round(reviews_remembered / reviews_done * 100) if reviews_done else 0,
        "practice_total": drill_total,
        "practice_correct_rate": round(drill_correct / drill_total * 100) if drill_total else 0,
        "mock_count": len(mock_rows),
        "mock_best": mock_best,
        "sign_in_days": int(signin_days),
        "streak_days": user.streak_days or 0,
        "points": user.points or 0,
        "display_name": user.display_name or user.username,
    }

    # LLM 一句话总结（失败降级为规则文案）
    try:
        from app.services.llm import llm_chat

        summary = await llm_chat(
            [
                {
                    "role": "system",
                    "content": "你是学习教练。根据本周数据给学生一句 40 字以内的中文总结与鼓励，语气积极具体，不要罗列数字。",
                },
                {
                    "role": "user",
                    "content": (
                        f"专注 {focus_minutes} 分钟、点亮 {planets_lit} 颗行星、复习 {reviews_done} 项"
                        f"（记住率 {report['remember_rate']}%）、刷题 {drill_total} 道"
                        f"（正确率 {report['practice_correct_rate']}%）、签到 {signin_days} 天。"
                    ),
                },
            ],
            temperature=0.6,
            timeout=30.0,
        )
        report["summary"] = (summary or "").strip()[:80]
    except Exception:  # noqa: BLE001
        report["summary"] = ""
    if not report["summary"]:
        if focus_minutes or reviews_done or drill_total:
            report["summary"] = "这周的星轨在稳步延伸，保持节奏，下周继续点亮新的星球！"
        else:
            report["summary"] = "这周还没有学习记录，从一个 25 分钟番茄钟开始吧！"
    return report
