"""面试弱项回流：错题本 / 复习卡 / 学习事件 / 定向资源包 / 作业提交。"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import AssignmentSubmission
from app.models.generated_resource import GeneratedResource, ProfileLearningEvent
from app.models.mock_interview import InterviewReport, InterviewSession, InterviewTurn
from app.models.review import ReviewCard
from app.models.zone_extras import MistakeRecord
from app.services.interview_catalog import role_label
from app.services.interview_scoring import dimension_labels

logger = logging.getLogger(__name__)

WEAK_SCORE = 70.0


async def apply_interview_closed_loop(
    db: AsyncSession,
    session: InterviewSession,
    report: InterviewReport,
    turns: list[InterviewTurn],
) -> list[dict]:
    refs: list[dict] = []
    weak_turns = [t for t in turns if t.fused_score is not None and float(t.fused_score) < WEAK_SCORE]
    subject = role_label(session.job_role)

    for turn in weak_turns[:6]:
        mistake = MistakeRecord(
            id=str(uuid4()),
            user_id=session.user_id,
            question=turn.question,
            student_answer=turn.transcript[:2000],
            correct_answer=turn.feedback[:1000],
            subject=subject,
            note=f"模拟面试弱项（综合 {turn.fused_score}）",
        )
        db.add(mistake)
        refs.append({"kind": "mistake", "id": mistake.id, "title": turn.question[:40]})

        card = ReviewCard(
            id=str(uuid4()),
            user_id=session.user_id,
            kind="card",
            source_id=f"interview:{turn.id}",
            front=turn.question,
            back=turn.feedback or "回看本轮点评，用 STAR 再答一遍。",
            extra=subject,
        )
        db.add(card)
        refs.append({"kind": "review", "id": card.id, "title": turn.question[:40]})

    labels = dimension_labels(session.scenario)
    weak_dims = [
        labels.get(k, k)
        for k, v in (report.dimension_scores or {}).items()
        if isinstance(v, (int, float)) and float(v) < WEAK_SCORE
    ]
    body = [
        f"# {subject} 面试复盘包",
        "",
        report.summary or "",
        "",
        "## 关键问题",
        *[f"- {x}" for x in (report.key_issues or [])],
        "",
        "## 改进建议",
        *[f"- {x}" for x in (report.suggestions or [])],
        "",
        "## 弱项维度",
        ", ".join(weak_dims) or "本场未出现明显弱项",
    ]
    resource = GeneratedResource(
        id=str(uuid4()),
        user_id=session.user_id,
        planet_slug="interview-remediation",
        planet_name=f"面试复盘 · {subject}",
        kind="doc",
        title=f"模拟面试复盘：{subject}",
        content="\n".join(body),
        meta_json={"source": "interview", "session_id": session.id, "scenario": session.scenario},
        review_status="approved",
    )
    db.add(resource)
    refs.append({"kind": "resource", "id": resource.id, "title": resource.title})

    event = ProfileLearningEvent(
        id=str(uuid4()),
        user_id=session.user_id,
        event_type="interview_completed",
        summary=f"完成{subject}模拟面试，总分 {session.overall_score}",
        payload_json={
            "session_id": session.id,
            "overall_score": session.overall_score,
            "dimension_scores": report.dimension_scores,
            "weak_turns": len(weak_turns),
        },
    )
    db.add(event)

    if session.assignment_id:
        existing = (
            await db.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == session.assignment_id,
                    AssignmentSubmission.student_id == session.user_id,
                )
            )
        ).scalar_one_or_none()
        score_int = int(round(float(session.overall_score or 0)))
        now = datetime.now(timezone.utc)
        if existing:
            existing.score = score_int
            existing.feedback = report.summary[:2000]
            existing.status = "graded"
            existing.submitted_at = existing.submitted_at or now
            existing.graded_at = now
            existing.content = f"interview:{session.id}"
        else:
            db.add(
                AssignmentSubmission(
                    id=str(uuid4()),
                    assignment_id=session.assignment_id,
                    student_id=session.user_id,
                    content=f"interview:{session.id}",
                    score=score_int,
                    feedback=report.summary[:2000],
                    status="graded",
                    submitted_at=now,
                    graded_at=now,
                )
            )
        refs.append({"kind": "assignment", "id": session.assignment_id, "title": "已回写作业成绩"})

    report.resource_refs = refs
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("interview closed loop failed: %s", exc)
        await db.rollback()
        return []
    return refs
