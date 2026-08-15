"""画像改进闭环：补救计划、三档评分、维度加减分与警告。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.remediation import ImprovementSubmission, RemediationPlan
from app.models.student_profile import DIMENSION_LABELS, PROFILE_DIMENSIONS, StudentProfile
from app.models.user import User
from app.schemas.student_profile import StudentProfileExtract
from app.services.llm import extract_json, llm_available, llm_chat
from app.services.profile_refresh import record_learning_event
from app.services.profiles import get_latest_profile, save_student_profile

logger = logging.getLogger(__name__)

GRADE_EXCELLENT = "excellent"
GRADE_PASS = "pass"
GRADE_FAIL = "fail"
VALID_GRADES = {GRADE_EXCELLENT, GRADE_PASS, GRADE_FAIL}

GRADE_DELTA = {
    GRADE_EXCELLENT: 10,
    GRADE_PASS: 5,
    GRADE_FAIL: 0,
}

WEEKLY_DELTA_CAP = 15
LABEL_TO_DIM = {v: k for k, v in DIMENSION_LABELS.items()}


def infer_target_dimension(topic: str, explicit: str | None = None) -> str:
    if explicit and explicit in PROFILE_DIMENSIONS:
        return explicit
    text = topic or ""
    for key, label in DIMENSION_LABELS.items():
        if key in text or label in text:
            return key
    # 常见薄弱维默认
    return "prior_knowledge"


def _profile_to_extract(row: StudentProfile) -> StudentProfileExtract:
    payload = {
        "student_name": row.student_name,
        "summary": row.summary,
        "missing_dimensions": row.missing_dimensions or [],
        "follow_up_questions": row.follow_up_questions or [],
    }
    for dim in PROFILE_DIMENSIONS:
        payload[dim] = getattr(row, dim) or {}
    return StudentProfileExtract.model_validate(payload)


def _plan_out(plan: RemediationPlan, submission: ImprovementSubmission | None = None) -> dict:
    steps = plan.steps_json if isinstance(plan.steps_json, list) else []
    out: dict[str, Any] = {
        "id": plan.id,
        "user_id": plan.user_id,
        "simulation_run_id": plan.simulation_run_id,
        "target_dimension": plan.target_dimension,
        "target_dimension_label": DIMENSION_LABELS.get(plan.target_dimension, plan.target_dimension),
        "topic": plan.topic,
        "root_cause": plan.root_cause,
        "steps": steps,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "submission": None,
    }
    if submission:
        out["submission"] = {
            "id": submission.id,
            "reflection": submission.reflection,
            "ai_grade": submission.ai_grade,
            "ai_feedback": submission.ai_feedback,
            "ai_delta_json": submission.ai_delta_json,
            "teacher_grade": submission.teacher_grade,
            "teacher_feedback": submission.teacher_feedback,
            "final_grade": submission.final_grade,
            "applied_delta": submission.applied_delta,
            "warning_text": submission.warning_text,
            "teacher_reviewed": submission.teacher_reviewed,
            "pending_review": not submission.teacher_reviewed,
            "created_at": submission.created_at.isoformat() if submission.created_at else None,
        }
    return out


async def create_remediation_plan(
    session: AsyncSession,
    *,
    user_id: str,
    simulation_run_id: str,
    topic: str,
    root_cause: str,
    steps: list[str],
    target_dimension: str | None = None,
) -> RemediationPlan:
    dim = infer_target_dimension(topic, target_dimension)
    step_rows = [
        {"index": i, "title": str(title), "done": False, "evidence_text": ""}
        for i, title in enumerate(steps)
    ]
    plan = RemediationPlan(
        id=str(uuid4()),
        user_id=user_id,
        simulation_run_id=simulation_run_id,
        target_dimension=dim,
        topic=topic,
        root_cause=root_cause or "",
        steps_json=step_rows,
        status="open",
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def list_user_plans(session: AsyncSession, user_id: str) -> list[dict]:
    plans = (
        await session.execute(
            select(RemediationPlan)
            .where(RemediationPlan.user_id == user_id)
            .order_by(desc(RemediationPlan.created_at))
            .limit(40)
        )
    ).scalars().all()
    out = []
    for plan in plans:
        sub = (
            await session.execute(
                select(ImprovementSubmission)
                .where(ImprovementSubmission.plan_id == plan.id)
                .order_by(desc(ImprovementSubmission.created_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(_plan_out(plan, sub))
    return out


async def update_plan_step(
    session: AsyncSession,
    *,
    user_id: str,
    plan_id: str,
    step_index: int,
    done: bool | None = None,
    evidence_text: str | None = None,
) -> dict:
    plan = await session.get(RemediationPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="补救计划不存在")
    if plan.status not in ("open", "submitted"):
        # allow editing evidence only while open; after graded locked except fail retry
        if plan.status == "graded":
            latest = (
                await session.execute(
                    select(ImprovementSubmission)
                    .where(ImprovementSubmission.plan_id == plan.id)
                    .order_by(desc(ImprovementSubmission.created_at))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest and latest.final_grade != GRADE_FAIL:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该计划已评分，不可修改步骤")
            plan.status = "open"
    steps = list(plan.steps_json or [])
    if step_index < 0 or step_index >= len(steps):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="步骤索引无效")
    step = dict(steps[step_index])
    if done is not None:
        step["done"] = bool(done)
    if evidence_text is not None:
        step["evidence_text"] = evidence_text.strip()
        if step["evidence_text"]:
            step["done"] = True
    steps[step_index] = step
    plan.steps_json = steps
    await session.commit()
    await session.refresh(plan)
    return _plan_out(plan)


async def _weekly_delta_sum(session: AsyncSession, user_id: str, dimension: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = (
        await session.execute(
            select(ImprovementSubmission).where(
                ImprovementSubmission.user_id == user_id,
                ImprovementSubmission.final_grade.in_([GRADE_EXCELLENT, GRADE_PASS]),
                ImprovementSubmission.created_at >= since,
            )
        )
    ).scalars().all()
    total = 0
    for row in rows:
        delta = row.ai_delta_json or {}
        if isinstance(delta, dict) and dimension in delta:
            try:
                total += int(delta[dimension])
            except (TypeError, ValueError):
                pass
        elif row.applied_delta and isinstance(delta, dict) and dimension in (delta or {}):
            total += int(row.applied_delta)
        else:
            # fallback: if submission applied to this dim via plan
            plan = await session.get(RemediationPlan, row.plan_id)
            if plan and plan.target_dimension == dimension:
                total += int(row.applied_delta or 0)
    return total


def _heuristic_grade(plan: RemediationPlan, reflection: str) -> tuple[str, str, int]:
    steps = plan.steps_json or []
    done_count = sum(1 for s in steps if isinstance(s, dict) and s.get("done"))
    evidence_ok = sum(
        1 for s in steps if isinstance(s, dict) and len(str(s.get("evidence_text") or "").strip()) >= 12
    )
    refl = (reflection or "").strip()
    cause_hit = bool(plan.root_cause) and any(
        token in refl for token in str(plan.root_cause)[:40].split() if len(token) >= 2
    )

    if done_count < len(steps) or evidence_ok < max(1, len(steps) - 1):
        return GRADE_FAIL, "步骤未完成或证据不足，未能回应错因。请补齐证据后重提。", 0
    if len(refl) < 20:
        return GRADE_FAIL, "反思过短，缺少对错因的针对性分析。", 0
    if evidence_ok == len(steps) and len(refl) >= 60 and (cause_hit or "区分" in refl or "对比" in refl):
        return GRADE_EXCELLENT, "证据完整且能回应激因，概念区分清晰。", GRADE_DELTA[GRADE_EXCELLENT]
    return GRADE_PASS, "步骤已完成，证据基本相关；建议加深与错因的对应分析。", GRADE_DELTA[GRADE_PASS]


async def _ai_grade_submission(plan: RemediationPlan, reflection: str) -> tuple[str, str, int]:
    if not llm_available():
        return _heuristic_grade(plan, reflection)

    steps_text = "\n".join(
        f"{i + 1}. done={s.get('done')} evidence={s.get('evidence_text', '')[:200]}"
        for i, s in enumerate(plan.steps_json or [])
        if isinstance(s, dict)
    )
    prompt = f"""你是画像改进评审官。根据固定 rubric 给三档评分，只返回 JSON。
