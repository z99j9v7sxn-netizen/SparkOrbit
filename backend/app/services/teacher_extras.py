from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment, AssignmentSubmission, AttendanceRecord, TeacherBroadcast
from app.models.galaxy import Planet
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.school_class import SchoolClass
from app.models.user import User
from app.models.zone_extras import FocusSession, MistakeRecord
from app.models.alert import Alert
from app.models.student_profile import PROFILE_DIMENSIONS, StudentProfile
from app.services.notification_service import create_notification
from app.services.teacher import _students, list_teacher_classes


async def create_assignment(
    session: AsyncSession,
    teacher: User,
    *,
    class_id: str,
    title: str,
    description: str,
    galaxy_slug: str = "",
    due_at: datetime | None = None,
    questions: list | None = None,
    source_resource_id: str = "",
) -> dict:
    if not class_id:
        classes = await list_teacher_classes(session, teacher)
        class_id = classes[0].id if classes else ""
    qs = list(questions or [])
    desc = description.strip()
    if qs and not desc:
        from app.services.assignment_extract import questions_to_description

        desc = questions_to_description(qs)
    row = Assignment(
        teacher_id=teacher.id,
        class_id=class_id,
        title=title.strip(),
        description=desc,
        galaxy_slug=galaxy_slug.strip(),
        questions_json=qs,
        source_resource_id=(source_resource_id or "").strip(),
        due_at=due_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _assignment_out(row, submission_count=0)


def _assignment_out(row: Assignment, submission_count: int = 0) -> dict:
    return {
        "id": row.id,
        "class_id": row.class_id,
        "title": row.title,
        "description": row.description,
        "galaxy_slug": row.galaxy_slug,
        "due_at": row.due_at.isoformat() if row.due_at else "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "submission_count": submission_count,
        "questions": list(getattr(row, "questions_json", None) or []),
        "source_resource_id": getattr(row, "source_resource_id", None) or "",
    }


async def list_teacher_assignments(session: AsyncSession, teacher: User, class_id: str = "") -> list[dict]:
    stmt = select(Assignment).where(Assignment.teacher_id == teacher.id).order_by(Assignment.created_at.desc())
    if class_id:
        stmt = stmt.where(Assignment.class_id == class_id)
    rows = (await session.execute(stmt)).scalars().all()
    out = []
    for row in rows:
        count = (
            await session.execute(
                select(func.count()).select_from(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == row.id,
                    AssignmentSubmission.status != "pending",
                )
            )
        ).scalar_one()
        out.append(_assignment_out(row, submission_count=int(count or 0)))
    return out


async def list_student_assignments(session: AsyncSession, student: User) -> list[dict]:
    if not student.class_id:
        return []
    rows = (
        await session.execute(
            select(Assignment)
            .where(Assignment.class_id == student.class_id)
            .order_by(Assignment.created_at.desc())
        )
    ).scalars().all()
    out = []
    for row in rows:
        sub = (
            await session.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == row.id,
                    AssignmentSubmission.student_id == student.id,
                )
            )
        ).scalar_one_or_none()
        out.append({
            **_assignment_out(row),
            "my_status": sub.status if sub else "pending",
            "my_score": sub.score if sub else None,
            "submission_id": sub.id if sub else "",
        })
    return out


