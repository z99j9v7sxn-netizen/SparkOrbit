"""预演结果 vs 真实作答对照。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.simulation_outcome import SimulationOutcomeLink
from app.models.user import User


async def write_prediction(
    session: AsyncSession,
    *,
    user_id: str,
    planet_slug: str,
    sim_run_id: str,
    predicted_fail: bool,
    weaknesses: list[str] | None = None,
    root_cause: str = "",
    topic: str = "",
) -> Optional[dict[str, Any]]:
    """预演结束写入 open 预测行（real_correct=None）。"""
    uid = (user_id or "").strip()
    slug = (planet_slug or "").strip()
    if not uid:
        return None

    planet = None
    if slug:
        planet = (
            await session.execute(select(Planet).where(Planet.slug == slug))
        ).scalar_one_or_none()
    if planet is None and topic:
        planet = (
            await session.execute(select(Planet).where(Planet.name == topic))
        ).scalar_one_or_none()
        if planet is None:
            # 模糊：topic 包含行星名
            planets = (await session.execute(select(Planet))).scalars().all()
            for p in planets:
                if p.name and p.name in topic:
                    planet = p
                    break
    if planet is None:
        return None

    items = [str(x) for x in (weaknesses or []) if str(x).strip()][:12]
    if root_cause and root_cause not in items:
        items.insert(0, root_cause[:240])
    if not items:
        items = [f"镜像预演主题：{topic or planet.name}"]

    # 同一预演 run 不重复插入
    existing = (
        await session.execute(
            select(SimulationOutcomeLink).where(
                SimulationOutcomeLink.sim_run_id == sim_run_id,
                SimulationOutcomeLink.user_id == uid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.real_correct is None:
            existing.planet_id = planet.id
            existing.planet_slug = planet.slug
            existing.predicted_weaknesses = {
                "predicted_fail": bool(predicted_fail),
                "items": items,
                "root_cause": root_cause,
                "topic": topic,
            }
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return _row_out(existing)
        return _row_out(existing)

    # 关闭同行星更早的未回填预测，避免串单
    stale = (
        await session.execute(
            select(SimulationOutcomeLink).where(
                SimulationOutcomeLink.user_id == uid,
                SimulationOutcomeLink.planet_slug == planet.slug,
                SimulationOutcomeLink.real_correct.is_(None),
            )
        )
    ).scalars().all()
    for row in stale:
        row.real_correct = False
        row.agreement_score = 0.0
        row.predicted_weaknesses = {
            **(row.predicted_weaknesses or {}),
            "superseded": True,
        }
        session.add(row)

    row = SimulationOutcomeLink(
        user_id=uid,
        planet_id=planet.id,
        planet_slug=planet.slug,
        sim_run_id=sim_run_id or "",
        predicted_weaknesses={
            "predicted_fail": bool(predicted_fail),
            "items": items,
            "root_cause": root_cause,
            "topic": topic,
        },
        real_correct=None,
        agreement_score=0.0,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_out(row)


def _row_out(row: SimulationOutcomeLink) -> dict[str, Any]:
    return {
        "id": row.id,
        "planet_slug": row.planet_slug,
        "sim_run_id": row.sim_run_id,
        "real_correct": row.real_correct,
        "agreement_score": row.agreement_score,
        "predicted_weaknesses": row.predicted_weaknesses or {},
    }


async def record_or_update_outcome(
    session: AsyncSession,
    *,
    user_id: str,
    planet_slug: str,
    challenge_id: str,
    real_correct: bool,
) -> Optional[dict[str, Any]]:
    """挑战提交后：仅回填已有 open 预测行；无预测则返回 None。"""
    planet = (
        await session.execute(select(Planet).where(Planet.slug == planet_slug))
    ).scalar_one_or_none()
    if planet is None:
        return None

    open_row = (
        await session.execute(
            select(SimulationOutcomeLink)
            .where(
                SimulationOutcomeLink.user_id == user_id,
                SimulationOutcomeLink.planet_slug == planet_slug,
                SimulationOutcomeLink.real_correct.is_(None),
            )
            .order_by(SimulationOutcomeLink.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if open_row is None:
        return None

    pred = open_row.predicted_weaknesses if isinstance(open_row.predicted_weaknesses, dict) else {}
    predicted_fail = bool(pred.get("predicted_fail", True))
    agreement = 1.0 if (predicted_fail == (not real_correct)) else 0.0

    open_row.real_challenge_id = challenge_id
    open_row.real_correct = bool(real_correct)
    open_row.agreement_score = float(agreement)
    session.add(open_row)
    await session.commit()
    await session.refresh(open_row)
    return _row_out(open_row)


async def list_calibration(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    stmt = (
        select(SimulationOutcomeLink)
        .where(SimulationOutcomeLink.user_id == user_id)
        .order_by(SimulationOutcomeLink.created_at.desc())
        .limit(limit)
    )
    if planet_slug:
        stmt = stmt.where(SimulationOutcomeLink.planet_slug == planet_slug)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            **_row_out(r),
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def teacher_calibration_summary(
    session: AsyncSession,
    teacher: User,
    class_id: str = "",
) -> dict[str, Any]:
    from app.services.teacher import _students

    students = await _students(session, teacher, class_id)
    ids = [s.id for s in students]
    if not ids:
        return {"class_id": class_id, "samples": 0, "avg_agreement": 0.0, "by_student": []}

    rows = (
        await session.execute(
            select(SimulationOutcomeLink).where(
                SimulationOutcomeLink.user_id.in_(ids),
                SimulationOutcomeLink.real_correct.is_not(None),
            )
        )
    ).scalars().all()
    if not rows:
        return {"class_id": class_id, "samples": 0, "avg_agreement": 0.0, "by_student": []}

    avg = sum(float(r.agreement_score or 0) for r in rows) / len(rows)
    by: dict[str, list[float]] = {}
    for r in rows:
        by.setdefault(r.user_id, []).append(float(r.agreement_score or 0))
    name_map = {s.id: (s.display_name or s.username) for s in students}
    return {
        "class_id": class_id,
        "samples": len(rows),
        "avg_agreement": round(avg, 3),
        "by_student": [
            {
                "user_id": uid,
                "display_name": name_map.get(uid, uid),
                "samples": len(scores),
                "avg_agreement": round(sum(scores) / len(scores), 3),
            }
            for uid, scores in by.items()
        ],
    }
