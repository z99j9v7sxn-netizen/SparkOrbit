"""模拟面试区 API。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_current_user, require_teacher
from app.schemas.interview import (
    InterviewApplicationIn,
    InterviewApplicationOut,
    InterviewApplicationPatch,
    InterviewJobRoleOut,
    InterviewOverviewOut,
    InterviewPortraitOut,
    InterviewPracticeAnswerIn,
    InterviewPracticeAnswerOut,
    InterviewPracticeQuestionOut,
    InterviewPracticeRecordOut,
    InterviewReportOut,
    InterviewResumeCoachIn,
    InterviewResumeDocxIn,
    InterviewResumeMatchOut,
    InterviewResumeOptimizeOut,
    InterviewResumeOut,
    InterviewSessionBriefOut,
    InterviewSessionDetailOut,
    InterviewStartIn,
    InterviewTaskOut,
    InterviewTeacherReviewIn,
)
from app.services.interview_catalog import get_role, list_job_roles
from app.services.interview_practice import (
    generate_practice_question,
    list_practice_history,
    score_practice_answer,
)
from app.services.interview_resume import (
    match_resume,
    optimize_resume,
    save_and_parse_resume,
)
from app.services.interview_runtime import get_prep, iter_prep_events, register_prep
from app.services.interview_service import (
    create_session,
    delete_owned_session,
    get_interview_portrait,
    get_owned_session,
    list_sessions,
    list_student_interview_tasks,
    list_teacher_sessions,
    review_report,
    serialize_report,
    serialize_session_brief,
    serialize_session_detail,
    serialize_teacher_session_brief,
    teacher_can_see,
    teacher_overview,
)
from app.services.resource_agents import format_resource_sse

router = APIRouter(tags=["mock-interview"])


@router.get("/interview/job-roles", response_model=list[InterviewJobRoleOut])
async def interview_job_roles(
    scenario: str = "",
    current_user=Depends(require_current_user),
) -> list[InterviewJobRoleOut]:
    _ = current_user
    return [InterviewJobRoleOut(**item) for item in list_job_roles(scenario)]


@router.post("/interview/resume", response_model=InterviewResumeOut)
async def interview_resume_upload(
    file: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> InterviewResumeOut:
    try:
        result = await save_and_parse_resume(file, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return InterviewResumeOut(url=result["url"], profile=result["profile"], text_preview=result["text_preview"])


@router.get("/interview/career/portals")
async def interview_career_portals(
    group: str = "",
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    from app.data.career_portals import list_portals, list_windows

    return {"portals": list_portals(group), "windows": list_windows()}


@router.get("/interview/career/templates")
async def interview_career_templates(current_user=Depends(require_current_user)) -> dict:
    _ = current_user
    from app.data.career_templates import list_resume_templates

    return list_resume_templates()


@router.get("/interview/career/questions")
async def interview_career_questions(
    company: str = "",
    job_role: str = "",
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    from app.data.career_questions import list_career_questions, list_question_companies

    return {
        "companies": list_question_companies(),
        "questions": list_career_questions(company=company, job_role=job_role),
    }


@router.post("/interview/resume/optimize", response_model=InterviewResumeOptimizeOut)
async def interview_resume_optimize(
    payload: InterviewResumeCoachIn,
    current_user=Depends(require_current_user),
) -> InterviewResumeOptimizeOut:
    data = await optimize_resume(
        text=payload.text,
        profile=payload.profile,
        target_role=payload.target_role,
        jd=payload.jd,
        user_id=current_user.id,
    )
    return InterviewResumeOptimizeOut(**data)


@router.post("/interview/resume/match", response_model=InterviewResumeMatchOut)
async def interview_resume_match(
    payload: InterviewResumeCoachIn,
    current_user=Depends(require_current_user),
) -> InterviewResumeMatchOut:
    data = await match_resume(
        text=payload.text,
        profile=payload.profile,
        target_role=payload.target_role,
        jd=payload.jd,
        user_id=current_user.id,
    )
    return InterviewResumeMatchOut(**data)


@router.post("/interview/resume/export")
@router.post("/interview/resume/docx")
async def interview_resume_export(
    payload: InterviewResumeDocxIn,
    current_user=Depends(require_current_user),
) -> Response:
    _ = current_user
    from app.data.career_templates import get_resume_template
    from app.services.resume_export import export_resume

    if get_resume_template(payload.template_id) is None:
        raise HTTPException(status_code=422, detail="未知简历模板")
    blob, media, filename = export_resume(payload.fields or {}, payload.template_id, payload.format)
    return Response(
        content=blob,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/interview/applications", response_model=list[InterviewApplicationOut])
async def interview_list_applications(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewApplicationOut]:
    from app.services.interview_applications import list_applications, serialize_application

    rows = await list_applications(db, current_user.id)
    return [InterviewApplicationOut(**serialize_application(r)) for r in rows]


@router.post("/interview/applications", response_model=InterviewApplicationOut)
async def interview_create_application(
    payload: InterviewApplicationIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewApplicationOut:
    from app.services.interview_applications import create_application, serialize_application

    if not (payload.company or "").strip():
        raise HTTPException(status_code=422, detail="请填写公司名称")
    row = await create_application(db, current_user.id, payload.model_dump())
    return InterviewApplicationOut(**serialize_application(row))


@router.patch("/interview/applications/{app_id}", response_model=InterviewApplicationOut)
async def interview_patch_application(
    app_id: str,
    payload: InterviewApplicationPatch,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewApplicationOut:
    from app.services.interview_applications import serialize_application, update_application

    data = payload.model_dump(exclude_unset=True)
    row = await update_application(db, current_user.id, app_id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return InterviewApplicationOut(**serialize_application(row))


@router.delete("/interview/applications/{app_id}")
async def interview_delete_application(
    app_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.interview_applications import delete_application

    ok = await delete_application(db, current_user.id, app_id)
    if not ok:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return {"ok": True}


@router.post("/interview/sessions", response_model=InterviewSessionBriefOut)
async def interview_create_session(
    payload: InterviewStartIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionBriefOut:
    if get_role(payload.job_role) is None:
        raise HTTPException(status_code=422, detail="未知岗位/场景模板")
    row = await create_session(
        db,
        current_user,
        {
            "scenario": payload.scenario,
            "job_role": payload.job_role,
            "difficulty": payload.difficulty,
            "question_count": payload.question_count,
            "resume_url": payload.resume_url,
            "resume_profile": payload.resume_profile,
            "assignment_id": payload.assignment_id,
            "consent": payload.consent,
        },
    )
    return InterviewSessionBriefOut(**serialize_session_brief(row))


@router.get("/interview/sessions", response_model=list[InterviewSessionBriefOut])
async def interview_list_sessions(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewSessionBriefOut]:
    rows = await list_sessions(db, current_user.id)
    return [InterviewSessionBriefOut(**serialize_session_brief(r)) for r in rows]


@router.get("/interview/sessions/{session_id}", response_model=InterviewSessionDetailOut)
async def interview_session_detail(
    session_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionDetailOut:
    row = await get_owned_session(db, current_user.id, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    data = await serialize_session_detail(db, row)
    return InterviewSessionDetailOut(**data)


@router.get("/interview/sessions/{session_id}/prep/stream")
async def interview_prep_stream(
    session_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await get_owned_session(db, current_user.id, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if get_prep(session_id) is None and row.status == "preparing":
        register_prep(session_id, current_user.id)
        from app.services.interview_agents import run_interview_prep

        asyncio.create_task(run_interview_prep(session_id))

    async def event_stream():
        if row.status in {"ready", "running", "completed"}:
            yield format_resource_sse(
                {
                    "role": "Coordinator",
                    "type": "done",
                    "content": "题目已就绪",
                    "payload": {"status": row.status, "questions": row.questions or []},
                }
            )
            return
        async for event in iter_prep_events(session_id):
            yield format_resource_sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/interview/reports/{report_id}", response_model=InterviewReportOut)
async def interview_report_detail(
    report_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewReportOut:
    from app.models.mock_interview import InterviewReport

    report = await db.get(InterviewReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    session = await get_owned_session(db, current_user.id, report.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return InterviewReportOut(**serialize_report(report, session.scenario))


@router.get("/interview/portrait", response_model=InterviewPortraitOut)
async def interview_portrait(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewPortraitOut:
    data = await get_interview_portrait(db, current_user.id)
    return InterviewPortraitOut(**data)


@router.get("/interview/practice/question", response_model=InterviewPracticeQuestionOut)
async def interview_practice_question(
    scenario: str = "job",
    job_role: str = "backend",
    kind: str = "",
    current_user=Depends(require_current_user),
) -> InterviewPracticeQuestionOut:
    if scenario not in {"job", "academic"}:
        scenario = "job"
    if get_role(job_role) is None:
        raise HTTPException(status_code=422, detail="未知岗位/场景模板")
    data = await generate_practice_question(
        scenario=scenario, job_role=job_role, kind=kind, user_id=current_user.id
    )
    return InterviewPracticeQuestionOut(**data)


@router.post("/interview/practice/answer", response_model=InterviewPracticeAnswerOut)
async def interview_practice_answer(
    payload: InterviewPracticeAnswerIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewPracticeAnswerOut:
    scenario = payload.scenario if payload.scenario in {"job", "academic"} else "job"
    data = await score_practice_answer(
        db,
        user_id=current_user.id,
        scenario=scenario,
        job_role=payload.job_role,
        kind=payload.kind,
        question=payload.question,
        transcript=payload.transcript,
    )
    return InterviewPracticeAnswerOut(**data)


@router.get("/interview/practice/history", response_model=list[InterviewPracticeRecordOut])
async def interview_practice_history(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewPracticeRecordOut]:
    rows = await list_practice_history(db, current_user.id)
    return [InterviewPracticeRecordOut(**item) for item in rows]


@router.get("/interview/tasks", response_model=list[InterviewTaskOut])
async def interview_student_tasks(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewTaskOut]:
    rows = await list_student_interview_tasks(db, current_user)
    return [InterviewTaskOut(**item) for item in rows]


@router.delete("/interview/sessions/{session_id}")
async def interview_delete_session(
    session_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await delete_owned_session(db, current_user.id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    return {"ok": True}


@router.get("/teacher/interview/overview", response_model=InterviewOverviewOut)
async def teacher_interview_overview(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> InterviewOverviewOut:
    return InterviewOverviewOut(**await teacher_overview(db, current_user))


@router.get("/teacher/interview/sessions", response_model=list[InterviewSessionBriefOut])
async def teacher_interview_sessions(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewSessionBriefOut]:
    rows = await list_teacher_sessions(db, current_user)
    out = []
    for row in rows:
        out.append(InterviewSessionBriefOut(**await serialize_teacher_session_brief(db, row)))
    return out


@router.get("/teacher/interview/sessions/{session_id}", response_model=InterviewSessionDetailOut)
async def teacher_interview_session_detail(
    session_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionDetailOut:
    from app.models.mock_interview import InterviewSession

    row = await db.get(InterviewSession, session_id)
    if row is None or not await teacher_can_see(db, current_user, row):
        raise HTTPException(status_code=404, detail="面试会话不存在")
    data = await serialize_session_detail(db, row)
    extra = await serialize_teacher_session_brief(db, row)
    data["student_name"] = extra.get("student_name") or ""
    data["review_status"] = extra.get("review_status") or ""
    return InterviewSessionDetailOut(**data)


@router.post("/teacher/interview/reports/{report_id}/review", response_model=InterviewReportOut)
async def teacher_interview_review(
    report_id: str,
    payload: InterviewTeacherReviewIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> InterviewReportOut:
    from app.models.mock_interview import InterviewSession

    report = await review_report(
        db,
        current_user,
        report_id,
        comment=payload.comment,
        score=payload.score,
        status=payload.status,
    )
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    session = await db.get(InterviewSession, report.session_id)
    return InterviewReportOut(**serialize_report(report, session.scenario if session else "job"))

