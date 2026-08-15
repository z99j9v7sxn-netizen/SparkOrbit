"""陨石危机与超新星：艾宾浩斯遗忘曲线驱动的行星衰减与复习固化。"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.mastery import PlanetMastery
from app.models.user import User
from app.models.zone_extras import DailyTaskRecord

# 默认衰减阶段（天）：lit -> fading -> meteor -> dim
DECAY_STAGES = [
    (3, "fading"),
    (7, "meteor"),
    (14, "dim"),
]

REVIEW_STATES = frozenset({"fading", "meteor", "dim"})


def _stages_from_days(decay_days: dict[str, Any] | None) -> list[tuple[int, str]]:
    if not isinstance(decay_days, dict) or not decay_days:
        return list(DECAY_STAGES)
    fading = int(decay_days.get("fading", 3))
    meteor = int(decay_days.get("meteor", 7))
    dim = int(decay_days.get("dim", 14))
    # 保证单调递增
    meteor = max(meteor, fading + 1)
    dim = max(dim, meteor + 1)
    return [(fading, "fading"), (meteor, "meteor"), (dim, "dim")]


def compute_decay_state(mastery: PlanetMastery, decay_days: dict[str, Any] | None = None) -> str:
    """根据 last_reviewed_at / lit_at 计算衰减状态。"""
    if mastery.is_permanent or mastery.status != "lit":
        return mastery.decay_state or mastery.status

    ref = mastery.last_reviewed_at or mastery.lit_at
    if ref is None:
        return "lit"

    days = (datetime.utcnow() - ref.replace(tzinfo=None)).days
    state = "lit"
    for threshold, label in _stages_from_days(decay_days):
        if days >= threshold:
            state = label
    return state


async def apply_decay_to_user(session: AsyncSession, user_id: str) -> int:
    """刷新用户所有已点亮行星的衰减状态，返回受影响数量。"""
    decay_days = None
    try:
        from app.models.user import User as UserModel
        from app.services.gate_policy import get_thresholds_for_user

        user = (await session.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
        if user is not None:
            thr = await get_thresholds_for_user(session, user, "")
            decay_days = thr.get("decay_days")
    except Exception:  # noqa: BLE001
        decay_days = None

    rows = (
        await session.execute(
            select(PlanetMastery).where(
                PlanetMastery.user_id == user_id, PlanetMastery.status == "lit"
            )
        )
    ).scalars().all()
    count = 0
    for m in rows:
        new_state = compute_decay_state(m, decay_days)
        if m.decay_state != new_state:
            m.decay_state = new_state
            if new_state == "dim" and not m.is_permanent:
                m.status = "dim"
            session.add(m)
            count += 1
    if count:
        await session.commit()
    return count


async def review_planet(
    session: AsyncSession, user: User, planet_id: str, correct: bool
) -> Optional[dict]:
    """复习成功触发超新星爆发，固化为永久恒星。"""
    mastery = (
        await session.execute(
            select(PlanetMastery).where(
                PlanetMastery.user_id == user.id, PlanetMastery.planet_id == planet_id
            )
        )
    ).scalar_one_or_none()
    if mastery is None:
        return None

    if mastery.is_permanent:
        return {
            "success": True,
            "supernova": True,
            "is_permanent": True,
            "points": user.points,
            "message": "该行星已是永久恒星。",
        }

    decay = (mastery.decay_state or "").lower()
    status = (mastery.status or "").lower()
    if status not in ("lit", "dim", "fading", "meteor") and decay not in ("fading", "meteor", "dim"):
        return None

    mastery.attempts += 1
    if correct:
        mastery.correct_count += 1
        mastery.last_reviewed_at = datetime.utcnow()
        mastery.decay_state = "lit"
        mastery.status = "lit"
        mastery.is_permanent = True
        mastery.score = min(100, mastery.score + 10)
        user.points += 15
        user.mood = "celebrate"
        session.add(user)
        session.add(mastery)
        await session.commit()
        return {
            "success": True,
            "supernova": True,
            "is_permanent": True,
            "points": user.points,
            "message": "超新星爆发！该行星已固化为永久恒星。",
        }

    mastery.decay_state = "meteor"
    user.mood = "confused"
    session.add(user)
    session.add(mastery)
    await session.commit()
    return {"success": False, "supernova": False, "message": "复习未通过，陨石危机仍在持续。"}


def _day_start_utc() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


async def list_review_candidates(
    session: AsyncSession,
    user_id: str,
    *,
    refresh_decay: bool = True,
) -> list[dict[str, Any]]:
    """列出需要复习固化的行星（fading/meteor/dim）。"""
    if refresh_decay:
        await apply_decay_to_user(session, user_id)

    rows = (
        await session.execute(
            select(PlanetMastery, Planet)
            .join(Planet, Planet.id == PlanetMastery.planet_id)
            .where(PlanetMastery.user_id == user_id)
        )
    ).all()
    out: list[dict[str, Any]] = []
    for mastery, planet in rows:
        decay = (mastery.decay_state or "").lower()
        status = (mastery.status or "").lower()
        if mastery.is_permanent:
            continue
        if decay not in REVIEW_STATES and status not in REVIEW_STATES:
            continue
        state = decay if decay in REVIEW_STATES else status
        out.append(
            {
                "planet_id": planet.id,
                "planet_slug": planet.slug,
                "planet_name": planet.name,
                "decay_state": state,
                "score": float(mastery.score or 0),
            }
        )
    out.sort(key=lambda x: {"dim": 0, "meteor": 1, "fading": 2}.get(x["decay_state"], 9))
    return out


async def ensure_review_daily_tasks(
    session: AsyncSession,
    user: User,
    *,
    candidates: list[dict[str, Any]] | None = None,
    max_tasks: int = 3,
    commit: bool = True,
) -> list[dict[str, Any]]:
    """为衰减行星写入当日「复习固化」DailyTask（去重）。"""
    cands = candidates if candidates is not None else await list_review_candidates(session, user.id)
    if not cands:
        return []

    day_start = _day_start_utc()
    existing = (
        await session.execute(
            select(DailyTaskRecord).where(
                DailyTaskRecord.user_id == user.id,
                DailyTaskRecord.task_type == "review",
                DailyTaskRecord.created_at >= day_start,
            )
        )
    ).scalars().all()
    existing_titles = {r.title for r in existing}

    created: list[dict[str, Any]] = []
    for item in cands[: max(1, max_tasks)]:
        title = f"复习固化「{item['planet_name']}」（{item['decay_state']}）"
        if title in existing_titles:
            continue
        row = DailyTaskRecord(
            user_id=user.id,
            title=title,
            task_type="review",
            points=12 if item["decay_state"] in ("meteor", "dim") else 10,
            done=False,
        )
        session.add(row)
        await session.flush()
        created.append(
            {
                "id": row.id,
                "title": row.title,
                "task_type": row.task_type,
                "done": row.done,
                "points": row.points,
                "planet_slug": item["planet_slug"],
                "decay_state": item["decay_state"],
            }
        )
        existing_titles.add(title)

    if commit and created:
        await session.commit()
    return created


async def scan_and_dispatch_reviews(
    session: AsyncSession,
    teacher: User,
    class_id: str,
) -> dict[str, Any]:
    """教师触发：刷新班级衰减并为需复习学生派发任务 + 通知。"""
    from app.services.notification_service import create_notification
    from app.services.teacher import _students

    cid = (class_id or "").strip()
    if not cid:
        raise ValueError("缺少 class_id")

    students = await _students(session, teacher, cid)
    students_touched = 0
    tasks_created = 0
    planets_flagged = 0
    details: list[dict[str, Any]] = []

    for student in students:
        cands = await list_review_candidates(session, student.id, refresh_decay=True)
        if not cands:
            continue
        planets_flagged += len(cands)
        created = await ensure_review_daily_tasks(
            session, student, candidates=cands, max_tasks=3, commit=False
        )
        if not created:
            # 任务可能已存在，仍计入需复习
            students_touched += 1
            details.append(
                {
                    "user_id": student.id,
                    "display_name": student.display_name or student.username,
                    "review_planets": len(cands),
                    "tasks_created": 0,
                }
            )
            continue

        tasks_created += len(created)
        students_touched += 1
        names = "、".join(c["planet_name"] for c in cands[:3])
        await create_notification(
            session,
            user_id=student.id,
            title="复习任务已派发",
            body=f"教师已根据遗忘曲线为你安排复习：{names}。请到「每日任务」完成复习固化。",
            kind="review",
            link="/student?dock=tasks",
        )
        details.append(
            {
                "user_id": student.id,
                "display_name": student.display_name or student.username,
                "review_planets": len(cands),
                "tasks_created": len(created),
            }
        )

    await session.commit()
    return {
        "ok": True,
        "class_id": cid,
        "students_scanned": len(students),
        "students_needing_review": students_touched,
        "tasks_created": tasks_created,
        "planets_flagged": planets_flagged,
        "details": details[:50],
    }