async def submit_assignment(
    session: AsyncSession, student: User, assignment_id: str, content: str, attachment_url: str = ""
) -> dict:
    assignment = (
        await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None:
        raise ValueError("作业不存在")
    if assignment.class_id and assignment.class_id != student.class_id:
        raise ValueError("无权提交该作业")
    existing = (
        await session.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id == assignment_id,
                AssignmentSubmission.student_id == student.id,
            )
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.content = content.strip()
        existing.attachment_url = attachment_url.strip()
        existing.status = "submitted"
        existing.submitted_at = now
        row = existing
    else:
        row = AssignmentSubmission(
            assignment_id=assignment_id,
            student_id=student.id,
            content=content.strip(),
            attachment_url=attachment_url.strip(),
            status="submitted",
            submitted_at=now,
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": row.id,
        "assignment_id": row.assignment_id,
        "status": row.status,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else "",
    }


async def list_submissions(session: AsyncSession, teacher: User, assignment_id: str) -> list[dict]:
    assignment = (
        await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None or (assignment.teacher_id != teacher.id and teacher.role != "admin"):
        return []
    rows = (
        await session.execute(
            select(AssignmentSubmission, User)
            .join(User, User.id == AssignmentSubmission.student_id)
            .where(AssignmentSubmission.assignment_id == assignment_id)
            .order_by(AssignmentSubmission.submitted_at.desc())
        )
    ).all()
    return [
        {
            "id": sub.id,
            "student_id": sub.student_id,
            "student_name": user.display_name,
            "content": sub.content,
            "attachment_url": sub.attachment_url,
            "score": sub.score,
            "feedback": sub.feedback,
            "status": sub.status,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else "",
        }
        for sub, user in rows
    ]


async def grade_submission(
    session: AsyncSession, teacher: User, assignment_id: str, submission_id: str, score: int, feedback: str
) -> dict:
    sub = (
        await session.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.id == submission_id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise ValueError("提交记录不存在")
    assignment = (
        await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None or (assignment.teacher_id != teacher.id and teacher.role != "admin"):
        raise ValueError("无权批改")
    sub.score = max(0, min(100, score))
    sub.feedback = feedback.strip()
    sub.status = "graded"
    sub.graded_at = datetime.now(timezone.utc)
    await session.commit()
    return {"ok": True, "submission_id": sub.id, "score": sub.score}


async def gradebook(session: AsyncSession, teacher: User, class_id: str = "") -> list[dict]:
    students = await _students(session, teacher, class_id)
    total_planets = len((await session.execute(select(Planet))).scalars().all())
    out = []
    for u in students:
        mastery = (
            await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == u.id))
        ).scalars().all()
        lit = sum(1 for m in mastery if m.status == "lit")
        mastery_rate = round((lit / total_planets) * 100) if total_planets else 0

        challenges = (
            await session.execute(select(ChallengeQuestion).where(ChallengeQuestion.user_id == u.id))
        ).scalars().all()
        correct = sum(1 for c in challenges if c.correct)
        quiz_rate = round((correct / len(challenges)) * 100) if challenges else 0

        subs = (
            await session.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.student_id == u.id,
                    AssignmentSubmission.status == "graded",
                )
            )
        ).scalars().all()
        avg_score = round(sum(s.score or 0 for s in subs) / len(subs)) if subs else None

        out.append({
            "user_id": u.id,
            "display_name": u.display_name,
            "username": u.username,
            "mastery_rate": mastery_rate,
            "quiz_accuracy": quiz_rate,
            "assignment_avg": avg_score,
            "lit_count": lit,
            "total_planets": total_planets,
        })
    return out


