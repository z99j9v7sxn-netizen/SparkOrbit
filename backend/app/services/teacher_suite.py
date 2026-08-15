"""教师端扩展套件：题库 / 成绩分析 / 待办 / 私信 / Agent 观测 / 资源审核 / 错题热点 / 日历 / 分组 / 激励 / 周报。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trace import AgentRun
from app.models.assignment import Assignment, AssignmentSubmission, AttendanceRecord
from app.models.galaxy import Galaxy, Planet
from app.models.generated_resource import GeneratedResource
from app.models.hallucination import HallucinationTicket
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.alert import Alert
from app.models.teacher_tools import (
    DirectMessage,
    PraiseRecord,
    QuestionBankItem,
    StudentGroup,
    TeacherCalendarEvent,
)
from app.models.user import User
from app.models.zone_extras import MistakeRecord
from app.services.notification_service import create_notification
from app.services.teacher import _class_ids_for_teacher, _students

_UTC = timezone.utc


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


async def _student_ids(session: AsyncSession, teacher: User, class_id: str = "") -> list[str]:
    return [s.id for s in await _students(session, teacher, class_id)]


# ---------------------------------------------------------------------------
# P0-1 题库管理
# ---------------------------------------------------------------------------


def _question_out(row: QuestionBankItem) -> dict:
    return {
        "id": row.id,
        "class_id": row.class_id,
        "stem": row.stem,
        "kind": row.kind,
        "options": list(row.options or []),
        "answer": row.answer,
        "explanation": row.explanation,
        "difficulty": row.difficulty,
        "galaxy_slug": row.galaxy_slug,
        "planet_slug": row.planet_slug,
        "tags": list(row.tags or []),
        "source": row.source,
        "created_at": _iso(row.created_at),
    }


async def list_questions(
    session: AsyncSession,
    teacher: User,
    *,
    galaxy_slug: str = "",
    difficulty: str = "",
    q: str = "",
    limit: int = 200,
) -> list[dict]:
    stmt = (
        select(QuestionBankItem)
        .where(QuestionBankItem.teacher_id == teacher.id)
        .order_by(QuestionBankItem.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if galaxy_slug:
        stmt = stmt.where(QuestionBankItem.galaxy_slug == galaxy_slug)
    if difficulty:
        stmt = stmt.where(QuestionBankItem.difficulty == difficulty)
    rows = (await session.execute(stmt)).scalars().all()
    if q:
        needle = q.strip().lower()
        rows = [r for r in rows if needle in (r.stem or "").lower() or needle in (r.answer or "").lower()]
    return [_question_out(r) for r in rows]


async def create_question(session: AsyncSession, teacher: User, data: dict) -> dict:
    row = QuestionBankItem(
        teacher_id=teacher.id,
        class_id=str(data.get("class_id") or ""),
        stem=str(data.get("stem") or "").strip(),
        kind=str(data.get("kind") or "choice"),
        options=[str(o) for o in (data.get("options") or [])],
        answer=str(data.get("answer") or ""),
        explanation=str(data.get("explanation") or ""),
        difficulty=str(data.get("difficulty") or "medium"),
        galaxy_slug=str(data.get("galaxy_slug") or ""),
        planet_slug=str(data.get("planet_slug") or ""),
        tags=[str(t) for t in (data.get("tags") or [])],
        source=str(data.get("source") or "manual"),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _question_out(row)


async def bulk_create_questions(
    session: AsyncSession,
    teacher: User,
    *,
    questions: list[dict],
    class_id: str = "",
    galaxy_slug: str = "",
    source: str = "ai",
) -> dict:
    created = 0
    for q in questions:
        stem = str(q.get("stem") or "").strip()
        if not stem:
            continue
        session.add(
            QuestionBankItem(
                teacher_id=teacher.id,
                class_id=class_id or str(q.get("class_id") or ""),
                stem=stem,
                kind=str(q.get("kind") or "choice"),
                options=[str(o) for o in (q.get("options") or [])],
                answer=str(q.get("answer") or ""),
                explanation=str(q.get("explanation") or ""),
                difficulty=str(q.get("difficulty") or "medium"),
                galaxy_slug=galaxy_slug or str(q.get("galaxy_slug") or ""),
                planet_slug=str(q.get("planet_slug") or ""),
                tags=[str(t) for t in (q.get("tags") or [])],
                source=source,
            )
        )
        created += 1
    await session.commit()
    return {"ok": True, "created": created}


async def update_question(session: AsyncSession, teacher: User, question_id: str, data: dict) -> dict:
    row = (
        await session.execute(
            select(QuestionBankItem).where(
                QuestionBankItem.id == question_id, QuestionBankItem.teacher_id == teacher.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("题目不存在")
    for field in ("stem", "kind", "answer", "explanation", "difficulty", "galaxy_slug", "planet_slug"):
        if data.get(field) is not None:
            setattr(row, field, str(data[field]))
    if data.get("options") is not None:
        row.options = [str(o) for o in data["options"]]
    if data.get("tags") is not None:
        row.tags = [str(t) for t in data["tags"]]
    await session.commit()
    await session.refresh(row)
    return _question_out(row)


async def delete_question(session: AsyncSession, teacher: User, question_id: str) -> dict:
    row = (
        await session.execute(
            select(QuestionBankItem).where(
                QuestionBankItem.id == question_id, QuestionBankItem.teacher_id == teacher.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("题目不存在")
    await session.delete(row)
    await session.commit()
    return {"ok": True, "id": question_id}


async def import_questions_from_assignment(
    session: AsyncSession, teacher: User, assignment_id: str, class_id: str = ""
) -> dict:
    assignment = (
        await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None or (assignment.teacher_id != teacher.id and teacher.role != "admin"):
        raise ValueError("作业不存在或无权访问")
    qs = list(assignment.questions_json or [])
    if not qs:
        raise ValueError("该作业没有结构化题目")
    normalized = [
        {
            "stem": q.get("stem") or "",
            "kind": q.get("kind") or "short",
            "options": q.get("options") or [],
            "answer": q.get("answer") or "",
            "galaxy_slug": assignment.galaxy_slug or "",
            "tags": [assignment.title] if assignment.title else [],
        }
        for q in qs
        if isinstance(q, dict)
    ]
    return await bulk_create_questions(
        session,
        teacher,
        questions=normalized,
        class_id=class_id or assignment.class_id,
        galaxy_slug=assignment.galaxy_slug or "",
        source="assignment",
    )


async def ai_generate_questions(
    teacher: User, *, topic: str, count: int = 5, difficulty: str = "medium"
) -> dict:
    """用 LLM 生成候选题目（不落库，前端确认后批量入库）。"""
    from app.services.llm import extract_json_list, llm_available, llm_chat

    if not llm_available():
        return {"ok": False, "questions": [], "message": "未配置 LLM，无法 AI 生成题目"}
    prompt = (
        f"你是一位资深教师，请围绕主题「{topic}」出 {count} 道{difficulty}难度的题目。"
        "以 JSON 返回：{\"questions\":[{\"stem\":题干,\"kind\":\"choice|short|judge\","
        "\"options\":[\"A. ...\",\"B. ...\"](选择题必填,其他为空数组),\"answer\":参考答案,"
        "\"explanation\":解析,\"tags\":[知识点标签]}]}。只返回 JSON。"
    )
    content = await llm_chat(
        [{"role": "user", "content": prompt}],
        temperature=0.7,
        response_json=True,
        timeout=90.0,
        user_id=teacher.id,
        endpoint="teacher_question_gen",
    )
    questions = extract_json_list(content or "") or []
    cleaned = []
    for q in questions:
        if not isinstance(q, dict) or not str(q.get("stem") or "").strip():
            continue
        cleaned.append(
            {
                "stem": str(q.get("stem") or "").strip(),
                "kind": str(q.get("kind") or "short"),
                "options": [str(o) for o in (q.get("options") or [])],
                "answer": str(q.get("answer") or ""),
                "explanation": str(q.get("explanation") or ""),
                "difficulty": difficulty,
                "tags": [str(t) for t in (q.get("tags") or [])],
            }
        )
    if not cleaned:
        return {"ok": False, "questions": [], "message": "AI 未返回可用题目，请调整主题重试"}
    return {"ok": True, "questions": cleaned, "message": f"AI 生成 {len(cleaned)} 道候选题"}


# ---------------------------------------------------------------------------
# P0-2 作业 / 成绩分析
# ---------------------------------------------------------------------------

_SCORE_BUCKETS = (("0-59", 0, 59), ("60-69", 60, 69), ("70-79", 70, 79), ("80-89", 80, 89), ("90-100", 90, 100))


async def assignment_analysis(session: AsyncSession, teacher: User, assignment_id: str) -> dict:
    assignment = (
        await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    ).scalar_one_or_none()
    if assignment is None or (assignment.teacher_id != teacher.id and teacher.role != "admin"):
        raise ValueError("作业不存在或无权访问")

    total_students = 0
    if assignment.class_id:
        total_students = int(
            (
                await session.execute(
                    select(func.count()).select_from(User).where(
                        User.role == "student", User.class_id == assignment.class_id
                    )
                )
            ).scalar_one()
            or 0
        )

    rows = (
        await session.execute(
            select(AssignmentSubmission, User)
            .join(User, User.id == AssignmentSubmission.student_id)
            .where(AssignmentSubmission.assignment_id == assignment_id)
            .order_by(AssignmentSubmission.submitted_at.asc())
        )
    ).all()

    submitted = [s for s, _ in rows if s.status in ("submitted", "graded")]
    graded = [(s, u) for s, u in rows if s.status == "graded" and s.score is not None]
    scores = [int(s.score or 0) for s, _ in graded]

    distribution = []
    for label, lo, hi in _SCORE_BUCKETS:
        distribution.append({"label": label, "count": sum(1 for sc in scores if lo <= sc <= hi)})

    students = [
        {
            "student_id": s.student_id,
            "student_name": u.display_name or u.username,
            "score": s.score,
            "status": s.status,
            "submitted_at": _iso(s.submitted_at),
        }
        for s, u in rows
    ]
    students.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))

    return {
        "assignment_id": assignment.id,
        "title": assignment.title,
        "class_id": assignment.class_id,
        "created_at": _iso(assignment.created_at),
        "due_at": _iso(assignment.due_at),
        "question_count": len(assignment.questions_json or []),
        "total_students": total_students,
        "submitted_count": len(submitted),
        "graded_count": len(graded),
        "missing_count": max(total_students - len(submitted), 0),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "max_score": max(scores) if scores else None,
        "min_score": min(scores) if scores else None,
        "pass_rate": round(sum(1 for sc in scores if sc >= 60) / len(scores) * 100) if scores else None,
        "distribution": distribution,
        "students": students,
    }


async def gradebook_trends(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    stmt = (
        select(Assignment)
        .where(Assignment.teacher_id == teacher.id)
        .order_by(Assignment.created_at.asc())
        .limit(30)
    )
    if class_id:
        stmt = stmt.where(Assignment.class_id == class_id)
    assignments = (await session.execute(stmt)).scalars().all()
    if not assignments:
        return {"trend": [], "progress": []}

    aid_list = [a.id for a in assignments]
    subs = (
        await session.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id.in_(aid_list),
                AssignmentSubmission.status == "graded",
            )
        )
    ).scalars().all()
    by_assignment: dict[str, list[AssignmentSubmission]] = {}
    for s in subs:
        by_assignment.setdefault(s.assignment_id, []).append(s)

    trend = []
    for a in assignments:
        graded = by_assignment.get(a.id, [])
        scores = [int(s.score or 0) for s in graded]
        trend.append(
            {
                "assignment_id": a.id,
                "title": a.title,
                "created_at": _iso(a.created_at),
                "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
                "graded_count": len(scores),
            }
        )

    # 学生进退步：按作业时间序，比较前半段与后半段均分
    order_index = {a.id: i for i, a in enumerate(assignments)}
    per_student: dict[str, list[tuple[int, int]]] = {}
    for s in subs:
        per_student.setdefault(s.student_id, []).append((order_index[s.assignment_id], int(s.score or 0)))

    student_ids = list(per_student.keys())
    name_map: dict[str, str] = {}
    if student_ids:
        users = (
            await session.execute(select(User).where(User.id.in_(student_ids)))
        ).scalars().all()
        name_map = {u.id: (u.display_name or u.username) for u in users}

    progress = []
    for sid, pairs in per_student.items():
        if len(pairs) < 2:
            continue
        pairs.sort(key=lambda x: x[0])
        half = len(pairs) // 2
        early = [sc for _, sc in pairs[:half]] or [pairs[0][1]]
        late = [sc for _, sc in pairs[half:]]
        delta = round(sum(late) / len(late) - sum(early) / len(early), 1)
        progress.append(
            {
                "student_id": sid,
                "student_name": name_map.get(sid, sid),
                "assignment_count": len(pairs),
                "recent_avg": round(sum(late) / len(late), 1),
                "delta": delta,
            }
        )
    progress.sort(key=lambda x: -x["delta"])
    return {"trend": trend, "progress": progress}


# ---------------------------------------------------------------------------
# P0-3 教师待办中心
# ---------------------------------------------------------------------------


async def teacher_todos(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    sids = await _student_ids(session, teacher, class_id)

    ungraded = int(
        (
            await session.execute(
                select(func.count())
                .select_from(AssignmentSubmission)
                .join(Assignment, Assignment.id == AssignmentSubmission.assignment_id)
                .where(Assignment.teacher_id == teacher.id, AssignmentSubmission.status == "submitted")
            )
        ).scalar_one()
        or 0
    )

    tickets = 0
    resource_pending = 0
    high_risk = 0
    if sids:
        tickets = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(HallucinationTicket)
                    .where(HallucinationTicket.student_id.in_(sids), HallucinationTicket.status == "pending")
                )
            ).scalar_one()
            or 0
        )
        resource_pending = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(GeneratedResource)
                    .where(GeneratedResource.user_id.in_(sids), GeneratedResource.review_status == "")
                )
            ).scalar_one()
            or 0
        )
        from app.services.teacher import student_risks

        risks = await student_risks(session, teacher, class_id)
        high_risk = sum(1 for r in risks if r.risk_level == "high")

    from app.services.improvement import list_pending_for_teacher

    improvement_pending = len(await list_pending_for_teacher(session, teacher))

    items = [
        {"key": "grading", "label": "待批改提交", "count": ungraded, "link": "/teacher/assignments"},
        {"key": "tickets", "label": "待人审判题工单", "count": tickets, "link": "/teacher/dashboard"},
        {"key": "improvement", "label": "画像改进待复核", "count": improvement_pending, "link": "/teacher/improvement"},
        {"key": "resources", "label": "学生资源待审核", "count": resource_pending, "link": "/teacher/resource-review"},
        {"key": "risk", "label": "高风险学生", "count": high_risk, "link": "/teacher/dashboard"},
    ]
    return {"items": items, "total": sum(i["count"] for i in items)}


# ---------------------------------------------------------------------------
# P0-4 一对一私信
# ---------------------------------------------------------------------------


async def send_direct_message(session: AsyncSession, teacher: User, student_id: str, body: str) -> dict:
    from app.services.teacher_extras import student_accessible

    if not await student_accessible(session, teacher, student_id):
        raise ValueError("学生不存在或不在您的班级中")
    row = DirectMessage(teacher_id=teacher.id, student_id=student_id, sender_role="teacher", body=body.strip())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await create_notification(
        session,
        student_id,
        f"{teacher.display_name or '老师'}的私信",
        body.strip(),
        kind="teacher_message",
        link="/student",
    )
    return {
        "id": row.id,
        "student_id": row.student_id,
        "body": row.body,
        "sender_role": row.sender_role,
        "created_at": _iso(row.created_at),
    }


async def list_direct_messages(
    session: AsyncSession, teacher: User, student_id: str, limit: int = 100
) -> list[dict]:
    rows = (
        await session.execute(
            select(DirectMessage)
            .where(DirectMessage.teacher_id == teacher.id, DirectMessage.student_id == student_id)
            .order_by(DirectMessage.created_at.asc())
            .limit(min(max(limit, 1), 300))
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "sender_role": r.sender_role,
            "body": r.body,
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


async def list_dm_conversations(session: AsyncSession, teacher: User, class_id: str = "") -> list[dict]:
    students = await _students(session, teacher, class_id)
    if not students:
        return []
    sids = [s.id for s in students]
    rows = (
        await session.execute(
            select(DirectMessage)
            .where(DirectMessage.teacher_id == teacher.id, DirectMessage.student_id.in_(sids))
            .order_by(DirectMessage.created_at.desc())
        )
    ).scalars().all()
    last_map: dict[str, DirectMessage] = {}
    count_map: Counter[str] = Counter()
    for r in rows:
        count_map[r.student_id] += 1
        if r.student_id not in last_map:
            last_map[r.student_id] = r
    out = []
    for s in students:
        last = last_map.get(s.id)
        out.append(
            {
                "student_id": s.id,
                "student_name": s.display_name or s.username,
                "username": s.username,
                "message_count": count_map.get(s.id, 0),
                "last_body": last.body if last else "",
                "last_at": _iso(last.created_at) if last else "",
            }
        )
    out.sort(key=lambda x: x["last_at"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# P1-5 班级 Agent 运行观测（教师版）
# ---------------------------------------------------------------------------


def _run_out(r: AgentRun) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "user_name": r.user_name,
        "scene": r.scene,
        "mode": r.mode,
        "status": r.status,
        "topic": r.topic,
        "graph_plan": r.graph_plan or {},
        "current_step": r.current_step,
        "current_agent": r.current_agent,
        "error_message": r.error_message,
        "created_at": _iso(r.created_at),
        "finished_at": _iso(r.finished_at),
        "steps": [],
    }


async def teacher_agent_runs(
    session: AsyncSession,
    teacher: User,
    *,
    class_id: str = "",
    limit: int = 80,
    scene: str = "",
    mode: str = "",
    status: str = "",
    user_id: str = "",
) -> list[dict]:
    sids = await _student_ids(session, teacher, class_id)
    if not sids:
        return []
    if user_id and user_id not in sids:
        return []
    stmt = (
        select(AgentRun)
        .where(AgentRun.user_id.in_([user_id] if user_id else sids))
        .order_by(AgentRun.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if scene:
        stmt = stmt.where(AgentRun.scene == scene)
    if mode:
        stmt = stmt.where(AgentRun.mode == mode)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_run_out(r) for r in rows]


async def teacher_agent_run_detail(session: AsyncSession, teacher: User, run_id: str) -> dict | None:
    from app.services.agent_trace import get_agent_run_detail

    detail = await get_agent_run_detail(session, run_id)
    if detail is None:
        return None
    sids = set(await _student_ids(session, teacher))
    if detail.get("user_id") not in sids:
        return None
    return detail


# ---------------------------------------------------------------------------
# P1-6 学生生成资源审核与推荐
# ---------------------------------------------------------------------------


async def list_student_generated_resources(
    session: AsyncSession, teacher: User, *, class_id: str = "", status: str = "", limit: int = 100
) -> list[dict]:
    students = await _students(session, teacher, class_id)
    if not students:
        return []
    name_map = {s.id: (s.display_name or s.username) for s in students}
    stmt = (
        select(GeneratedResource)
        .where(GeneratedResource.user_id.in_(list(name_map.keys())))
        .order_by(GeneratedResource.created_at.desc())
        .limit(min(max(limit, 1), 300))
    )
    if status == "pending":
        stmt = stmt.where(GeneratedResource.review_status == "")
    elif status:
        stmt = stmt.where(GeneratedResource.review_status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "student_id": r.user_id,
            "student_name": name_map.get(r.user_id, r.user_id),
            "kind": r.kind,
            "title": r.title,
            "planet_slug": r.planet_slug,
            "planet_name": r.planet_name,
            "content_preview": (r.content or "")[:400],
            "content": r.content or "",
            "review_status": r.review_status or "",
            "review_comment": r.review_comment or "",
            "created_at": _iso(r.created_at),
        }
        for r in rows
    ]


async def review_generated_resource(
    session: AsyncSession, teacher: User, resource_id: str, *, status: str, comment: str = ""
) -> dict:
    row = await session.get(GeneratedResource, resource_id)
    if row is None:
        raise ValueError("资源不存在")
    sids = set(await _student_ids(session, teacher))
    if row.user_id not in sids:
        raise ValueError("该资源的作者不在您的班级中")
    row.review_status = status
    row.review_comment = comment.strip()
    row.reviewed_by = teacher.id
    row.reviewed_at = datetime.now(_UTC)
    await session.commit()
    return {"ok": True, "id": resource_id, "review_status": status}


async def recommend_generated_resource(
    session: AsyncSession, teacher: User, resource_id: str, *, class_id: str = "", galaxy_slug: str = ""
) -> dict:
    """将学生优质产物以教师名义收录进资料库并升格班级星库。"""
    from app.services.note_service import create_lesson_resource_from_text, promote_lesson_resource_to_starlib

    row = await session.get(GeneratedResource, resource_id)
    if row is None:
        raise ValueError("资源不存在")
    sids = set(await _student_ids(session, teacher))
    if row.user_id not in sids:
        raise ValueError("该资源的作者不在您的班级中")

    kind_map = {"deck": "deck", "quiz": "quiz", "doc": "plan", "mindmap": "other", "reading": "other"}
    lesson = await create_lesson_resource_from_text(
        session,
        teacher,
        title=row.title or f"{row.kind} · {row.planet_name}",
        content=row.content or "",
        galaxy_slug=galaxy_slug or "",
        class_id=class_id,
        resource_kind=kind_map.get(row.kind, "other"),
    )
    result = await promote_lesson_resource_to_starlib(
        session,
        teacher,
        lesson["id"],
        class_id=class_id,
        galaxy_slug=galaxy_slug or "",
        planet_slug=row.planet_slug or "",
    )
    row.review_status = "recommended"
    row.reviewed_by = teacher.id
    row.reviewed_at = datetime.now(_UTC)
    await session.commit()
    return {"ok": True, "id": resource_id, "starlib": result}


# ---------------------------------------------------------------------------
# P1-7 班级错题热点
# ---------------------------------------------------------------------------


async def mistake_hotspots(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    sids = await _student_ids(session, teacher, class_id)
    if not sids:
        return {"hotspots": [], "subjects": [], "recent_mistakes": []}

    planets = (await session.execute(select(Planet))).scalars().all()
    planet_map = {p.id: p for p in planets}
    galaxy_map = {g.id: g for g in (await session.execute(select(Galaxy))).scalars().all()}

    challenges = (
        await session.execute(
            select(ChallengeQuestion).where(
                ChallengeQuestion.user_id.in_(sids), ChallengeQuestion.answered.is_(True)
            )
        )
    ).scalars().all()
    attempts: Counter[str] = Counter()
    wrongs: Counter[str] = Counter()
    wrong_students: dict[str, set[str]] = {}
    for c in challenges:
        attempts[c.planet_id] += 1
        if not c.correct:
            wrongs[c.planet_id] += 1
            wrong_students.setdefault(c.planet_id, set()).add(c.user_id)

    tag_map: dict[str, Counter[str]] = {}
    mastery_rows = (
        await session.execute(select(PlanetMastery).where(PlanetMastery.user_id.in_(sids)))
    ).scalars().all()
    for m in mastery_rows:
        for tag in m.last_wrong_tags or []:
            tag_map.setdefault(m.planet_id, Counter())[str(tag)] += 1

    hotspots = []
    for pid, wrong_count in wrongs.most_common(12):
        p = planet_map.get(pid)
        if p is None:
            continue
        g = galaxy_map.get(p.galaxy_id)
        total = attempts.get(pid, 0)
        hotspots.append(
            {
                "planet_id": pid,
                "planet_slug": p.slug,
                "planet_name": p.name,
                "galaxy_name": g.name if g else "",
                "wrong_count": wrong_count,
                "attempts": total,
                "wrong_rate": round(wrong_count / total * 100) if total else 0,
                "affected_students": len(wrong_students.get(pid, set())),
                "top_tags": [t for t, _ in (tag_map.get(pid, Counter())).most_common(4)],
            }
        )

    mistakes = (
        await session.execute(
            select(MistakeRecord, User)
            .join(User, User.id == MistakeRecord.user_id)
            .where(MistakeRecord.user_id.in_(sids))
            .order_by(MistakeRecord.created_at.desc())
            .limit(15)
        )
    ).all()
    subject_counter: Counter[str] = Counter()
    all_mistakes = (
        await session.execute(select(MistakeRecord.subject).where(MistakeRecord.user_id.in_(sids)))
    ).scalars().all()
    for subj in all_mistakes:
        subject_counter[subj or "未分类"] += 1

    return {
        "hotspots": hotspots,
        "subjects": [{"subject": s, "count": c} for s, c in subject_counter.most_common(8)],
        "recent_mistakes": [
            {
                "id": m.id,
                "student_name": u.display_name or u.username,
                "question": (m.question or "")[:120],
                "subject": m.subject or "",
                "created_at": _iso(m.created_at),
            }
            for m, u in mistakes
        ],
    }


async def dispatch_hotspot_review(
    session: AsyncSession, teacher: User, *, class_id: str, planet_slug: str, message: str
) -> dict:
    sids = await _student_ids(session, teacher, class_id)
    if not sids:
        raise ValueError("班级暂无学生")
    planet = (
        await session.execute(select(Planet).where(Planet.slug == planet_slug))
    ).scalar_one_or_none()
    if planet is None:
        raise ValueError("行星不存在")
    wrong_sids = (
        await session.execute(
            select(ChallengeQuestion.user_id)
            .where(
                ChallengeQuestion.user_id.in_(sids),
                ChallengeQuestion.planet_id == planet.id,
                ChallengeQuestion.answered.is_(True),
                ChallengeQuestion.correct.is_(False),
            )
            .distinct()
        )
    ).scalars().all()
    if not wrong_sids:
        return {"ok": True, "dispatched": 0, "message": "该行星暂无答错学生"}
    for sid in wrong_sids:
        session.add(
            Alert(
                user_id=teacher.id,
                student_id=sid,
                alert_type="review_task",
                alert_level="medium",
                message=f"[planet:{planet_slug}] 目标行星：{planet.name}。{message}",
            )
        )
    await session.commit()
    return {"ok": True, "dispatched": len(wrong_sids), "message": f"已向 {len(wrong_sids)} 名答错学生派发复习任务"}


# ---------------------------------------------------------------------------
# P2-8 教学日历
# ---------------------------------------------------------------------------


def _event_out(row: TeacherCalendarEvent) -> dict:
    return {
        "id": row.id,
        "class_id": row.class_id,
        "title": row.title,
        "event_date": row.event_date,
        "kind": row.kind,
        "note": row.note,
    }


async def calendar_month(session: AsyncSession, teacher: User, *, class_id: str = "", month: str = "") -> dict:
    """month: YYYY-MM；合并自定义事件与作业截止。"""
    if not month:
        month = datetime.now(_UTC).strftime("%Y-%m")
    prefix = month + "-"

    stmt = select(TeacherCalendarEvent).where(
        TeacherCalendarEvent.teacher_id == teacher.id,
        TeacherCalendarEvent.event_date.like(prefix + "%"),
    )
    if class_id:
        stmt = stmt.where(TeacherCalendarEvent.class_id.in_(["", class_id]))
    events = [(_event_out(r)) for r in (await session.execute(stmt)).scalars().all()]

    astmt = select(Assignment).where(Assignment.teacher_id == teacher.id, Assignment.due_at.isnot(None))
    if class_id:
        astmt = astmt.where(Assignment.class_id == class_id)
    for a in (await session.execute(astmt)).scalars().all():
        due = a.due_at.strftime("%Y-%m-%d") if a.due_at else ""
        if due.startswith(prefix):
            events.append(
                {
                    "id": f"assignment-{a.id}",
                    "class_id": a.class_id,
                    "title": f"作业截止：{a.title}",
                    "event_date": due,
                    "kind": "assignment",
                    "note": "",
                }
            )
    events.sort(key=lambda e: e["event_date"])
    return {"month": month, "events": events}


async def create_calendar_event(session: AsyncSession, teacher: User, data: dict) -> dict:
    row = TeacherCalendarEvent(
        teacher_id=teacher.id,
        class_id=str(data.get("class_id") or ""),
        title=str(data.get("title") or "").strip(),
        event_date=str(data.get("event_date") or ""),
        kind=str(data.get("kind") or "custom"),
        note=str(data.get("note") or ""),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _event_out(row)


async def delete_calendar_event(session: AsyncSession, teacher: User, event_id: str) -> dict:
    row = (
        await session.execute(
            select(TeacherCalendarEvent).where(
                TeacherCalendarEvent.id == event_id, TeacherCalendarEvent.teacher_id == teacher.id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("事件不存在")
    await session.delete(row)
    await session.commit()
    return {"ok": True, "id": event_id}


# ---------------------------------------------------------------------------
# P2-9 学生分组
# ---------------------------------------------------------------------------


async def _group_out(session: AsyncSession, row: StudentGroup) -> dict:
    member_ids = [str(m) for m in (row.member_ids or [])]
    members = []
    if member_ids:
        users = (await session.execute(select(User).where(User.id.in_(member_ids)))).scalars().all()
        members = [{"id": u.id, "name": u.display_name or u.username} for u in users]
    return {
        "id": row.id,
        "class_id": row.class_id,
        "name": row.name,
        "note": row.note,
        "member_ids": member_ids,
        "members": members,
        "created_at": _iso(row.created_at),
    }


async def list_groups(session: AsyncSession, teacher: User, class_id: str = "") -> list[dict]:
    stmt = select(StudentGroup).where(StudentGroup.teacher_id == teacher.id).order_by(StudentGroup.created_at.asc())
    if class_id:
        stmt = stmt.where(StudentGroup.class_id == class_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [await _group_out(session, r) for r in rows]


async def create_group(session: AsyncSession, teacher: User, data: dict) -> dict:
    allowed = set(await _student_ids(session, teacher, str(data.get("class_id") or "")))
    member_ids = [m for m in (data.get("member_ids") or []) if m in allowed]
    row = StudentGroup(
        teacher_id=teacher.id,
        class_id=str(data.get("class_id") or ""),
        name=str(data.get("name") or "").strip(),
        member_ids=member_ids,
        note=str(data.get("note") or ""),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return await _group_out(session, row)


async def update_group(session: AsyncSession, teacher: User, group_id: str, data: dict) -> dict:
    row = (
        await session.execute(
            select(StudentGroup).where(StudentGroup.id == group_id, StudentGroup.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("分组不存在")
    if data.get("name") is not None:
        row.name = str(data["name"]).strip()
    if data.get("note") is not None:
        row.note = str(data["note"])
    if data.get("member_ids") is not None:
        allowed = set(await _student_ids(session, teacher, row.class_id))
        row.member_ids = [m for m in data["member_ids"] if m in allowed]
    await session.commit()
    await session.refresh(row)
    return await _group_out(session, row)


async def delete_group(session: AsyncSession, teacher: User, group_id: str) -> dict:
    row = (
        await session.execute(
            select(StudentGroup).where(StudentGroup.id == group_id, StudentGroup.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("分组不存在")
    await session.delete(row)
    await session.commit()
    return {"ok": True, "id": group_id}


async def dispatch_to_group(
    session: AsyncSession, teacher: User, group_id: str, *, message: str, planet_slug: str = ""
) -> dict:
    row = (
        await session.execute(
            select(StudentGroup).where(StudentGroup.id == group_id, StudentGroup.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("分组不存在")
    member_ids = [str(m) for m in (row.member_ids or [])]
    if not member_ids:
        return {"ok": True, "dispatched": 0, "message": "该分组暂无成员"}
    planet_hint = ""
    if planet_slug:
        planet = (
            await session.execute(select(Planet).where(Planet.slug == planet_slug))
        ).scalar_one_or_none()
        if planet:
            planet_hint = f"[planet:{planet_slug}] 目标行星：{planet.name}。"
    for sid in member_ids:
        session.add(
            Alert(
                user_id=teacher.id,
                student_id=sid,
                alert_type="review_task",
                alert_level="medium",
                message=f"{planet_hint}{message}",
            )
        )
    await session.commit()
    return {"ok": True, "dispatched": len(member_ids), "message": f"已向小组 {row.name} 的 {len(member_ids)} 名成员派发任务"}


# ---------------------------------------------------------------------------
# P2-10 激励系统
# ---------------------------------------------------------------------------


async def create_praise(session: AsyncSession, teacher: User, data: dict) -> dict:
    student_id = str(data.get("student_id") or "")
    from app.services.teacher_extras import student_accessible

    if not await student_accessible(session, teacher, student_id, str(data.get("class_id") or "")):
        raise ValueError("学生不存在或不在您的班级中")
    row = PraiseRecord(
        teacher_id=teacher.id,
        student_id=student_id,
        class_id=str(data.get("class_id") or ""),
        badge=str(data.get("badge") or ""),
        points=int(data.get("points") or 0),
        message=str(data.get("message") or ""),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    body = f"获得「{row.badge}」徽章 +{row.points} 星光"
    if row.message:
        body += f"：{row.message}"
    await create_notification(
        session,
        student_id,
        f"{teacher.display_name or '老师'}的表扬",
        body,
        kind="teacher_praise",
        link="/student",
    )
    return {"ok": True, "id": row.id}


async def praise_overview(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    students = await _students(session, teacher, class_id)
    if not students:
        return {"records": [], "leaderboard": []}
    name_map = {s.id: (s.display_name or s.username) for s in students}
    rows = (
        await session.execute(
            select(PraiseRecord)
            .where(PraiseRecord.teacher_id == teacher.id, PraiseRecord.student_id.in_(list(name_map.keys())))
            .order_by(PraiseRecord.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    points: Counter[str] = Counter()
    badges: dict[str, Counter[str]] = {}
    for r in rows:
        points[r.student_id] += r.points
        badges.setdefault(r.student_id, Counter())[r.badge] += 1
    leaderboard = [
        {
            "student_id": sid,
            "student_name": name_map.get(sid, sid),
            "total_points": pts,
            "badge_count": sum(badges.get(sid, Counter()).values()),
            "top_badge": (badges.get(sid, Counter()).most_common(1) or [("", 0)])[0][0],
        }
        for sid, pts in points.most_common(20)
    ]
    return {
        "records": [
            {
                "id": r.id,
                "student_id": r.student_id,
                "student_name": name_map.get(r.student_id, r.student_id),
                "badge": r.badge,
                "points": r.points,
                "message": r.message,
                "created_at": _iso(r.created_at),
            }
            for r in rows
        ],
        "leaderboard": leaderboard,
    }


# ---------------------------------------------------------------------------
# P2-11 教学周报
# ---------------------------------------------------------------------------


async def weekly_report(session: AsyncSession, teacher: User, class_id: str = "") -> dict:
    from app.services.teacher import student_risks
    from app.services.teacher_extras import insight_overview

    now = datetime.now(_UTC)
    week_ago = now - timedelta(days=7)
    overview = await insight_overview(session, teacher, class_id)
    risks = await student_risks(session, teacher, class_id)
    high_risks = [r for r in risks if r.risk_level == "high"]

    astmt = select(Assignment).where(Assignment.teacher_id == teacher.id, Assignment.created_at >= week_ago)
    if class_id:
        astmt = astmt.where(Assignment.class_id == class_id)
    assignments = (await session.execute(astmt)).scalars().all()

    assignment_lines = []
    for a in assignments:
        subs = (
            await session.execute(
                select(AssignmentSubmission).where(
                    AssignmentSubmission.assignment_id == a.id,
                    AssignmentSubmission.status == "graded",
                )
            )
        ).scalars().all()
        scores = [int(s.score or 0) for s in subs]
        avg = round(sum(scores) / len(scores), 1) if scores else None
        assignment_lines.append(f"- {a.title}：已批改 {len(scores)} 份" + (f"，均分 {avg}" if avg is not None else ""))

    sids = await _student_ids(session, teacher, class_id)
    attendance_summary = ""
    if sids:
        week_start = (now - timedelta(days=7)).date().isoformat()
        att_rows = (
            await session.execute(
                select(AttendanceRecord.status, func.count())
                .where(AttendanceRecord.student_id.in_(sids), AttendanceRecord.record_date >= week_start)
                .group_by(AttendanceRecord.status)
            )
        ).all()
        if att_rows:
            attendance_summary = "、".join(f"{status} {count} 人次" for status, count in att_rows)

    praise_count = 0
    if sids:
        praise_count = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(PraiseRecord)
                    .where(PraiseRecord.student_id.in_(sids), PraiseRecord.created_at >= week_ago)
                )
            ).scalar_one()
            or 0
        )

    period = f"{week_ago.date().isoformat()} ~ {now.date().isoformat()}"
    lines = [
        f"# 班级教学周报（{period}）",
        "",
        "## 班级概况",
        f"- 学生人数：{overview['total_students']}",
        f"- 平均掌握率：{overview['avg_mastery_rate']}%",
        f"- 平均答题正确率：{overview['avg_quiz_accuracy']}%",
        f"- 近 7 日活跃学生：{overview['active_students_7d']} 人",
        f"- 学习证据总量：{overview['total_evidence']} 条",
        "",
        "## 本周作业",
    ]
    lines.extend(assignment_lines or ["- 本周未发布新作业"])
    lines.extend(["", "## 考勤概况", f"- {attendance_summary or '本周暂无考勤记录'}"])
    lines.extend(["", "## 风险关注"])
    if high_risks:
        for r in high_risks[:8]:
            lines.append(f"- {r.display_name}：掌握率 {r.mastery_rate}%，近期错误 {r.recent_wrong} 次")
    else:
        lines.append("- 本周无高风险学生")
    lines.extend(["", "## 激励发放", f"- 本周共发放表扬/徽章 {praise_count} 次"])
    lines.extend(["", "---", f"报告生成时间：{now.strftime('%Y-%m-%d %H:%M')} UTC"])

    return {
        "period": period,
        "markdown": "\n".join(lines),
        "generated_at": now.isoformat(),
        "stats": {
            "total_students": overview["total_students"],
            "avg_mastery_rate": overview["avg_mastery_rate"],
            "assignments_this_week": len(assignments),
            "high_risk_count": len(high_risks),
            "praise_count": praise_count,
        },
    }
