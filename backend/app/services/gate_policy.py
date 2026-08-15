"""班级通关门控策略：查询 / 写入 / 解析为阈值字典。"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gate_policy import DEFAULT_DECAY_DAYS, GatePolicy
from app.models.user import User
from app.services import mastery_gates as gates


def default_thresholds() -> dict[str, Any]:
    return {
        "practice_questions": gates.PRACTICE_QUESTIONS,
        "practice_min_correct": gates.PRACTICE_MIN_CORRECT,
        "explain_pass_threshold": gates.EXPLAIN_PASS_THRESHOLD,
        "apply_required_default": True,
        "learn_evidence_min": gates.LEARN_EVIDENCE_MIN,
        "decay_days": dict(DEFAULT_DECAY_DAYS),
    }


def thresholds_from_row(row: GatePolicy | None) -> dict[str, Any]:
    base = default_thresholds()
    if row is None:
        return base
    decay = row.decay_days if isinstance(row.decay_days, dict) and row.decay_days else dict(DEFAULT_DECAY_DAYS)
    return {
        "practice_questions": int(row.practice_questions or base["practice_questions"]),
        "practice_min_correct": int(row.practice_min_correct or base["practice_min_correct"]),
        "explain_pass_threshold": float(
            row.explain_pass_threshold if row.explain_pass_threshold is not None else base["explain_pass_threshold"]
        ),
        "apply_required_default": bool(row.apply_required_default),
        "learn_evidence_min": int(row.learn_evidence_min or base["learn_evidence_min"]),
        "decay_days": {
            "fading": int(decay.get("fading", DEFAULT_DECAY_DAYS["fading"])),
            "meteor": int(decay.get("meteor", DEFAULT_DECAY_DAYS["meteor"])),
            "dim": int(decay.get("dim", DEFAULT_DECAY_DAYS["dim"])),
        },
    }


def policy_to_dict(row: GatePolicy) -> dict[str, Any]:
    thr = thresholds_from_row(row)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "galaxy_slug": row.galaxy_slug or "",
        **thr,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


async def get_policy(
    session: AsyncSession,
    class_id: str,
    galaxy_slug: str = "",
    *,
    create_if_missing: bool = True,
) -> GatePolicy | None:
    """优先匹配 class_id + galaxy_slug；再回退 class_id + 空 slug；缺失时可创建默认行。"""
    class_id = (class_id or "").strip()
    galaxy_slug = (galaxy_slug or "").strip()
    if not class_id:
        return None
    if galaxy_slug:
        specific = (
            await session.execute(
                select(GatePolicy).where(
                    GatePolicy.class_id == class_id,
                    GatePolicy.galaxy_slug == galaxy_slug,
                )
            )
        ).scalar_one_or_none()
        if specific is not None:
            return specific
    row = (
        await session.execute(
            select(GatePolicy).where(
                GatePolicy.class_id == class_id,
                GatePolicy.galaxy_slug == "",
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    if create_if_missing:
        return await upsert_policy(session, class_id=class_id, galaxy_slug=galaxy_slug)
    return None


async def get_thresholds(
    session: AsyncSession,
    class_id: str,
    galaxy_slug: str = "",
) -> dict[str, Any]:
    row = await get_policy(session, class_id, galaxy_slug, create_if_missing=False)
    return thresholds_from_row(row)


async def get_thresholds_for_user(
    session: AsyncSession,
    user: User,
    galaxy_slug: str = "",
) -> dict[str, Any]:
    class_id = getattr(user, "class_id", "") or ""
    return await get_thresholds(session, class_id, galaxy_slug)


async def upsert_policy(
    session: AsyncSession,
    *,
    class_id: str,
    galaxy_slug: str = "",
    practice_questions: Optional[int] = None,
    practice_min_correct: Optional[int] = None,
    explain_pass_threshold: Optional[float] = None,
    apply_required_default: Optional[bool] = None,
    learn_evidence_min: Optional[int] = None,
    decay_days: Optional[dict] = None,
) -> GatePolicy:
    class_id = (class_id or "").strip()
    galaxy_slug = (galaxy_slug or "").strip()
    if not class_id:
        raise ValueError("class_id 不能为空")

    row = (
        await session.execute(
            select(GatePolicy).where(
                GatePolicy.class_id == class_id,
                GatePolicy.galaxy_slug == galaxy_slug,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        defaults = default_thresholds()
        row = GatePolicy(
            class_id=class_id,
            galaxy_slug=galaxy_slug,
            practice_questions=defaults["practice_questions"],
            practice_min_correct=defaults["practice_min_correct"],
            explain_pass_threshold=defaults["explain_pass_threshold"],
            apply_required_default=defaults["apply_required_default"],
            learn_evidence_min=defaults["learn_evidence_min"],
            decay_days=dict(defaults["decay_days"]),
        )
        session.add(row)

    if practice_questions is not None:
        row.practice_questions = max(1, int(practice_questions))
    if practice_min_correct is not None:
        row.practice_min_correct = max(1, int(practice_min_correct))
    if explain_pass_threshold is not None:
        row.explain_pass_threshold = max(0.0, min(1.0, float(explain_pass_threshold)))
    if apply_required_default is not None:
        row.apply_required_default = bool(apply_required_default)
    if learn_evidence_min is not None:
        row.learn_evidence_min = max(1, int(learn_evidence_min))
    if decay_days is not None and isinstance(decay_days, dict):
        base = dict(DEFAULT_DECAY_DAYS)
        for key in ("fading", "meteor", "dim"):
            if key in decay_days and decay_days[key] is not None:
                base[key] = max(1, int(decay_days[key]))
        row.decay_days = base

    if row.practice_min_correct > row.practice_questions:
        row.practice_min_correct = row.practice_questions

    await session.commit()
    await session.refresh(row)
    return row
