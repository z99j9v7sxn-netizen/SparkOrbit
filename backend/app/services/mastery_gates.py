"""多闸门掌握协议：学 → 练 → 讲 → 用 → 点亮。

练习通过不再直接 lit；需各闸门证据齐备后才点亮。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import PlanetMastery

# 阶段顺序
PHASE_DIM = "dim"
PHASE_EXPLORING = "exploring"
PHASE_PRACTICING = "practicing"
PHASE_EXPLAINING = "explaining"
PHASE_APPLYING = "applying"
PHASE_LIT = "lit"

GATE_LEARN = "learn"
GATE_PRACTICE = "practice"
GATE_EXPLAIN = "explain"
GATE_APPLY = "apply"

# 练闸：5 题答对 ≥4（80%）—— GatePolicy 缺失时回退
PRACTICE_QUESTIONS = 5
PRACTICE_MIN_CORRECT = 4
EXPLAIN_PASS_THRESHOLD = 0.7
LEARN_EVIDENCE_MIN = 1


def _flags(mastery: PlanetMastery) -> dict[str, Any]:
    raw = getattr(mastery, "gate_flags", None)
    if isinstance(raw, dict):
        return dict(raw)
    return {
        GATE_LEARN: False,
        GATE_PRACTICE: False,
        GATE_EXPLAIN: False,
        GATE_APPLY: False,
        "apply_required": True,
    }


def _policy_int(policy: dict[str, Any] | None, key: str, fallback: int) -> int:
    if not policy:
        return fallback
    try:
        return int(policy.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _policy_float(policy: dict[str, Any] | None, key: str, fallback: float) -> float:
    if not policy:
        return fallback
    try:
        return float(policy.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _policy_bool(policy: dict[str, Any] | None, key: str, fallback: bool) -> bool:
    if not policy or key not in policy:
        return fallback
    return bool(policy.get(key))


def _evidence(mastery: PlanetMastery) -> list:
    raw = getattr(mastery, "learn_evidence", None)
    return list(raw) if isinstance(raw, list) else []


def _phase(mastery: PlanetMastery) -> str:
    p = getattr(mastery, "mastery_phase", None) or mastery.status or PHASE_DIM
    if mastery.status == "lit" or mastery.is_permanent:
        return PHASE_LIT
    return str(p)


def next_gate_id(flags: dict[str, Any]) -> str | None:
    """返回下一道未通过的闸门 id；全部通过则 None。"""
    apply_required = bool(flags.get("apply_required", True))
    if not flags.get(GATE_LEARN):
        return GATE_LEARN
    if not flags.get(GATE_PRACTICE):
        return GATE_PRACTICE
    if not flags.get(GATE_EXPLAIN):
        return GATE_EXPLAIN
    if apply_required and not flags.get(GATE_APPLY):
        return GATE_APPLY
    return None


def gate_snapshot(mastery: PlanetMastery, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = _flags(mastery)
    apply_required = bool(flags.get("apply_required", True))
    nxt = next_gate_id(flags)
    pq = _policy_int(policy, "practice_questions", PRACTICE_QUESTIONS)
    pmc = _policy_int(policy, "practice_min_correct", PRACTICE_MIN_CORRECT)
    return {
        "mastery_phase": _phase(mastery),
        "status": mastery.status,
        "gates": {
            GATE_LEARN: bool(flags.get(GATE_LEARN)),
            GATE_PRACTICE: bool(flags.get(GATE_PRACTICE)),
            GATE_EXPLAIN: bool(flags.get(GATE_EXPLAIN)),
            GATE_APPLY: bool(flags.get(GATE_APPLY)) if apply_required else True,
        },
        "apply_required": apply_required,
        "learn_evidence_count": len(_evidence(mastery)),
        "practice_questions": pq,
        "practice_min_correct": pmc,
        "explain_pass_threshold": _policy_float(policy, "explain_pass_threshold", EXPLAIN_PASS_THRESHOLD),
        "learn_evidence_min": _policy_int(policy, "learn_evidence_min", LEARN_EVIDENCE_MIN),
        "can_challenge": bool(flags.get(GATE_LEARN)),
        "lit_ready": _all_gates_passed(flags),
        "next_gate": nxt,
        "lit": mastery.status == "lit" or bool(mastery.is_permanent),
    }


def _all_gates_passed(flags: dict[str, Any]) -> bool:
    apply_required = bool(flags.get("apply_required", True))
    if not flags.get(GATE_LEARN) or not flags.get(GATE_PRACTICE) or not flags.get(GATE_EXPLAIN):
        return False
    if apply_required and not flags.get(GATE_APPLY):
        return False
    return True


def _sync_phase(mastery: PlanetMastery, flags: dict[str, Any]) -> None:
    if mastery.status == "lit" or mastery.is_permanent:
        mastery.mastery_phase = PHASE_LIT
        return
    if not flags.get(GATE_LEARN):
        mastery.mastery_phase = PHASE_EXPLORING if _evidence(mastery) else PHASE_DIM
    elif not flags.get(GATE_PRACTICE):
        mastery.mastery_phase = PHASE_PRACTICING
    elif not flags.get(GATE_EXPLAIN):
        mastery.mastery_phase = PHASE_EXPLAINING
    elif bool(flags.get("apply_required", True)) and not flags.get(GATE_APPLY):
        mastery.mastery_phase = PHASE_APPLYING
    else:
        mastery.mastery_phase = PHASE_APPLYING


async def ensure_mastery(
    session: AsyncSession,
    user_id: str,
    planet_id: str,
    *,
    apply_required_default: bool | None = None,
) -> PlanetMastery:
    mastery = (
        await session.execute(
            select(PlanetMastery).where(PlanetMastery.user_id == user_id, PlanetMastery.planet_id == planet_id)
        )
    ).scalar_one_or_none()
    apply_default = True if apply_required_default is None else bool(apply_required_default)
    if mastery is None:
        mastery = PlanetMastery(
            user_id=user_id,
            planet_id=planet_id,
            status="dim",
            mastery_phase=PHASE_DIM,
            gate_flags={
                GATE_LEARN: False,
                GATE_PRACTICE: False,
                GATE_EXPLAIN: False,
                GATE_APPLY: False,
                "apply_required": apply_default,
            },
            learn_evidence=[],
        )
        session.add(mastery)
        await session.flush()
    # 兼容旧行
    if getattr(mastery, "gate_flags", None) is None:
        mastery.gate_flags = {
            GATE_LEARN: False,
            GATE_PRACTICE: False,
            GATE_EXPLAIN: False,
            GATE_APPLY: False,
            "apply_required": apply_default,
        }
    if getattr(mastery, "learn_evidence", None) is None:
        mastery.learn_evidence = []
    if not getattr(mastery, "mastery_phase", None):
        mastery.mastery_phase = PHASE_LIT if mastery.status == "lit" else PHASE_DIM
    return mastery


def set_apply_required(mastery: PlanetMastery, required: bool) -> None:
    flags = _flags(mastery)
    flags["apply_required"] = bool(required)
    mastery.gate_flags = flags
    _sync_phase(mastery, flags)


def record_learn_evidence(
    mastery: PlanetMastery,
    *,
    kind: str,
    ref_id: str = "",
    detail: str = "",
    auto_pass_learn: bool = True,
    policy: dict[str, Any] | None = None,
    evidence_min: int | None = None,
) -> dict[str, Any]:
    """记录学闸证据；默认达到 learn_evidence_min 条即过学闸。"""
    evidence = _evidence(mastery)
    entry = {
        "kind": kind,
        "ref_id": ref_id,
        "detail": detail[:240],
        "at": datetime.utcnow().isoformat() + "Z",
    }
    evidence.append(entry)
    mastery.learn_evidence = evidence[-40:]
    flags = _flags(mastery)
    min_needed = evidence_min if evidence_min is not None else _policy_int(policy, "learn_evidence_min", LEARN_EVIDENCE_MIN)
    if auto_pass_learn and len(evidence) >= min_needed:
        flags[GATE_LEARN] = True
    mastery.gate_flags = flags
    if mastery.status != "lit":
        _sync_phase(mastery, flags)
    return gate_snapshot(mastery, policy)


def pass_practice_gate(
    mastery: PlanetMastery,
    *,
    correct: int,
    total: int,
    min_correct: int | None = None,
    questions: int | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    flags = _flags(mastery)
    need_correct = min_correct if min_correct is not None else _policy_int(policy, "practice_min_correct", PRACTICE_MIN_CORRECT)
    need_total = questions if questions is not None else _policy_int(policy, "practice_questions", PRACTICE_QUESTIONS)
    if correct >= need_correct and total >= need_total:
        flags[GATE_PRACTICE] = True
    mastery.gate_flags = flags
    if mastery.status != "lit":
        _sync_phase(mastery, flags)
    return gate_snapshot(mastery, policy)


def pass_explain_gate(
    mastery: PlanetMastery,
    *,
    score: float = 1.0,
    pass_threshold: float | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    flags = _flags(mastery)
    threshold = (
        pass_threshold
        if pass_threshold is not None
        else _policy_float(policy, "explain_pass_threshold", EXPLAIN_PASS_THRESHOLD)
    )
    if score >= threshold:
        flags[GATE_EXPLAIN] = True
    mastery.gate_flags = flags
    if mastery.status != "lit":
        _sync_phase(mastery, flags)
    return gate_snapshot(mastery, policy)


def pass_apply_gate(mastery: PlanetMastery, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = _flags(mastery)
    flags[GATE_APPLY] = True
    mastery.gate_flags = flags
    if mastery.status != "lit":
        _sync_phase(mastery, flags)
    return gate_snapshot(mastery, policy)


def apply_credit(
    mastery: PlanetMastery,
    *,
    source: str = "viz_predict",
    detail: str = "",
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """演武预测等折抵用闸：非强制代码行星直接过用闸；强制代码行星只记证据。"""
    flags = _flags(mastery)
    apply_required = bool(flags.get("apply_required", True))
    snap_evidence = record_learn_evidence(
        mastery,
        kind="viz_predict",
        ref_id=source,
        detail=detail or f"apply_credit:{source}",
        auto_pass_learn=False,
    )
    if not apply_required:
        snap = pass_apply_gate(mastery, policy)
        return {
            **snap,
            "apply_credit": True,
            "apply_passed": True,
            "apply_required": False,
            "learn_evidence_count": snap_evidence.get("learn_evidence_count", snap.get("learn_evidence_count")),
        }
    # 强制代码用闸：只记 credit，引导 CodeLab
    return {
        **gate_snapshot(mastery, policy),
        "apply_credit": True,
        "apply_passed": bool(flags.get(GATE_APPLY)),
        "apply_required": True,
        "hint": "本行星需代码舱测例全绿通过用闸；预测答对已记入学闸证据。",
    }


def try_light_planet(mastery: PlanetMastery) -> bool:
    """四闸齐备则点亮；返回是否刚刚点亮。"""
    if mastery.status == "lit":
        return False
    flags = _flags(mastery)
    if not _all_gates_passed(flags):
        _sync_phase(mastery, flags)
        return False
    mastery.status = "lit"
    mastery.lit_at = datetime.utcnow()
    mastery.mastery_phase = PHASE_LIT
    mastery.decay_state = "lit"
    mastery.score = max(mastery.score, 80)
    return True


def bootstrap_from_assessment(mastery: PlanetMastery) -> None:
    """黑洞初测：只给探索起步，不直接 lit。"""
    if mastery.status == "lit":
        return
    flags = _flags(mastery)
    mastery.mastery_phase = PHASE_EXPLORING
    mastery.status = "dim"
    mastery.score = max(mastery.score, 40)
    mastery.gate_flags = flags
    record_learn_evidence(mastery, kind="assessment", detail="黑洞初测解锁探索", auto_pass_learn=False)
