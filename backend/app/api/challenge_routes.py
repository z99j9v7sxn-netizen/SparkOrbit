"""挑战赛增量 API：星库 / 演武 / 代码舱 / 闸门 / 笔记升维。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import STARLIB_DIR
from app.db.session import get_db
from app.dependencies import require_current_user, require_teacher
from app.models.galaxy import Planet
from app.schemas.galaxy import SelectionAskIn, SelectionAskOut
from app.schemas.note import NoteAiSummaryIn, NoteClipIn, NoteOut
from app.services import algo_viz as viz
from app.services import codelab as lab
from app.services import codelab_runner
from app.services import mastery_gates as gates
from app.services import starlib as starlib_svc
from app.services.companion import selection_ask
from app.services.note_service import ai_summary_note, clip_to_note
from app.services.upload_service import save_upload_file

router = APIRouter(tags=["challenge-sprint"])


class BilibiliCreateIn(BaseModel):
    title: str = ""
    bvid: str = ""
    galaxy_slug: str = ""
    planet_slug: str = ""
    description: str = ""
    class_id: str = ""


class CodelabRunIn(BaseModel):
    code: str
    timeout: int = 3


@router.get("/starlib/assets")
async def starlib_list(
    galaxy_slug: str = "",
    asset_type: str = "",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await starlib_svc.list_assets(db, current_user, galaxy_slug=galaxy_slug, asset_type=asset_type)


@router.get("/starlib/assets/{asset_id}")
async def starlib_get(
    asset_id: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    _ = current_user
    row = await starlib_svc.get_asset(db, asset_id)
    if not row:
        raise HTTPException(status_code=404, detail="资产不存在")
    return row


@router.delete("/starlib/assets/{asset_id}")
async def starlib_delete(
    asset_id: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        return await starlib_svc.delete_asset(db, current_user, asset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/starlib/upload")
async def starlib_upload(
    title: str = Form(""),
    galaxy_slug: str = Form(""),
    planet_slug: str = Form(""),
    asset_type: str = Form("pdf"),
    description: str = Form(""),
    class_id: str = Form(""),
    file: UploadFile = File(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw = await file.read()
    file.file.seek(0)
    try:
        file_url = await save_upload_file(file, STARLIB_DIR, "starlib")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await starlib_svc.create_pdf_asset(
            db,
            current_user,
            title=title or (file.filename or "教材"),
            file_url=file_url,
            pdf_bytes=raw,
            galaxy_slug=galaxy_slug,
            planet_slug=planet_slug,
            asset_type=asset_type,
            description=description,
            class_id=class_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/starlib/bilibili")
async def starlib_bilibili(
    body: BilibiliCreateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await starlib_svc.create_bilibili_asset(
            db,
            current_user,
            title=body.title,
            bvid_or_url=body.bvid,
            galaxy_slug=body.galaxy_slug,
            planet_slug=body.planet_slug,
            description=body.description,
            class_id=body.class_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/starlib/bilibili/recommend")
async def starlib_bili_recommend(topic: str = "数据结构", current_user=Depends(require_current_user)) -> list[dict]:
    _ = current_user
    return await starlib_svc.recommend_bilibili(topic)


@router.get("/starlib/lectures")
async def starlib_lectures(
    galaxy_slug: str = "",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """考研讲义模式：本地 MP4 列表（自动种子入库）。"""
    return await starlib_svc.ensure_lecture_assets(db, current_user, galaxy_slug=galaxy_slug)


@router.post("/starlib/video")
async def starlib_upload_video(
    title: str = Form(""),
    galaxy_slug: str = Form(""),
    planet_slug: str = Form(""),
    description: str = Form(""),
    file: UploadFile = File(...),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        file_url = await save_upload_file(file, STARLIB_DIR, "starlib")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await starlib_svc.create_local_video_asset(
        db,
        current_user,
        title=title or (file.filename or "讲义视频"),
        file_url=file_url,
        galaxy_slug=galaxy_slug,
        planet_slug=planet_slug,
        description=description,
    )


@router.post("/starlib/assets/{asset_id}/progress")
async def starlib_progress(
    asset_id: str,
    page: int = 1,
    seconds: int = 30,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await starlib_svc.mark_reading_progress(db, current_user, asset_id=asset_id, page=page, seconds=seconds)


@router.get("/algo-viz/traces")
async def algo_viz_list(current_user=Depends(require_current_user)) -> list[dict]:
    _ = current_user
    return viz.list_traces()


@router.get("/algo-viz/traces/{trace_id}")
async def algo_viz_get(trace_id: str, current_user=Depends(require_current_user)) -> dict:
    _ = current_user
    t = viz.get_trace(trace_id)
    if not t:
        raise HTTPException(status_code=404, detail="轨迹不存在")
    return t


@router.get("/algo-viz/match")
async def algo_viz_match(
    planet_slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    _ = current_user
    planet = (await db.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if not planet:
        raise HTTPException(status_code=404, detail="行星不存在")
    t = viz.match_trace_for_planet(planet.name, planet.description or "")
    if not t:
        raise HTTPException(status_code=404, detail="暂无匹配演武")
    return t


@router.post("/algo-viz/complete")
async def algo_viz_complete(
    planet_slug: str = Form(...),
    trace_id: str = Form(...),
    steps_viewed: int = Form(0),
    total_steps: int = Form(1),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await viz.complete_viz(
        db,
        current_user,
        planet_slug=planet_slug,
        trace_id=trace_id,
        steps_viewed=steps_viewed,
        total_steps=total_steps,
    )


@router.post("/algo-viz/predict")
async def algo_viz_predict(
    payload: dict = Body(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    trace_id = str(payload.get("trace_id") or "").strip()
    if not trace_id:
        raise HTTPException(status_code=400, detail="缺少 trace_id")
    try:
        step_index = int(payload.get("step_index", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="step_index 无效") from exc
    answer = str(payload.get("answer") or "")
    planet_slug = str(payload.get("planet_slug") or "")
    result = await viz.predict_next_state(
        db,
        current_user,
        trace_id=trace_id,
        step_index=step_index,
        answer=answer,
        planet_slug=planet_slug,
    )
    if not result.get("ok") and result.get("detail"):
        raise HTTPException(status_code=400, detail=str(result["detail"]))
    return result


@router.post("/algo-viz/generate")
async def algo_viz_generate(
    topic: str = Form(...),
    planet_slug: str = Form(""),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    return await viz.generate_trace(topic, planet_slug)


@router.post("/algo-viz/rerun")
async def algo_viz_rerun(
    payload: dict = Body(...),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    structure = str(payload.get("structure") or "array")
    initial = payload.get("initial") or {}
    if not isinstance(initial, dict):
        raise HTTPException(status_code=400, detail="initial 必须是对象")
    return viz.rerun_from_initial(
        structure=structure,
        initial=initial,
        code=str(payload.get("code") or ""),
        title=str(payload.get("title") or ""),
    )


@router.get("/mastery/{planet_slug}/gates")
async def mastery_gates_get(
    planet_slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    from app.services.gate_policy import get_thresholds_for_user

    planet = (await db.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if not planet:
        raise HTTPException(status_code=404, detail="行星不存在")
    mastery = await gates.ensure_mastery(db, current_user.id, planet.id)
    thresholds = await get_thresholds_for_user(db, current_user, "")
    await db.commit()
    return gates.gate_snapshot(mastery, thresholds)


@router.post("/mastery/{planet_slug}/gates/explain")
async def mastery_pass_explain(
    planet_slug: str,
    score: float = 0.8,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.gate_policy import get_thresholds_for_user

    planet = (await db.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if not planet:
        raise HTTPException(status_code=404, detail="行星不存在")
    mastery = await gates.ensure_mastery(db, current_user.id, planet.id)
    thresholds = await get_thresholds_for_user(db, current_user, "")
    gates.pass_explain_gate(mastery, score=score, policy=thresholds)
    lit = gates.try_light_planet(mastery)
    if lit:
        current_user.points += 10
        db.add(current_user)
    await db.commit()
    snap = gates.gate_snapshot(mastery, thresholds)
    snap["lit"] = lit
    return snap


@router.post("/mastery/{planet_slug}/gates/learn")
async def mastery_learn_evidence(
    planet_slug: str,
    kind: str = Form("manual"),
    detail: str = Form(""),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.gate_policy import get_thresholds_for_user

    planet = (await db.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if not planet:
        raise HTTPException(status_code=404, detail="行星不存在")
    mastery = await gates.ensure_mastery(db, current_user.id, planet.id)
    thresholds = await get_thresholds_for_user(db, current_user, "")
    snap = gates.record_learn_evidence(mastery, kind=kind, detail=detail, policy=thresholds)
    await db.commit()
    return snap


@router.post("/companion/selection-ask", response_model=SelectionAskOut)
async def companion_selection_ask(
    body: SelectionAskIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> SelectionAskOut:
    result = await selection_ask(
        quote=body.quote,
        planet_slug=body.planet_slug,
        question=body.question,
        asset_id=body.asset_id,
        page_no=body.page_no,
        image_base64=body.image_base64,
        image_mime=body.image_mime,
        mode=body.mode,
        socratic=body.socratic,
        session=db,
        user=current_user,
    )
    return SelectionAskOut(**result)


@router.post("/codelab/run")
async def codelab_run(
    body: CodelabRunIn,
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    return await codelab_runner.run_code(body.code, timeout=body.timeout)


@router.post("/codelab/exercise")
async def codelab_exercise(
    planet_slug: str = Form(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await lab.generate_exercise(db, current_user, planet_slug)


@router.post("/codelab/hint")
async def codelab_hint(
    planet_slug: str = Form(...),
    code: str = Form(""),
    question: str = Form(""),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    return await lab.coach_hint(planet_slug, code, question)


@router.post("/codelab/explain")
async def codelab_explain(
    planet_slug: str = Form(...),
    code: str = Form(""),
    question: str = Form(""),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    return await lab.coach_explain(planet_slug, code, question)


@router.post("/codelab/passed")
async def codelab_passed(
    planet_slug: str = Form(...),
    passed: int = Form(1),
    total: int = Form(1),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await lab.mark_tests_passed(db, current_user, planet_slug=planet_slug, passed=passed, total=total)


@router.post("/notes/clip", response_model=NoteOut)
async def notes_clip(
    request: NoteClipIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    row = await clip_to_note(
        db,
        current_user.id,
        planet_slug=request.planet_slug,
        block=request.block,
        title=request.title,
    )
    return NoteOut(**row)


@router.post("/notes/ai-summary", response_model=NoteOut)
async def notes_ai_summary(
    request: NoteAiSummaryIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    row = await ai_summary_note(db, current_user.id, planet_slug=request.planet_slug)
    return NoteOut(**row)


@router.post("/digital-tutor/generate")
async def digital_tutor_generate(
    payload: dict = Body(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """创建数字人讲解。mode=mistake 为 DeepSeek 分镜+讲稿；其它模式可走讯飞视频。"""
    from app.services import digital_tutor as dh_svc

    mode = str(payload.get("mode") or "planet").strip().lower()
    planet_slug = str(payload.get("planet_slug") or "").strip()
    if mode != "mistake" and not planet_slug:
        raise HTTPException(status_code=400, detail="planet_slug 必填")
    prompt = str(payload.get("prompt") or "").strip()
    force = bool(payload.get("force") or False)
    word_count = payload.get("word_count")
    try:
        wc = int(word_count) if word_count is not None else None
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="word_count 须为整数") from exc
    try:
        return await dh_svc.start_generate(
            db,
            current_user,
            planet_slug=planet_slug,
            prompt=prompt,
            word_count=wc,
            force=force,
            mode=mode,
            mistake_id=str(payload.get("mistake_id") or "").strip(),
            question=str(payload.get("question") or "").strip(),
            student_answer=str(payload.get("student_answer") or "").strip(),
            correct_answer=str(payload.get("correct_answer") or "").strip(),
            note=str(payload.get("note") or "").strip(),
            subject=str(payload.get("subject") or "").strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/digital-tutor/mistake-explain")
async def digital_tutor_mistake_explain(
    payload: dict = Body(...),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """错题分镜讲解（DeepSeek slides + script）；与 generate?mode=mistake 等价。"""
    from app.services import digital_tutor as dh_svc

    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 必填")
    _ = db
    try:
        return await dh_svc.start_generate(
            db,
            current_user,
            planet_slug=str(payload.get("planet_slug") or "").strip(),
            force=bool(payload.get("force") or False),
            mode="mistake",
            mistake_id=str(payload.get("mistake_id") or "").strip(),
            question=question,
            student_answer=str(payload.get("student_answer") or "").strip(),
            correct_answer=str(payload.get("correct_answer") or "").strip(),
            note=str(payload.get("note") or "").strip(),
            subject=str(payload.get("subject") or "").strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/digital-tutor/saved")
async def digital_tutor_saved(
    planet_slug: str = "",
    mistake_id: str = "",
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """读取已保存讲解：planet_slug（视频）或 mistake_id（分镜缓存 / 旧视频）。"""
    from app.services import digital_tutor as dh_svc

    _ = current_user
    mid = (mistake_id or "").strip()
    slug = (planet_slug or "").strip()
    if mid:
        return await dh_svc.get_saved(db, mistake_id=mid)
    if not slug:
        raise HTTPException(status_code=400, detail="planet_slug 或 mistake_id 必填")
    return await dh_svc.get_saved(db, planet_slug=slug)


@router.get("/digital-tutor/tasks/{task_id}")
async def digital_tutor_task(
    task_id: str,
    current_user=Depends(require_current_user),
) -> dict:
    """查询数字人讲解任务状态。"""
    from app.services import digital_tutor as dh_svc

    _ = current_user
    try:
        return await dh_svc.query_local_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="任务不存在或已过期") from exc
