"""统一今日复习队列：衰减行星 + 到期错题 + 复习卡（词汇/自定义）。

间隔重复采用固定梯度（1/3/7/14 天），三档反馈：
- remember 记得：进入下一档间隔
- fuzzy 模糊：保持当前档间隔
- forgot 忘了：回到第一档
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import ReviewCard
from app.models.user import User
from app.models.zone_extras import MistakeRecord
from app.services.memory_decay import list_review_candidates, review_planet

INTERVAL_DAYS = [1, 3, 7, 14]
RESULTS = ("remember", "fuzzy", "forgot")
POINTS = {"remember": 5, "fuzzy": 2, "forgot": 0}

MAX_MISTAKES = 20
MAX_CARDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_review_at(interval_index: int) -> datetime:
    days = INTERVAL_DAYS[min(max(interval_index, 0), len(INTERVAL_DAYS) - 1)]
    return _now() + timedelta(days=days)


def _advance(interval_index: int, result: str) -> int:
    if result == "remember":
        return min(interval_index + 1, len(INTERVAL_DAYS) - 1)
    if result == "forgot":
        return 0
    return interval_index


async def get_review_queue(session: AsyncSession, user: User) -> dict[str, Any]:
    """聚合三类到期复习项。"""
    now = _now()

    planets = await list_review_candidates(session, user.id, refresh_decay=True)

    mistakes = (
        (
            await session.execute(
                select(MistakeRecord)
                .where(
                    MistakeRecord.user_id == user.id,
                    or_(MistakeRecord.next_review_at.is_(None), MistakeRecord.next_review_at <= now),
                )
                .order_by(MistakeRecord.created_at.asc())
                .limit(MAX_MISTAKES)
            )
        )
        .scalars()
        .all()
    )

    cards = (
        (
            await session.execute(
                select(ReviewCard)
                .where(
                    ReviewCard.user_id == user.id,
                    or_(ReviewCard.next_review_at.is_(None), ReviewCard.next_review_at <= now),
                )
                .order_by(ReviewCard.created_at.asc())
                .limit(MAX_CARDS)
            )
        )
        .scalars()
        .all()
    )

    items: list[dict[str, Any]] = []
    for p in planets:
        items.append(
            {
                "item_type": "planet",
                "item_id": p["planet_id"],
                "front": f"复习固化「{p['planet_name']}」",
                "back": "",
                "meta": {
                    "planet_slug": p["planet_slug"],
                    "planet_name": p["planet_name"],
                    "decay_state": p["decay_state"],
                    "score": p["score"],
                },
            }
        )
    for m in mistakes:
        items.append(
            {
                "item_type": "mistake",
                "item_id": m.id,
                "front": m.question,
                "back": m.correct_answer or m.note or "（无参考答案，回忆解题思路后自评）",
                "meta": {
                    "subject": m.subject,
                    "student_answer": m.student_answer,
                    "review_count": m.review_count,
                },
            }
        )
    for c in cards:
        items.append(
            {
                "item_type": c.kind if c.kind in ("word", "card") else "card",
                "item_id": c.id,
                "front": c.front,
                "back": c.back,
                "meta": {"extra": c.extra, "review_count": c.review_count},
            }
        )

    return {
        "generated_at": now.isoformat(),
        "counts": {"planet": len(planets), "mistake": len(mistakes), "card": len(cards)},
        "items": items,
    }


async def submit_review(
    session: AsyncSession,
    user: User,
    item_type: str,
    item_id: str,
    result: str,
) -> dict[str, Any]:
    if result not in RESULTS:
        raise ValueError("result 必须是 remember / fuzzy / forgot")

    if item_type == "planet":
        outcome = await review_planet(session, user, item_id, correct=(result == "remember"))
        if outcome is None:
            raise LookupError("行星复习项不存在")
        return {"ok": True, "item_type": "planet", "points": user.points, **outcome}

    if item_type == "mistake":
        row = (
            await session.execute(
                select(MistakeRecord).where(MistakeRecord.id == item_id, MistakeRecord.user_id == user.id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError("错题不存在")
        row.interval_index = _advance(row.interval_index or 0, result)
        row.review_count = (row.review_count or 0) + 1
        row.last_result = result
        row.next_review_at = _next_review_at(row.interval_index)
        session.add(row)
    elif item_type in ("word", "card"):
        row = (
            await session.execute(
                select(ReviewCard).where(ReviewCard.id == item_id, ReviewCard.user_id == user.id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError("复习卡不存在")
        row.interval_index = _advance(row.interval_index or 0, result)
        row.review_count = (row.review_count or 0) + 1
        row.last_result = result
        row.next_review_at = _next_review_at(row.interval_index)
        session.add(row)
    else:
        raise ValueError(f"未知复习项类型：{item_type}")

    points = POINTS.get(result, 0)
    if points:
        user.points += points
        session.add(user)

    # 记入训练日志：供 21 天挑战 / 周报统计每日复习量
    try:
        from app.models.exam import ExamPracticeLog

        session.add(
            ExamPracticeLog(
                user_id=user.id,
                exam_type="",
                section="review",
                activity="review",
                total=1,
                correct=1 if result == "remember" else 0,
                meta_json={"item_type": item_type, "result": result},
            )
        )
    except Exception:  # noqa: BLE001
        pass

    await session.commit()
    return {
        "ok": True,
        "item_type": item_type,
        "result": result,
        "next_review_at": row.next_review_at.isoformat() if row.next_review_at else "",
        "points": user.points,
    }


async def add_review_card(
    session: AsyncSession,
    user_id: str,
    *,
    kind: str = "card",
    front: str,
    back: str = "",
    extra: str = "",
    source_id: str = "",
    commit: bool = True,
) -> ReviewCard:
    """新增复习卡；按 source_id（或 front）去重，重复时返回已有卡。"""
    conditions = [ReviewCard.user_id == user_id, ReviewCard.kind == kind]
    if source_id:
        conditions.append(ReviewCard.source_id == source_id)
    else:
        conditions.append(ReviewCard.front == front)
    existing = (await session.execute(select(ReviewCard).where(*conditions))).scalars().first()
    if existing is not None:
        return existing

    row = ReviewCard(
        user_id=user_id,
        kind=kind,
        source_id=source_id,
        front=front[:2000],
        back=back[:4000],
        extra=extra[:4000],
        next_review_at=None,  # 新卡立即到期
    )
    session.add(row)
    if commit:
        await session.commit()
        await session.refresh(row)
    else:
        await session.flush()
    return row


async def count_due(session: AsyncSession, user_id: str) -> int:
    """到期复习项总数（供日历/任务角标）。不刷新行星衰减，保持轻量。"""
    now = _now()
    from sqlalchemy import func as sa_func

    mistake_count = (
        await session.execute(
            select(sa_func.count(MistakeRecord.id)).where(
                MistakeRecord.user_id == user_id,
                or_(MistakeRecord.next_review_at.is_(None), MistakeRecord.next_review_at <= now),
            )
        )
    ).scalar_one()
    card_count = (
        await session.execute(
            select(sa_func.count(ReviewCard.id)).where(
                ReviewCard.user_id == user_id,
                or_(ReviewCard.next_review_at.is_(None), ReviewCard.next_review_at <= now),
            )
        )
    ).scalar_one()
    planets = await list_review_candidates(session, user_id, refresh_decay=False)
    return int(mistake_count) + int(card_count) + len(planets)