async def broadcast_to_class(
    session: AsyncSession, teacher: User, class_id: str, title: str, body: str
) -> dict:
    if not class_id:
        raise ValueError("请选择班级")
    cls = (await session.execute(select(SchoolClass).where(SchoolClass.id == class_id))).scalar_one_or_none()
    if cls is None:
        raise ValueError("班级不存在")
    if teacher.role != "admin" and cls.teacher_id != teacher.id:
        raise ValueError("无权向该班级群发")
    students = (
        await session.execute(select(User).where(User.role == "student", User.class_id == class_id))
    ).scalars().all()
    for s in students:
        await create_notification(
            session,
            s.id,
            title.strip() or "教师通知",
            body.strip(),
            kind="teacher_broadcast",
            link="/student",
        )
    row = TeacherBroadcast(
        teacher_id=teacher.id,
        class_id=class_id,
        title=title.strip() or "教师通知",
        body=body.strip(),
        recipient_count=len(students),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "ok": True,
        "id": row.id,
        "recipient_count": row.recipient_count,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def list_broadcasts(session: AsyncSession, teacher: User, class_id: str = "") -> list[dict]:
    stmt = select(TeacherBroadcast).where(TeacherBroadcast.teacher_id == teacher.id).order_by(
        TeacherBroadcast.created_at.desc()
    )
    if class_id:
        stmt = stmt.where(TeacherBroadcast.class_id == class_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "class_id": r.class_id,
            "title": r.title,
            "body": r.body,
            "recipient_count": r.recipient_count,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def set_attendance(
    session: AsyncSession, teacher: User, class_id: str, student_id: str, status: str, record_date: str
) -> dict:
    existing = (
        await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_id == class_id,
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.record_date == record_date,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.status = status
        row = existing
    else:
        row = AttendanceRecord(
            class_id=class_id,
            student_id=student_id,
            teacher_id=teacher.id,
            record_date=record_date,
            status=status,
        )
        session.add(row)
    await session.commit()
    return {"ok": True, "student_id": student_id, "status": status, "date": record_date}


async def list_attendance(session: AsyncSession, teacher: User, class_id: str, record_date: str) -> list[dict]:
    students = await _students(session, teacher, class_id)
    records = (
        await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_id == class_id,
                AttendanceRecord.record_date == record_date,
            )
        )
    ).scalars().all()
    record_map = {r.student_id: r.status for r in records}
    return [
        {
            "student_id": s.id,
            "display_name": s.display_name,
            "status": record_map.get(s.id, "unknown"),
        }
        for s in students
    ]


async def student_accessible(
    session: AsyncSession, teacher: User, student_id: str, class_id: str = ""
) -> bool:
    student = (
        await session.execute(select(User).where(User.id == student_id, User.role == "student"))
    ).scalar_one_or_none()
    if student is None:
        return False
    allowed = await _students(session, teacher, class_id)
    return student.id in {s.id for s in allowed}


async def student_detail(session: AsyncSession, teacher: User, student_id: str, class_id: str = "") -> dict | None:
    student = (
        await session.execute(select(User).where(User.id == student_id, User.role == "student"))
    ).scalar_one_or_none()
    if student is None:
        return None
    allowed_students = await _students(session, teacher, class_id)
    allowed_ids = {s.id for s in allowed_students}
    if student.id not in allowed_ids:
        return None

    total_planets = len((await session.execute(select(Planet))).scalars().all())
    mastery = (
        await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == student.id))
    ).scalars().all()
    planets = (await session.execute(select(Planet))).scalars().all()
    planet_map = {p.id: p for p in planets}
    mastery_rows = []
    for m in mastery:
        p = planet_map.get(m.planet_id)
        if p:
            mastery_rows.append({
                "planet_slug": p.slug,
                "planet_name": p.name,
                "status": m.status,
                "score": float(m.score or 0),
            })

    profile = (
        await session.execute(
            select(StudentProfile)
            .where(StudentProfile.user_id == student.id)
            .order_by(StudentProfile.created_at.desc())
        )
    ).scalars().first()
    if profile is None and student.display_name:
        # 兼容旧数据：仅按姓名落库、user_id 为空的历史画像
        profile = (
            await session.execute(
                select(StudentProfile)
                .where(StudentProfile.student_name == student.display_name)
                .order_by(StudentProfile.created_at.desc())
            )
        ).scalars().first()

    alerts = (
        await session.execute(
            select(Alert).where(Alert.student_id == student.id).order_by(Alert.created_at.desc()).limit(20)
        )
    ).scalars().all()

    mistakes = (
        await session.execute(
            select(MistakeRecord).where(MistakeRecord.user_id == student.id).order_by(MistakeRecord.created_at.desc()).limit(20)
        )
    ).scalars().all()

    subs = (
        await session.execute(
            select(AssignmentSubmission, Assignment)
            .join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
            .where(AssignmentSubmission.student_id == student.id)
            .order_by(AssignmentSubmission.submitted_at.desc())
        )
    ).all()

    focus_minutes = (
        await session.execute(
            select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(FocusSession.user_id == student.id)
        )
    ).scalar_one()

    profile_data = None
    if profile:
        profile_data = {
            "id": profile.id,
            "student_name": profile.student_name,
            "summary": profile.summary,
            "dimensions": {
                dim: getattr(profile, dim) if isinstance(getattr(profile, dim), dict) else {}
                for dim in PROFILE_DIMENSIONS
            },
        }

    return {
        "user_id": student.id,
        "display_name": student.display_name,
        "username": student.username,
        "class_id": student.class_id,
        "mastery_rate": round((sum(1 for m in mastery if m.status == "lit") / total_planets) * 100) if total_planets else 0,
        "focus_minutes": int(focus_minutes or 0),
        "profile_id": profile.id if profile else "",
        "profile": profile_data,
        "mastery": mastery_rows,
        "alerts": [
            {"id": a.id, "type": a.alert_type, "message": a.message, "created_at": a.created_at.isoformat() if a.created_at else ""}
            for a in alerts
        ],
        "mistakes": [
            {"id": m.id, "question": m.question, "subject": m.subject, "created_at": m.created_at.isoformat() if m.created_at else ""}
            for m in mistakes
        ],
        "assignments": [
            {
                "assignment_title": asn.title,
                "status": sub.status,
                "score": sub.score,
                "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else "",
            }
            for sub, asn in subs
        ],
    }