目标维度：{plan.target_dimension}（{DIMENSION_LABELS.get(plan.target_dimension, '')}）
主题：{plan.topic}
错因：{plan.root_cause}
步骤与证据：
{steps_text}
学生反思：
{reflection}

rubric：
- excellent：步骤齐全；证据直接回应激因；能区分概念/权重 → delta 10
- pass：步骤完成；证据部分相关；反思浅但有行动 → delta 5
- fail：缺步/空话/与错因无关 → delta 0

返回：{{"grade":"excellent|pass|fail","feedback":"中文反馈","delta":10}}"""
    raw = await llm_chat(
        [
            {"role": "system", "content": "你只输出 JSON，严格遵守 rubric。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_json=True,
    )
    if not raw:
        return _heuristic_grade(plan, reflection)
    parsed = extract_json(raw)
    if not parsed:
        return _heuristic_grade(plan, reflection)
    grade = str(parsed.get("grade") or "").lower()
    if grade not in VALID_GRADES:
        return _heuristic_grade(plan, reflection)
    feedback = str(parsed.get("feedback") or "")
    try:
        delta = int(parsed.get("delta", GRADE_DELTA[grade]))
    except (TypeError, ValueError):
        delta = GRADE_DELTA[grade]
    delta = GRADE_DELTA[grade] if grade == GRADE_FAIL else max(GRADE_DELTA[grade] - 2, min(delta, GRADE_DELTA[grade] + 2))
    if grade == GRADE_EXCELLENT:
        delta = max(8, min(12, delta))
    elif grade == GRADE_PASS:
        delta = max(4, min(6, delta))
    else:
        delta = 0
    return grade, feedback or _heuristic_grade(plan, reflection)[1], delta


async def _apply_grade_to_profile(
    session: AsyncSession,
    *,
    user_id: str,
    plan: RemediationPlan,
    grade: str,
    delta: int,
    submission_id: str,
    warning_text: str,
) -> tuple[int, list]:
    """Apply score delta / warning; return (applied_delta, warnings)."""
    latest = await get_latest_profile(session, user_id=user_id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先完成首次画像采集")

    extract = _profile_to_extract(latest)
    floors = dict(latest.dimension_floors_json or {})
    warnings = list(latest.warnings_json or [])
    dim = plan.target_dimension
    if dim not in PROFILE_DIMENSIONS:
        dim = "prior_knowledge"

    applied = 0
    if grade in (GRADE_EXCELLENT, GRADE_PASS) and delta > 0:
        used = await _weekly_delta_sum(session, user_id, dim)
        room = max(0, WEEKLY_DELTA_CAP - used)
        applied = min(delta, room)
        dim_obj = getattr(extract, dim)
        new_score = min(100, int(dim_obj.score or 0) + applied)
        dim_obj.score = new_score
        evidence = list(dim_obj.evidence or [])
        evidence.append(f"改进验收 {grade} +{applied}（submission {submission_id[:8]}）")
        dim_obj.evidence = evidence[-12:]
        floors[dim] = max(int(floors.get(dim) or 0), new_score)
        # clear same-dimension warnings on success
        warnings = [w for w in warnings if not (isinstance(w, dict) and w.get("dimension") == dim)]
        extract.summary = (extract.summary or "") + f" [改进验收 {DIMENSION_LABELS.get(dim, dim)} +{applied}]"
    elif grade == GRADE_FAIL:
        warn = {
            "dimension": dim,
            "text": warning_text or "改进提交不合格，需针对错因重新完成证据。",
            "source_submission_id": submission_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        warnings = [w for w in warnings if not (isinstance(w, dict) and w.get("dimension") == dim)]
        warnings.append(warn)
        applied = 0

    await save_student_profile(
        session,
        extract,
        user_id=user_id,
        dimension_floors=floors,
        warnings=warnings,
        apply_floor_merge=True,
    )
    return applied, warnings


async def submit_improvement(
    session: AsyncSession,
    *,
    user_id: str,
    plan_id: str,
    reflection: str,
) -> dict:
    plan = await session.get(RemediationPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="补救计划不存在")

    existing = (
        await session.execute(
            select(ImprovementSubmission)
            .where(ImprovementSubmission.plan_id == plan.id)
            .order_by(desc(ImprovementSubmission.created_at))
        )
    ).scalars().all()
    # allow one retry after fail
    if existing:
        latest = existing[0]
        if latest.final_grade != GRADE_FAIL:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该计划已提交评分")
        if len(existing) >= 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不合格仅允许重提一次")

    steps = plan.steps_json or []
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="计划无补救步骤")
    if not all(isinstance(s, dict) and s.get("done") for s in steps):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先完成全部步骤并填写证据")
    if not (reflection or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写反思感想")

    grade, feedback, delta = await _ai_grade_submission(plan, reflection)
    submission = ImprovementSubmission(
        id=str(uuid4()),
        plan_id=plan.id,
        user_id=user_id,
        reflection=reflection.strip(),
        evidence_bundle={"steps": steps},
        ai_grade=grade,
        ai_feedback=feedback,
        ai_delta_json={plan.target_dimension: delta},
        final_grade=grade,
        warning_text=feedback if grade == GRADE_FAIL else "",
        teacher_reviewed=False,
    )
    session.add(submission)
    await session.flush()

    applied, _warnings = await _apply_grade_to_profile(
        session,
        user_id=user_id,
        plan=plan,
        grade=grade,
        delta=delta,
        submission_id=submission.id,
        warning_text=submission.warning_text,
    )
    submission.applied_delta = applied
    submission.applied_at = datetime.now(timezone.utc)
    submission.ai_delta_json = {plan.target_dimension: applied if applied else delta}
    plan.status = "graded"
    await session.commit()
    await session.refresh(submission)
    await session.refresh(plan)

    await record_learning_event(
        session,
        user_id,
        "improvement_graded",
        f"改进验收 {grade} · {plan.topic} · Δ{applied}",
        {"plan_id": plan.id, "grade": grade, "delta": applied, "dimension": plan.target_dimension},
    )

    return _plan_out(plan, submission)


async def override_improvement(
    session: AsyncSession,
    *,
    teacher: User,
    submission_id: str,
    grade: str,
    feedback: str = "",
) -> dict:
    if grade not in VALID_GRADES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效档位")
    submission = await session.get(ImprovementSubmission, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提交不存在")
    plan = await session.get(RemediationPlan, submission.plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="补救计划不存在")

    # optional: teacher must share class with student
    student = await session.get(User, submission.user_id)
    if student and teacher.class_id and student.class_id and teacher.class_id != student.class_id:
        if student.teacher_id and student.teacher_id != teacher.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权复核该学生")

    old_grade = submission.final_grade
    old_applied = int(submission.applied_delta or 0)
    new_delta = GRADE_DELTA[grade]

    # revert previous applied delta then apply new
    latest = await get_latest_profile(session, user_id=submission.user_id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="学生尚无画像")

    extract = _profile_to_extract(latest)
    floors = dict(latest.dimension_floors_json or {})
    warnings = list(latest.warnings_json or [])
    dim = plan.target_dimension
    dim_obj = getattr(extract, dim)
    # undo old boost
    if old_applied > 0:
        dim_obj.score = max(0, int(dim_obj.score or 0) - old_applied)

    submission.teacher_grade = grade
    submission.teacher_feedback = feedback or ""
    submission.final_grade = grade
    submission.teacher_reviewed = True
    submission.warning_text = feedback if grade == GRADE_FAIL else ""

    applied = 0
    if grade in (GRADE_EXCELLENT, GRADE_PASS):
        used = await _weekly_delta_sum(session, submission.user_id, dim)
        # exclude current submission's previous count by subtracting old_applied already undone from profile
        room = max(0, WEEKLY_DELTA_CAP - max(0, used - (old_applied if old_grade in (GRADE_EXCELLENT, GRADE_PASS) else 0)))
        applied = min(new_delta, room)
        dim_obj.score = min(100, int(dim_obj.score or 0) + applied)
        floors[dim] = max(int(floors.get(dim) or 0), int(dim_obj.score))
        warnings = [w for w in warnings if not (isinstance(w, dict) and w.get("dimension") == dim)]
        evidence = list(dim_obj.evidence or [])
        evidence.append(f"教师覆盖 {old_grade}→{grade} +{applied}")
        dim_obj.evidence = evidence[-12:]
    else:
        warn = {
            "dimension": dim,
            "text": feedback or "教师判定不合格，需针对错因重新完成证据。",
            "source_submission_id": submission.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        warnings = [w for w in warnings if not (isinstance(w, dict) and w.get("dimension") == dim)]
        warnings.append(warn)
        # lower floor only if it was solely from this submission — keep max of remaining score
        floors[dim] = max(int(floors.get(dim) or 0), int(dim_obj.score or 0))

    submission.applied_delta = applied
    submission.ai_delta_json = {dim: applied if applied else new_delta}
    submission.applied_at = datetime.now(timezone.utc)
    plan.status = "overridden"

    extract.summary = (extract.summary or "") + f" [教师覆盖 {grade}]"
    await save_student_profile(
        session,
        extract,
        user_id=submission.user_id,
        dimension_floors=floors,
        warnings=warnings,
        apply_floor_merge=True,
    )
    await session.commit()
    await session.refresh(submission)
    await session.refresh(plan)
    return _plan_out(plan, submission)


async def list_pending_for_teacher(session: AsyncSession, teacher: User) -> list[dict]:
    """List graded-but-not-teacher-reviewed submissions for teacher's students."""
    stmt = (
        select(ImprovementSubmission, RemediationPlan, User)
        .join(RemediationPlan, RemediationPlan.id == ImprovementSubmission.plan_id)
        .join(User, User.id == ImprovementSubmission.user_id)
        .where(ImprovementSubmission.teacher_reviewed.is_(False))
        .order_by(desc(ImprovementSubmission.created_at))
        .limit(50)
    )
    rows = (await session.execute(stmt)).all()
    out = []
    for submission, plan, student in rows:
        if teacher.class_id and student.class_id and student.class_id != teacher.class_id:
            if student.teacher_id != teacher.id:
                continue
        item = _plan_out(plan, submission)
        item["student_name"] = student.display_name or student.username
        item["student_id"] = student.id
        out.append(item)
    return out


async def get_user_profile_meta(session: AsyncSession, user_id: str) -> dict:
    from app.services.profile_refresh import profile_source_meta

    latest = await get_latest_profile(session, user_id=user_id)
    extra = await profile_source_meta(session, user_id)
    if latest is None:
        return {
            "warnings": [],
            "floors": {},
            "has_profile": False,
            **extra,
        }
    return {
        "warnings": latest.warnings_json or [],
        "floors": latest.dimension_floors_json or {},
        "has_profile": True,
        "profile_id": latest.id,
        "summary": latest.summary,
        **extra,
    }
