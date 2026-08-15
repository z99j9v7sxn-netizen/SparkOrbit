"""求职助手投递看板 CRUD。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_interview import InterviewApplication

ALLOWED_STATUS = {"wishlist", "applied", "oa", "interview", "offer", "rejected"}


def serialize_application(row: InterviewApplication) -> dict[str, Any]:
    return {
        "id": row.id,
        "company": row.company,
        "role": row.role,
        "portal_url": row.portal_url,
        "status": row.status,
        "notes": row.notes,
        "applied_at": row.applied_at.isoformat() if row.applied_at else "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


async def list_applications(db: AsyncSession, user_id: str) -> list[InterviewApplication]:
    stmt = (
        select(InterviewApplication)
        .where(InterviewApplication.user_id == user_id)
        .order_by(InterviewApplication.updated_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_application(db: AsyncSession, user_id: str, payload: dict[str, Any]) -> InterviewApplication:
    status = str(payload.get("status") or "wishlist")
    if status not in ALLOWED_STATUS:
        status = "wishlist"
    row = InterviewApplication(
        user_id=user_id,
        company=str(payload.get("company") or "").strip()[:128],
        role=str(payload.get("role") or "").strip()[:128],
        portal_url=str(payload.get("portal_url") or "").strip()[:1024],
        status=status,
        notes=str(payload.get("notes") or "").strip()[:2000],
        applied_at=datetime.now(timezone.utc) if status == "applied" else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_application(
    db: AsyncSession, user_id: str, app_id: str, payload: dict[str, Any]
) -> InterviewApplication | None:
    row = await db.get(InterviewApplication, app_id)
    if row is None or row.user_id != user_id:
        return None
    if "company" in payload:
        row.company = str(payload.get("company") or "").strip()[:128]
    if "role" in payload:
        row.role = str(payload.get("role") or "").strip()[:128]
    if "portal_url" in payload:
        row.portal_url = str(payload.get("portal_url") or "").strip()[:1024]
    if "notes" in payload:
        row.notes = str(payload.get("notes") or "").strip()[:2000]
    if "status" in payload:
        status = str(payload.get("status") or "")
        if status in ALLOWED_STATUS:
            row.status = status
            if status == "applied" and row.applied_at is None:
                row.applied_at = datetime.now(timezone.utc)
    row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_application(db: AsyncSession, user_id: str, app_id: str) -> bool:
    row = await db.get(InterviewApplication, app_id)
    if row is None or row.user_id != user_id:
        return False
    await db.delete(row)
    await db.commit()
    return True