async def insight_overview(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    """班级学情洞察：轻量聚合掌握率 / 证据 / 专注 / 风险。"""
    from collections import Counter
    from datetime import timedelta

    from app.services.evaluation import _aggregate_learn_evidence

    students = await _students(session, teacher, class_id)
    total_students = len(students)
    if not students:
        return {
            "class_id": class_id,
            "total_students": 0,
            "avg_mastery_rate": 0,
            "avg_quiz_accuracy": 0,
            "active_students_7d": 0,
            "total_evidence": 0,
            "risk_count": 0,
            "evidence_by_kind": {},
            "students": [],
        }

    total_planets = len((await session.execute(select(Planet))).scalars().all()) or 1
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).date().isoformat()

    student_rows: list[dict] = []
    kind_counter: Counter[str] = Counter()
    active_7d = 0
    sum_mastery = 0.0
    sum_quiz = 0.0
    total_evidence = 0

    for u in students:
        mastery = (
            await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == u.id))
        ).scalars().all()
        lit = sum(1 for m in mastery if m.status == "lit")
        mastery_rate = round((lit / total_planets) * 100) if total_planets else 0

        challenges = (
            await session.execute(select(ChallengeQuestion).where(ChallengeQuestion.user_id == u.id))
        ).scalars().all()
        correct = sum(1 for c in challenges if c.correct)
        quiz_rate = round((correct / len(challenges)) * 100) if challenges else 0

        ask_count, heat = _aggregate_learn_evidence(list(mastery))
        by_day = heat.get("by_day") or {}
        evidence_7d = sum(int(v) for d, v in by_day.items() if isinstance(d, str) and d >= week_ago and d != "unknown")
        if evidence_7d > 0:
            active_7d += 1
        for k, v in (heat.get("by_kind") or {}).items():
            kind_counter[str(k)] += int(v or 0)
        ev_total = int(heat.get("total_evidence") or 0)
        total_evidence += ev_total

        focus_minutes = (
            await session.execute(
                select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(FocusSession.user_id == u.id)
            )
        ).scalar() or 0

        sum_mastery += mastery_rate
        sum_quiz += quiz_rate
        student_rows.append(
            {
                "user_id": u.id,
                "display_name": u.display_name,
                "username": u.username,
                "mastery_rate": mastery_rate,
                "quiz_accuracy": quiz_rate,
                "evidence_7d": evidence_7d,
                "evidence_total": ev_total,
                "selection_ask_count": ask_count,
                "focus_minutes": int(focus_minutes),
            }
        )

    student_ids = [s.id for s in students]
    risk_count = 0
    if student_ids:
        risk_count = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Alert)
                    .where(Alert.student_id.in_(student_ids), Alert.resolved == False)  # noqa: E712
                )
            ).scalar()
            or 0
        )

    student_rows.sort(key=lambda x: (-x["evidence_7d"], -x["mastery_rate"]))
    return {
        "class_id": class_id,
        "total_students": total_students,
        "avg_mastery_rate": round(sum_mastery / total_students, 1) if total_students else 0,
        "avg_quiz_accuracy": round(sum_quiz / total_students, 1) if total_students else 0,
        "active_students_7d": active_7d,
        "total_evidence": total_evidence,
        "risk_count": risk_count,
        "evidence_by_kind": dict(kind_counter.most_common(12)),
        "students": student_rows,
    }


