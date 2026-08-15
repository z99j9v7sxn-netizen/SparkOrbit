"""教师端：低置信判题工单列表与处理。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hallucination import HallucinationTicket
from app.models.user import User


async def list_pending_tickets(
    session: AsyncSession,
    teacher: User,
    *,
    class_id: str = "",
    limit: int = 50,
) -> list[dict]:
    stmt = (
        select(HallucinationTicket)
        .where(HallucinationTicket.status == "pending")
        .order_by(HallucinationTicket.created_at.desc())
        .limit(limit * 3)
    )
    rows = (await session.execute(stmt)).scalars().all()
    out: list[dict] = []
    for t in rows:
        student = (
            await session.execute(select(User).where(User.id == t.student_id))
        ).scalar_one_or_none()
        if student:
            if class_id and student.class_id and student.class_id != class_id:
                continue
            if student.teacher_id and student.teacher_id != teacher.id:
                continue
        out.append(
            {
                "id": t.id,
                "student_id": t.student_id,
                "student_name": (student.display_name or student.username) if student else t.student_id,
                "planet_slug": t.planet_slug,
                "planet_name": t.planet_name,
                "knowledge_point_id": t.knowledge_point_id,
                "cited_knowledge_point_id": t.cited_knowledge_point_id,
                "confidence": t.confidence,
                "reason": t.reason,
                "question_preview": t.question_preview,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else "",
            }
        )
        if len(out) >= limit:
            break
    return out


async def resolve_ticket(session: AsyncSession, teacher: User, ticket_id: str) -> dict | None:
    row = (
        await session.execute(select(HallucinationTicket).where(HallucinationTicket.id == ticket_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = "resolved"
    row.resolved = True
    if not row.teacher_id:
        row.teacher_id = teacher.id
    session.add(row)
    await session.commit()
    return {"ok": True, "id": row.id, "status": row.status}
