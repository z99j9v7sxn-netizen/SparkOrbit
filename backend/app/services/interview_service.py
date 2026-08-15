"""模拟面试 CRUD 与序列化。"""
from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import INTERVIEW_DIR
from app.models.assignment import Assignment, AssignmentSubmission
from app.models.mock_interview import InterviewReport, InterviewSession, InterviewTurn
from app.models.user import User
from app.services.interview_catalog import kind_labels, role_label
from app.services.interview_runtime import register_prep
from app.services.interview_scoring import dimension_labels, dimensions_for
from app.services.upload_service import save_upload_bytes

logger = logging.getLogger(__name__)
INTERVIEW_MEDIA_TTL_DAYS = 30


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def serialize_turn(row: InterviewTurn) -> dict[str, Any]:
    return {
        "id": row.id,
        "turn_index": row.turn_index,
        "question": row.question,
        "question_kind": row.question_kind,
        "transcript": row.transcript,
        "audio_url": row.audio_url,
        "frame_urls": list(row.frame_urls or []),
        "semantic_score": row.semantic_score,
        "prosody_score": row.prosody_score,
        "visual_score": row.visual_score,
        "fused_score": row.fused_score,
        "prosody_detail": dict(row.prosody_detail or {}),
        "feedback": row.feedback,
        "followup_strategy": row.followup_strategy,
        "duration_sec": row.duration_sec,
    }


def serialize_report(row: InterviewReport, scenario: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "dimension_scores": dict(row.dimension_scores or {}),
        "dimension_labels": dimension_labels(scenario),
        "key_issues": list(row.key_issues or []),
        "suggestions": list(row.suggestions or []),
        "resource_refs": list(row.resource_refs or []),
        "council_views": dict(row.council_views or {}),
        "teacher_comment": row.teacher_comment,
        "teacher_score": row.teacher_score,
        "review_status": row.review_status,
        "degraded_modalities": list(row.degraded_modalities or []),
        "summary": row.summary,
        "created_at": _iso(row.created_at),
    }


def serialize_session_brief(row: InterviewSession, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "scenario": row.scenario,
        "job_role": row.job_role,
        "job_role_label": role_label(row.job_role),
        "difficulty": row.difficulty,
        "question_count": row.question_count,
        "status": row.status,
        "overall_score": row.overall_score,
        "current_turn": row.current_turn,
        "created_at": _iso(row.created_at),
        "finished_at": _iso(row.finished_at),
        "user_id": row.user_id,
        "assignment_id": row.assignment_id or "",
        "student_name": "",
        "review_status": "",
    }
    if extra:
        data.update(extra)
    return data


def serialize_questions(row: InterviewSession) -> list[dict[str, Any]]:
    labels = kind_labels(row.scenario)
    out = []
    for item in row.questions or []:
        kind = str(item.get("kind") or "")
        out.append(
            {
                "index": int(item.get("index") or len(out)),
                "kind": kind,
                "kind_label": labels.get(kind, kind),
                "question": str(item.get("question") or ""),
                "followup_of": str(item.get("followup_of") or ""),
            }
        )
    return out


def unlink_interview_url(url: str) -> None:
    name = Path(str(url or "")).name
    if not name or ".." in name:
        return
    path = INTERVIEW_DIR / name
    try:
        if path.is_file():
            path.unlink()
    except OSError as exc:
        logger.warning("unlink interview media %s: %s", path, exc)


