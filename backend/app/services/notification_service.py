import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import UserNotification


async def create_notification(
    session: AsyncSession,
    user_id: str,
    title: str,
    body: str,
    *,
    kind: str = "system",
    link: str = "",
) -> dict:
    row = UserNotification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        link=link,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _out(row)


def _out(row: UserNotification) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "link": row.link,
        "is_read": row.is_read,
        "created_at": row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat(),
    }


async def list_notifications(session: AsyncSession, user_id: str, limit: int = 40) -> list[dict]:
    rows = (
        await session.execute(
            select(UserNotification)
            .where(UserNotification.user_id == user_id)
            .order_by(UserNotification.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_out(r) for r in rows]


async def unread_count(session: AsyncSession, user_id: str) -> int:
    rows = (
        await session.execute(
            select(UserNotification).where(UserNotification.user_id == user_id, UserNotification.is_read.is_(False))
        )
    ).scalars().all()
    return len(rows)


async def mark_read(session: AsyncSession, user_id: str, notification_id: str) -> bool:
    row = (
        await session.execute(
            select(UserNotification).where(UserNotification.id == notification_id, UserNotification.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.is_read = True
    await session.commit()
    return True


async def mark_all_read(session: AsyncSession, user_id: str) -> None:
    rows = (
        await session.execute(select(UserNotification).where(UserNotification.user_id == user_id, UserNotification.is_read.is_(False)))
    ).scalars().all()
    for row in rows:
        row.is_read = True
    await session.commit()
