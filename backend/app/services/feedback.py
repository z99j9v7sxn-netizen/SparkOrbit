"""用户反馈工单：学生/教师提交，管理员处理并回复（回复经站内通知送达）。"""
from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops import Feedback
from app.models.user import User

VALID_CATEGORY = {"bug", "suggestion", "content"}
VALID_STATUS = {"open", "processing", "closed"}

CATEGORY_LABEL = {"bug": "问题反馈", "suggestion": "功能建议", "content": "内容纠错"}


def _out(row: Feedback) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": row.user_name,
        "role": row.role,
        "category": row.category,
        "content": row.content,
        "status": row.status,
        "reply": row.reply,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


async def create_feedback(session: AsyncSession, user: User, *, category: str, content: str) -> dict:
    row = Feedback(
        user_id=user.id,
        user_name=user.display_name or user.username,
        role=user.role,
        category=category if category in VALID_CATEGORY else "suggestion",
        content=content.strip()[:4000],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _out(row)


async def list_my_feedback(session: AsyncSession, user_id: str, limit: int = 20) -> list[dict]:
    rows = (
        await session.execute(
            select(Feedback).where(Feedback.user_id == user_id).order_by(desc(Feedback.created_at)).limit(limit)
        )
    ).scalars().all()
    return [_out(r) for r in rows]


async def list_feedback(
    session: AsyncSession, *, status: str = "", category: str = "", limit: int = 100
) -> dict:
    stmt = select(Feedback)
    if status:
        stmt = stmt.where(Feedback.status == status)
    if category:
        stmt = stmt.where(Feedback.category == category)
    rows = (
        await session.execute(stmt.order_by(desc(Feedback.created_at)).limit(min(limit, 300)))
    ).scalars().all()
    open_count = (
        await session.execute(select(func.count()).select_from(Feedback).where(Feedback.status == "open"))
    ).scalar() or 0
    return {"items": [_out(r) for r in rows], "open_count": int(open_count)}


async def update_feedback(
    session: AsyncSession, feedback_id: str, *, status: str | None = None, reply: str | None = None
) -> dict | None:
    row = (await session.execute(select(Feedback).where(Feedback.id == feedback_id))).scalar_one_or_none()
    if row is None:
        return None
    if status and status in VALID_STATUS:
        row.status = status
    replied = False
    if reply is not None and reply.strip():
        row.reply = reply.strip()[:4000]
        replied = True
    await session.commit()
    await session.refresh(row)

    if replied and row.user_id:
        from app.services.notification_service import create_notification

        label = CATEGORY_LABEL.get(row.category, "反馈")
        await create_notification(
            session,
            row.user_id,
            f"你的{label}已收到回复",
            row.reply,
            kind="feedback",
        )
    return _out(row)
