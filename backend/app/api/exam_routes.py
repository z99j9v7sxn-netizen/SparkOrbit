"""考级中心 API：题库 / 专项刷题 / 模考 / 词书 / 精听 / 写译批改 / 21 天挑战。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_current_user, require_teacher_or_admin
from app.models.exam import EXAM_TYPES, ExamMockRun
from app.services import exam_center as exam_svc

router = APIRouter(tags=["exam-center"])


class GenerateIn(BaseModel):
    exam_type: str = Field(min_length=1, max_length=24)
    section: str = Field(min_length=1, max_length=24)
    count: int = Field(default=5, ge=1, le=10)


class PracticeCheckIn(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(default="", max_length=4000)
    archive_wrong: bool = True


class PracticeLogIn(BaseModel):
    exam_type: str = Field(default="", max_length=24)
    section: str = Field(default="", max_length=24)
    activity: str = Field(default="practice", max_length=24)
    total: int = Field(default=0, ge=0, le=500)
    correct: int = Field(default=0, ge=0, le=500)
    meta: dict = Field(default_factory=dict)


class MockStartIn(BaseModel):
    exam_type: str = Field(min_length=1, max_length=24)


class MockSubmitIn(BaseModel):
    run_id: str = Field(min_length=1, max_length=64)
    answers: dict[str, str] = Field(default_factory=dict)


class WordSeedIn(BaseModel):
    exam_type: str = Field(min_length=1, max_length=24)
    count: int = Field(default=30, ge=10, le=40)


class EssayGradeIn(BaseModel):
    exam_type: str = Field(min_length=1, max_length=24)
    kind: str = Field(default="writing", max_length=16)  # writing | translation
    prompt: str = Field(default="", max_length=2000)
    text: str = Field(min_length=1, max_length=6000)


class ListeningIn(BaseModel):
    exam_type: str = Field(min_length=1, max_length=24)
    topic: str = Field(default="", max_length=200)


class ChallengeJoinIn(BaseModel):
    exam_type: str = Field(default="cet4", max_length=24)


def _check_exam_type(exam_type: str) -> str:
    if exam_type not in EXAM_TYPES:
        raise HTTPException(status_code=422, detail=f"不支持的考试类型：{exam_type}")
    return exam_type


@router.get("/exam/meta")
async def exam_meta(current_user=Depends(require_current_user)) -> dict:
    _ = current_user
    return {
        "exam_types": [{"key": k, "label": v} for k, v in exam_svc.EXAM_LABELS.items()],
        "sections": [{"key": k, "label": v} for k, v in exam_svc.SECTION_LABELS.items()],
        "mock_structure": [{"section": s, "count": c} for s, c in exam_svc.MOCK_STRUCTURE],
    }


@router.get("/exam/bank/summary")
async def exam_bank_summary(
    exam_type: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = current_user
    return await exam_svc.bank_summary(db, _check_exam_type(exam_type))


@router.post("/exam/generate")
async def exam_generate(
    request: GenerateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_exam_type(request.exam_type)
    if request.section not in exam_svc.SECTION_LABELS:
        raise HTTPException(status_code=422, detail="不支持的题型")
    try:
        rows = await exam_svc.generate_questions(
            db, request.exam_type, request.section, request.count, created_by=current_user.id
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "created": len(rows)}


@router.post("/exam/import")
async def exam_import(
    exam_type: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.archive_service import extract_document_text

    _check_exam_type(exam_type)
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 15 MB")
    try:
        text = extract_document_text(str(file.filename or ""), data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        rows = await exam_svc.import_questions_from_text(
            db, exam_type, text, created_by=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "imported": len(rows)}


@router.get("/exam/practice")
async def exam_practice(
    exam_type: str,
    section: str,
    count: int = 5,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_exam_type(exam_type)
    if section not in exam_svc.SECTION_LABELS:
        raise HTTPException(status_code=422, detail="不支持的题型")
    rows = await exam_svc.pick_questions(
        db, exam_type, section, max(1, min(count, 10)), created_by=current_user.id
    )
    if not rows:
        raise HTTPException(status_code=502, detail="题库为空且自动补题失败，请稍后重试")
    return {"questions": [exam_svc._question_out(q) for q in rows]}


@router.post("/exam/practice/check")
async def exam_practice_check(
    request: PracticeCheckIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await exam_svc.check_answer(db, current_user, request.question_id, request.answer)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not result["correct"] and request.archive_wrong:
        try:
            from app.models.zone_extras import MistakeRecord

            q = result["question"]
            opts = "\n".join(f"{k}. {v}" for k, v in (q.get("options") or {}).items())
            db.add(
                MistakeRecord(
                    user_id=current_user.id,
                    question=(q["question"] + ("\n" + opts if opts else ""))[:2000],
                    student_answer=request.answer,
                    correct_answer=q.get("answer") or "",
                    subject=exam_svc.EXAM_LABELS.get(q.get("exam_type") or "", "考级练习"),
                    note=(q.get("analysis") or "")[:500],
                )
            )
            await db.commit()
            result["mistake_archived"] = True
        except Exception:  # noqa: BLE001
            result["mistake_archived"] = False
    return result


@router.post("/exam/practice/log")
async def exam_practice_log(
    request: PracticeLogIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await exam_svc.log_practice(
        db,
        current_user.id,
        exam_type=request.exam_type,
        section=request.section,
        activity=request.activity,
        total=request.total,
        correct=request.correct,
        meta=request.meta,
    )
    return {"ok": True}


@router.post("/exam/mock/start")
async def exam_mock_start(
    request: MockStartIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_exam_type(request.exam_type)
    try:
        return await exam_svc.start_mock(db, current_user, request.exam_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/exam/mock/submit")
async def exam_mock_submit(
    request: MockSubmitIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await exam_svc.submit_mock(db, current_user, request.run_id, request.answers)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/exam/mock/history")
async def exam_mock_history(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ExamMockRun)
                .where(ExamMockRun.user_id == current_user.id, ExamMockRun.status == "done")
                .order_by(ExamMockRun.finished_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "run_id": r.id,
            "exam_type": r.exam_type,
            "score": r.score,
            "section_scores": r.section_scores or {},
            "finished_at": r.finished_at.isoformat() if r.finished_at else "",
        }
        for r in rows
    ]


@router.get("/exam/words")
async def exam_words(
    exam_type: str,
    offset: int = 0,
    limit: int = 20,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = current_user
    return await exam_svc.list_words(db, _check_exam_type(exam_type), offset, limit)


@router.post("/exam/words/seed")
async def exam_words_seed(
    request: WordSeedIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = current_user
    added = await exam_svc.seed_words(db, _check_exam_type(request.exam_type), request.count)
    if not added:
        raise HTTPException(status_code=502, detail="词书生成失败，请稍后重试")
    return {"ok": True, "added": added}


@router.post("/exam/words/{word_id}/collect")
async def exam_word_collect(
    word_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await exam_svc.collect_word(db, current_user.id, word_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/exam/essay/grade")
async def exam_essay_grade(
    request: EssayGradeIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_exam_type(request.exam_type)
    kind = request.kind if request.kind in ("writing", "translation") else "writing"
    try:
        result = await exam_svc.grade_essay(
            current_user.id, request.exam_type, kind, request.prompt, request.text
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        await exam_svc.log_practice(
            db,
            current_user.id,
            exam_type=request.exam_type,
            section=kind,
            activity="essay",
            total=1,
            correct=1 if float(result.get("score") or 0) >= 60 else 0,
            meta={"score": result.get("score")},
        )
    except Exception:  # noqa: BLE001
        pass
    return result


@router.post("/exam/listening/material")
async def exam_listening_material(
    request: ListeningIn,
    current_user=Depends(require_current_user),
) -> dict:
    _check_exam_type(request.exam_type)
    try:
        return await exam_svc.generate_listening_material(
            current_user.id, request.exam_type, request.topic
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/exam/challenge")
async def exam_challenge_status(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await exam_svc.campaign_status(db, current_user)


@router.post("/exam/challenge/join")
async def exam_challenge_join(
    request: ChallengeJoinIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_exam_type(request.exam_type)
    row = await exam_svc.get_or_create_campaign(db, current_user, request.exam_type, create=True)
    return {"ok": True, "id": row.id if row else ""}


@router.post("/exam/challenge/checkin")
async def exam_challenge_checkin(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await exam_svc.campaign_checkin(db, current_user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
