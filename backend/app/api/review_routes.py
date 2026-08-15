"""学生学习闭环 API：今日复习队列（SRS）/ 学习日历 / 学习周报。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_current_user
from app.services import review_queue as review_svc

router = APIRouter(tags=["review-loop"])


class ReviewSubmitIn(BaseModel):
    item_type: str = Field(min_length=1, max_length=16)
    item_id: str = Field(min_length=1, max_length=64)
    result: str = Field(min_length=1, max_length=16)


class ReviewCardIn(BaseModel):
    kind: str = Field(default="card", max_length=16)
    front: str = Field(min_length=1, max_length=2000)
    back: str = Field(default="", max_length=4000)
    extra: str = Field(default="", max_length=4000)
    source_id: str = Field(default="", max_length=128)


@router.get("/review/queue")
async def review_queue(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await review_svc.get_review_queue(db, current_user)


@router.post("/review/submit")
async def review_submit(
    request: ReviewSubmitIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await review_svc.submit_review(
            db, current_user, request.item_type, request.item_id, request.result
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/review/cards")
async def review_card_add(
    request: ReviewCardIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    kind = request.kind if request.kind in ("word", "card") else "card"
    row = await review_svc.add_review_card(
        db,
        current_user.id,
        kind=kind,
        front=request.front,
        back=request.back,
        extra=request.extra,
        source_id=request.source_id,
    )
    return {"ok": True, "id": row.id, "kind": row.kind}


@router.get("/calendar")
async def study_calendar(
    month: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.student_calendar import month_calendar

    try:
        return await month_calendar(db, current_user, month)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/report/weekly")
async def weekly_report(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.student_calendar import weekly_report as build_report

    return await build_report(db, current_user)