async def learning_story(
    session: AsyncSession,
    teacher: User,
    student_id: str,
    class_id: str = "",
) -> dict | None:
    """教师可解释学情条：画像弱项 + 四闸 + 最近 Agent + 待审工单。"""
    from app.models.agent_trace import AgentRun
    from app.models.hallucination import HallucinationTicket
    from app.services import mastery_gates as gates
    from app.services.gate_policy import get_thresholds_for_user
    from app.services.memory_decay import list_review_candidates

    base = await student_detail(session, teacher, student_id, class_id)
    if base is None:
        return None

    student = (
        await session.execute(select(User).where(User.id == student_id, User.role == "student"))
    ).scalar_one_or_none()
    if student is None:
        return None

    thr = await get_thresholds_for_user(session, student, "")
    mastery_rows = (
        await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == student.id))
    ).scalars().all()
    planets = (await session.execute(select(Planet))).scalars().all()
    planet_map = {p.id: p for p in planets}

    gate_rows: list[dict] = []
    stuck = 0
    for m in mastery_rows:
        p = planet_map.get(m.planet_id)
        if not p:
            continue
        snap = gates.gate_snapshot(m, thr)
        if m.status != "lit" and not m.is_permanent:
            stuck += 1
        gate_rows.append(
            {
                "planet_slug": p.slug,
                "planet_name": p.name,
                "status": m.status,
                "decay_state": m.decay_state or "",
                "next_gate": snap.get("next_gate"),
                "gates": snap.get("gates") or {},
                "lit": bool(snap.get("lit")),
            }
        )
    gate_rows.sort(key=lambda x: (1 if x["lit"] else 0, x["planet_name"]))

    review_cands = await list_review_candidates(session, student.id, refresh_decay=False)

    agent_runs = (
        await session.execute(
            select(AgentRun)
            .where(AgentRun.user_id == student.id)
            .order_by(AgentRun.created_at.desc())
            .limit(8)
        )
    ).scalars().all()
    recent_agents = [
        {
            "id": r.id,
            "scene": r.scene,
            "mode": r.mode,
            "status": r.status,
            "topic": r.topic or "",
            "current_agent": r.current_agent or "",
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in agent_runs
    ]

    tickets = (
        await session.execute(
            select(HallucinationTicket)
            .where(
                HallucinationTicket.student_id == student.id,
                HallucinationTicket.status == "pending",
            )
            .order_by(HallucinationTicket.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    pending_tickets = [
        {
            "id": t.id,
            "planet_slug": t.planet_slug,
            "planet_name": t.planet_name,
            "confidence": float(t.confidence or 0),
            "reason": t.reason or "",
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in tickets
    ]

    weak_dims: list[str] = []
    dims = (base.get("profile") or {}).get("dimensions") or {}
    for key, label in (
        ("prior_knowledge", "前置知识"),
        ("mistake_tendency", "易错倾向"),
        ("cognitive_style", "认知风格"),
        ("learning_goal", "学习目标"),
        ("time_flexibility", "时间弹性"),
        ("modality_preference", "模态偏好"),
        ("motivation_level", "动机强度"),
        ("major_background", "专业背景"),
    ):
        raw = dims.get(key) if isinstance(dims, dict) else None
        score = 50
        if isinstance(raw, dict):
            score = float(raw.get("score") or 50)
        elif isinstance(raw, (int, float)):
            score = float(raw)
        if score < 55:
            weak_dims.append(f"{label}({int(score)})")

    next_gates = [g for g in gate_rows if not g["lit"] and g.get("next_gate")][:3]
    narrative_parts = [
        f"{base['display_name']} 掌握率 {base['mastery_rate']}%，未点亮行星 {stuck} 颗。",
    ]
    if weak_dims:
        narrative_parts.append("画像偏弱：" + "、".join(weak_dims[:4]) + "。")
    if next_gates:
        narrative_parts.append(
            "当前闸门卡点："
            + "；".join(f"{g['planet_name']}→{g['next_gate']}" for g in next_gates)
            + "。"
        )
    if review_cands:
        narrative_parts.append(
            f"遗忘复习预警 {len(review_cands)} 颗（如 {review_cands[0]['planet_name']}）。"
        )
    if pending_tickets:
        narrative_parts.append(f"Shield 待审工单 {len(pending_tickets)} 条，建议人工覆盖评分。")
    if recent_agents:
        last = recent_agents[0]
        narrative_parts.append(
            f"最近 AI 动作：{last['mode'] or last['scene']}「{last['topic'] or '未命名'}」({last['status']})。"
        )
    else:
        narrative_parts.append("近期无 Agent 运行记录。")

    return {
        **base,
        "narrative": "".join(narrative_parts),
        "weak_dimensions": weak_dims,
        "gate_progress": gate_rows[:40],
        "review_planets": review_cands[:20],
        "recent_agent_runs": recent_agents,
        "pending_tickets": pending_tickets,
        "action_hints": [
            hint
            for hint in [
                "派发复习扫描" if review_cands else "",
                "处理 Shield 工单" if pending_tickets else "",
                "关注闸门卡点" if next_gates else "",
                "引导完善画像" if weak_dims else "",
            ]
            if hint
        ],
    }


def gradebook_to_csv(rows: list[dict]) -> str:
    lines = ["姓名,用户名,掌握率,答题正确率,作业均分,点亮行星,用户ID"]
    for r in rows:
        avg = "" if r.get("assignment_avg") is None else str(r.get("assignment_avg"))
        lit = f"{r.get('lit_count', 0)}/{r.get('total_planets', 0)}"
        lines.append(
            ",".join(
                [
                    _csv_cell(r.get("display_name")),
                    _csv_cell(r.get("username")),
                    str(r.get("mastery_rate", 0)),
                    str(r.get("quiz_accuracy", 0)),
                    avg,
                    lit,
                    _csv_cell(r.get("user_id")),
                ]
            )
        )
    return "\ufeff" + "\n".join(lines) + "\n"


def _csv_cell(value: object) -> str:
    text = str(value or "")
    if any(c in text for c in (",", '"', "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text


def parse_roster_csv(raw: str | bytes) -> list[dict]:
    """解析花名册 CSV：支持 username,display_name[,password] 或 学号,姓名。"""
    import csv
    import io

    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="ignore")
    else:
        text = raw.lstrip("\ufeff")

    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(str(c).strip() for c in r)]
    if not rows:
        return []

    header = [str(c).strip().lower() for c in rows[0]]
    start = 0
    user_idx, name_idx, pwd_idx = 0, 1, 2
    known = {"username", "user", "学号", "账号", "用户名", "display_name", "name", "姓名", "password", "密码"}
    if any(h in known for h in header):
        start = 1
        user_idx = next((i for i, h in enumerate(header) if h in ("username", "user", "学号", "账号", "用户名")), 0)
        name_idx = next((i for i, h in enumerate(header) if h in ("display_name", "name", "姓名")), 1 if len(header) > 1 else 0)
        pwd_idx = next((i for i, h in enumerate(header) if h in ("password", "密码")), -1)

    out: list[dict] = []
    for row in rows[start:]:
        cells = [str(c).strip() for c in row]
        if not cells or not cells[0]:
            continue
        username = cells[user_idx] if user_idx < len(cells) else ""
        display = cells[name_idx] if name_idx < len(cells) else username
        password = "123456"
        if pwd_idx >= 0 and pwd_idx < len(cells) and cells[pwd_idx]:
            password = cells[pwd_idx]
        elif len(cells) > 2 and pwd_idx < 0 and cells[2] and cells[2] not in (username, display):
            # 第三列像密码时采用
            if len(cells[2]) >= 4:
                password = cells[2]
        if not username:
            continue
        out.append({"username": username, "display_name": display or username, "password": password})
    return out