def persist_frame_urls(raw_frames: list[str] | None) -> list[str]:
    urls: list[str] = []
    for item in list(raw_frames or [])[:4]:
        text = str(item or "")
        if text.startswith("/static/"):
            urls.append(text)
            continue
        if not text.startswith("data:image"):
            continue
        try:
            _header, b64 = text.split(",", 1)
            raw = base64.b64decode(b64)
            urls.append(save_upload_bytes(raw, INTERVIEW_DIR, "interview", content_type="image/jpeg"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist interview frame: %s", exc)
    return urls


def maybe_insert_followup(
    questions: list[dict[str, Any]],
    *,
    answered_index: int,
    strategy: str,
    followup_question: str,
    followup_of: str,
) -> tuple[list[dict[str, Any]], bool]:
    """一层追问：原题后插入一题；已是追问则不再追。"""
    text = str(followup_question or "").strip()
    if strategy not in {"probe", "challenge"} or not text:
        return list(questions or []), False
    qs = [dict(item) for item in (questions or [])]
    if not (0 <= answered_index < len(qs)):
        return qs, False
    if str(qs[answered_index].get("followup_of") or ""):
        return qs, False
    qs.insert(
        answered_index + 1,
        {
            "index": answered_index + 1,
            "kind": str(qs[answered_index].get("kind") or "followup"),
            "question": text,
            "followup_of": followup_of,
        },
    )
    for i, item in enumerate(qs):
        item["index"] = i
    return qs, True


async def serialize_session_detail(db: AsyncSession, row: InterviewSession) -> dict[str, Any]:
    turns = list(
        (
            await db.execute(
                select(InterviewTurn).where(InterviewTurn.session_id == row.id).order_by(InterviewTurn.turn_index.asc())
            )
        )
        .scalars()
        .all()
    )
    report = (
        await db.execute(select(InterviewReport).where(InterviewReport.session_id == row.id))
    ).scalar_one_or_none()
    data = serialize_session_brief(row)
    data.update(
        {
            "class_id": row.class_id,
            "resume_url": row.resume_url,
            "resume_profile": dict(row.resume_profile or {}),
            "questions": serialize_questions(row),
            "turns": [serialize_turn(t) for t in turns],
            "report": serialize_report(report, row.scenario) if report else None,
            "prep_run_id": row.prep_run_id,
            "prep_intel": dict(row.prep_intel or {}),
            "dimension_labels": dimension_labels(row.scenario),
        }
    )
    return data


async def create_session(db: AsyncSession, user: User, payload: dict[str, Any]) -> InterviewSession:
    scenario = payload.get("scenario") if payload.get("scenario") in {"job", "academic"} else "job"
    difficulty = payload.get("difficulty") if payload.get("difficulty") in {"easy", "medium", "hard"} else "medium"
    row = InterviewSession(
        id=str(uuid4()),
        user_id=user.id,
        class_id=user.class_id or "",
        scenario=scenario,
        job_role=str(payload.get("job_role") or "backend"),
        difficulty=difficulty,
        question_count=int(payload.get("question_count") or 4),
        status="preparing",
        resume_url=str(payload.get("resume_url") or ""),
        resume_profile=dict(payload.get("resume_profile") or {}),
        assignment_id=str(payload.get("assignment_id") or ""),
        consent_at=datetime.now(timezone.utc) if payload.get("consent", True) else None,
        prep_run_id=f"iv-prep-{uuid4().hex[:10]}",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    register_prep(row.id, user.id)
    from app.services.interview_agents import run_interview_prep

    asyncio.create_task(run_interview_prep(row.id))
    return row


async def list_sessions(db: AsyncSession, user_id: str, limit: int = 40) -> list[InterviewSession]:
    stmt = (
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.created_at.desc())
        .limit(min(max(limit, 1), 100))
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_owned_session(db: AsyncSession, user_id: str, session_id: str) -> InterviewSession | None:
    row = await db.get(InterviewSession, session_id)
    if row is None or row.user_id != user_id:
        return None
    return row


async def persist_turn(
    db: AsyncSession,
    session: InterviewSession,
    *,
    question: str,
    question_kind: str,
    transcript: str,
    result: dict[str, Any],
    audio_url: str = "",
    followup_of: str = "",
) -> InterviewTurn:
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    prosody = result.get("prosody") if isinstance(result.get("prosody"), dict) else {}
    visual = result.get("visual") if isinstance(result.get("visual"), dict) else {}
    row = InterviewTurn(
        id=str(uuid4()),
        session_id=session.id,
        turn_index=session.current_turn,
        question=question,
        question_kind=question_kind,
        transcript=transcript,
        audio_url=audio_url,
        frame_urls=persist_frame_urls(list(result.get("frames") or [])),
        semantic_score=float(semantic["score"]) if semantic.get("score") is not None else None,
        prosody_score=float(prosody["score"]) if prosody.get("score") is not None else None,
        visual_score=float(visual["score"]) if visual.get("score") is not None else None,
        fused_score=float(result["fused"]) if result.get("fused") is not None else None,
        prosody_detail=dict(prosody or {}),
        feedback=str(result.get("feedback") or ""),
        followup_of=followup_of,
        followup_strategy=str(result.get("followup_strategy") or "next"),
        duration_sec=float(result.get("duration_sec") or result.get("prosody", {}).get("duration_sec") or 0),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(row)
    session.current_turn = int(session.current_turn) + 1
    session.status = "running"
    await db.commit()
    await db.refresh(row)
    return row


def _interview_spec_from_assignment(row: Assignment) -> dict[str, Any]:
    questions = list(row.questions_json or [])
    spec = next((q for q in questions if str(q.get("kind") or "") == "interview"), questions[0] if questions else {})
    spec = dict(spec or {})
    return {
        "assignment_id": row.id,
        "title": row.title,
        "description": row.description,
        "due_at": _iso(row.due_at),
        "scenario": spec.get("scenario") if spec.get("scenario") in {"job", "academic"} else "job",
        "job_role": str(spec.get("job_role") or "backend"),
        "question_count": int(spec.get("question_count") or 4),
        "difficulty": spec.get("difficulty") if spec.get("difficulty") in {"easy", "medium", "hard"} else "medium",
        "stem": str(spec.get("stem") or spec.get("question") or row.description or ""),
    }


def _is_interview_assignment(row: Assignment) -> bool:
    if str(row.galaxy_slug or "") == "interview":
        return True
    return any(str(q.get("kind") or "") == "interview" for q in (row.questions_json or []))


async def list_student_interview_tasks(db: AsyncSession, user: User) -> list[dict[str, Any]]:
    if not user.class_id:
        return []
    rows = list(
        (
            await db.execute(
                select(Assignment)
                .where(Assignment.class_id == user.class_id)
                .order_by(Assignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        if not _is_interview_assignment(row):
            continue
        spec = _interview_spec_from_assignment(row)
        sub = (
            await db.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == row.id,
                    AssignmentSubmission.student_id == user.id,
                )
            )
        ).scalar_one_or_none()
        spec["my_status"] = sub.status if sub else "pending"
        spec["my_score"] = sub.score if sub else None
        out.append(spec)
    return out


async def _purge_session_media(db: AsyncSession, session: InterviewSession) -> None:
    turns = list(
        (await db.execute(select(InterviewTurn).where(InterviewTurn.session_id == session.id))).scalars().all()
    )
    for turn in turns:
        unlink_interview_url(turn.audio_url)
        for url in turn.frame_urls or []:
            unlink_interview_url(str(url))
        turn.audio_url = ""
        turn.frame_urls = []
    unlink_interview_url(session.resume_url)


async def delete_owned_session(db: AsyncSession, user_id: str, session_id: str) -> bool:
    row = await get_owned_session(db, user_id, session_id)
    if row is None:
        return False
    await _purge_session_media(db, row)
    turns = list((await db.execute(select(InterviewTurn).where(InterviewTurn.session_id == row.id))).scalars().all())
    for turn in turns:
        await db.delete(turn)
    report = (await db.execute(select(InterviewReport).where(InterviewReport.session_id == row.id))).scalar_one_or_none()
    if report:
        await db.delete(report)
    await db.delete(row)
    await db.commit()
    return True


async def apply_followup_to_session(
    db: AsyncSession,
    session: InterviewSession,
    *,
    answered_index: int,
    strategy: str,
    followup_question: str,
    followup_of: str,
) -> bool:
    questions, inserted = maybe_insert_followup(
        list(session.questions or []),
        answered_index=answered_index,
        strategy=strategy,
        followup_question=followup_question,
        followup_of=followup_of,
    )
    if not inserted:
        return False
    session.questions = questions
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(session, "questions")
    await db.commit()
    await db.refresh(session)
    return True


async def _teacher_class_ids(db: AsyncSession, teacher: User) -> list[str]:
    from app.services.teacher import _class_ids_for_teacher

    return await _class_ids_for_teacher(db, teacher)


async def teacher_can_see(db: AsyncSession, teacher: User, session: InterviewSession) -> bool:
    ids = await _teacher_class_ids(db, teacher)
    return bool(session.class_id) and session.class_id in ids


async def list_teacher_sessions(
    db: AsyncSession, teacher: User, *, limit: int = 80
) -> list[InterviewSession]:
    ids = await _teacher_class_ids(db, teacher)
    if not ids:
        return []
    stmt = (
        select(InterviewSession)
        .where(InterviewSession.class_id.in_(ids))
        .order_by(InterviewSession.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list((await db.execute(stmt)).scalars().all())


async def serialize_teacher_session_brief(db: AsyncSession, row: InterviewSession) -> dict[str, Any]:
    student = await db.get(User, row.user_id)
    report = (await db.execute(select(InterviewReport).where(InterviewReport.session_id == row.id))).scalar_one_or_none()
    return serialize_session_brief(
        row,
        extra={
            "student_name": (student.display_name if student else "") or (student.username if student else ""),
            "review_status": report.review_status if report else "",
        },
    )


async def teacher_overview(db: AsyncSession, teacher: User) -> dict[str, Any]:
    rows = await list_teacher_sessions(db, teacher, limit=200)
    completed = [r for r in rows if r.status == "completed"]
    scores = [float(r.overall_score) for r in completed if r.overall_score is not None]
    pending = 0
    for row in completed:
        report = (
            await db.execute(select(InterviewReport).where(InterviewReport.session_id == row.id))
        ).scalar_one_or_none()
        if report and report.review_status == "pending":
            pending += 1
    return {
        "total": len(rows),
        "completed": len(completed),
        "pending_review": pending,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "job_count": sum(1 for r in rows if r.scenario == "job"),
        "academic_count": sum(1 for r in rows if r.scenario == "academic"),
    }


async def review_report(
    db: AsyncSession,
    teacher: User,
    report_id: str,
    *,
    comment: str = "",
    score: float | None = None,
    status: str = "reviewed",
) -> InterviewReport | None:
    report = await db.get(InterviewReport, report_id)
    if report is None:
        return None
    session = await db.get(InterviewSession, report.session_id)
    if session is None or not await teacher_can_see(db, teacher, session):
        return None
    report.teacher_comment = comment[:2000]
    if score is not None:
        report.teacher_score = float(score)
    report.review_status = status if status in {"pending", "reviewed", "rejected"} else "reviewed"
    await db.commit()
    await db.refresh(report)
    return report


async def purge_expired_interview_media(db: AsyncSession, *, days: int = INTERVIEW_MEDIA_TTL_DAYS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    turns = list(
        (
            await db.execute(
                select(InterviewTurn).where(InterviewTurn.created_at < cutoff)
            )
        )
        .scalars()
        .all()
    )
    cleared = 0
    for turn in turns:
        changed = False
        if turn.audio_url:
            unlink_interview_url(turn.audio_url)
            turn.audio_url = ""
            changed = True
        if turn.frame_urls:
            for url in turn.frame_urls or []:
                unlink_interview_url(str(url))
            turn.frame_urls = []
            changed = True
        if changed:
            cleared += 1
    if cleared:
        await db.commit()
    return cleared


WEAK_DIM_THRESHOLD = 70.0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _empty_scenario_block(scenario: str) -> dict[str, Any]:
    return {
        "count": 0,
        "avg_score": None,
        "dimension_avg": {},
        "dimension_latest": {},
        "dimension_labels": dimension_labels(scenario),
        "latest_id": "",
        "latest_job_role": "",
        "latest_job_role_label": "",
    }


def _scenario_block(
    rows: list[InterviewSession],
    reports: dict[str, InterviewReport],
    scenario: str,
) -> dict[str, Any]:
    subset = [s for s in rows if s.scenario == scenario]
    labels = dimension_labels(scenario)
    keys = [key for key, _ in dimensions_for(scenario)]
    buckets: dict[str, list[float]] = {k: [] for k in keys}
    for session in subset:
        report = reports.get(session.id)
        scores = dict((report.dimension_scores if report else session.dimension_scores) or {})
        for key in keys:
            raw = scores.get(key)
            if isinstance(raw, (int, float)):
                buckets[key].append(float(raw))
    latest = subset[0] if subset else None
    latest_report = reports.get(latest.id) if latest else None
    latest_scores = dict(
        (latest_report.dimension_scores if latest_report else (latest.dimension_scores if latest else {})) or {}
    )
    scores_only = [float(s.overall_score) for s in subset if s.overall_score is not None]
    return {
        "count": len(subset),
        "avg_score": _mean(scores_only),
        "dimension_avg": {k: avg for k, vals in buckets.items() if (avg := _mean(vals)) is not None},
        "dimension_latest": {
            k: round(float(v), 1) for k, v in latest_scores.items() if isinstance(v, (int, float))
        },
        "dimension_labels": labels,
        "latest_id": latest.id if latest else "",
        "latest_job_role": latest.job_role if latest else "",
        "latest_job_role_label": role_label(latest.job_role) if latest else "",
    }


def aggregate_interview_portrait(
    sessions: list[InterviewSession],
    reports: dict[str, InterviewReport],
) -> dict[str, Any]:
    completed = [s for s in sessions if s.status == "completed"]
    empty_loop = {"mistake": 0, "review": 0, "resource": 0, "assignment": 0}
    if not completed:
        return {
            "session_count": 0,
            "avg_score": None,
            "latest": None,
            "job": _empty_scenario_block("job"),
            "academic": _empty_scenario_block("academic"),
            "by_role": [],
            "trend": [],
            "weak_dims": [],
            "loop_counts": empty_loop,
            "recent_refs": [],
        }

    job = _scenario_block(completed, reports, "job")
    academic = _scenario_block(completed, reports, "academic")
    overalls = [float(s.overall_score) for s in completed if s.overall_score is not None]
    latest = completed[0]
    latest_report = reports.get(latest.id)

    role_groups: dict[str, list[InterviewSession]] = {}
    for session in completed:
        role_groups.setdefault(session.job_role, []).append(session)
    by_role: list[dict[str, Any]] = []
    for key, rows in role_groups.items():
        scores = [float(s.overall_score) for s in rows if s.overall_score is not None]
        by_role.append(
            {
                "job_role": key,
                "job_role_label": role_label(key),
                "scenario": rows[0].scenario,
                "count": len(rows),
                "avg_score": _mean(scores),
            }
        )
    by_role.sort(key=lambda item: -(item["avg_score"] if item["avg_score"] is not None else -1))

    trend_src = list(reversed(completed[:12]))
    trend = [
        {
            "id": s.id,
            "at": _iso(s.finished_at or s.created_at),
            "overall_score": s.overall_score,
            "scenario": s.scenario,
            "job_role_label": role_label(s.job_role),
        }
        for s in trend_src
    ]

    weak_dims: list[dict[str, Any]] = []
    for scenario, block in (("job", job), ("academic", academic)):
        labels = block["dimension_labels"]
        for key, avg in (block["dimension_avg"] or {}).items():
            if isinstance(avg, (int, float)) and float(avg) < WEAK_DIM_THRESHOLD:
                weak_dims.append(
                    {
                        "key": key,
                        "label": labels.get(key, key),
                        "avg": float(avg),
                        "scenario": scenario,
                    }
                )
    weak_dims.sort(key=lambda item: item["avg"])

    loop_counts = dict(empty_loop)
    for report in reports.values():
        for ref in report.resource_refs or []:
            kind = str((ref or {}).get("kind") or "")
            if kind in loop_counts:
                loop_counts[kind] += 1
    recent_refs = [dict(item) for item in (latest_report.resource_refs or [])][:8] if latest_report else []

    return {
        "session_count": len(completed),
        "avg_score": _mean(overalls),
        "latest": {
            "id": latest.id,
            "scenario": latest.scenario,
            "job_role": latest.job_role,
            "job_role_label": role_label(latest.job_role),
            "overall_score": latest.overall_score,
            "created_at": _iso(latest.created_at),
        },
        "job": job,
        "academic": academic,
        "by_role": by_role,
        "trend": trend,
        "weak_dims": weak_dims,
        "loop_counts": loop_counts,
        "recent_refs": recent_refs,
    }


async def get_interview_portrait(db: AsyncSession, user_id: str) -> dict[str, Any]:
    sessions = await list_sessions(db, user_id, limit=80)
    completed_ids = [s.id for s in sessions if s.status == "completed"]
    reports: dict[str, InterviewReport] = {}
    if completed_ids:
        rows = list(
            (
                await db.execute(select(InterviewReport).where(InterviewReport.session_id.in_(completed_ids)))
            )
            .scalars()
            .all()
        )
        reports = {row.session_id: row for row in rows}
    return aggregate_interview_portrait(sessions, reports)
