from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import ProfileExtraction
from app.models.student_profile import PROFILE_DIMENSIONS, StudentProfile
from app.schemas.profile_history import ProfileHistoryItem
from app.schemas.student_profile import StudentProfileExtract


def _dim_value(data: dict | None) -> str:
    if isinstance(data, dict):
        return str(data.get("value") or "")
    return ""


def _dim_score(data: dict | None) -> int | None:
    if isinstance(data, dict) and data.get("score") is not None:
        try:
            return int(data.get("score"))
        except (TypeError, ValueError):
            return None
    return None


def _merge_floors(profile: StudentProfileExtract, floors: dict | None) -> StudentProfileExtract:
    """Ensure LLM extract scores do not fall below protected floors from improvement grading."""
    floors = floors or {}
    payload = profile.model_dump()
    for dim in PROFILE_DIMENSIONS:
        floor = floors.get(dim)
        if floor is None:
            continue
        try:
            floor_i = int(floor)
        except (TypeError, ValueError):
            continue
        dim_data = payload.get(dim) or {}
        if not isinstance(dim_data, dict):
            dim_data = {"value": "", "score": 0, "evidence": []}
        score = int(dim_data.get("score") or 0)
        if score < floor_i:
            dim_data = {**dim_data, "score": floor_i}
            evidence = list(dim_data.get("evidence") or [])
            note = f"分数保护下限 {floor_i}（改进验收）"
            if note not in evidence:
                evidence.append(note)
            dim_data["evidence"] = evidence
            payload[dim] = dim_data
    return StudentProfileExtract.model_validate(payload)


def _profile_to_history(row: StudentProfile) -> ProfileHistoryItem:
    return ProfileHistoryItem(
        id=row.id,
        student_name=row.student_name,
        summary=row.summary,
        major_background=_dim_value(row.major_background),
        prior_knowledge=_dim_value(row.prior_knowledge),
        cognitive_style=_dim_value(row.cognitive_style),
        mistake_tendency=_dim_value(row.mistake_tendency),
        learning_goal=_dim_value(row.learning_goal),
        time_flexibility=_dim_value(row.time_flexibility),
        modality_preference=_dim_value(getattr(row, "modality_preference", None)),
        motivation_level=_dim_value(getattr(row, "motivation_level", None)),
        major_background_score=_dim_score(row.major_background),
        prior_knowledge_score=_dim_score(row.prior_knowledge),
        cognitive_style_score=_dim_score(row.cognitive_style),
        mistake_tendency_score=_dim_score(row.mistake_tendency),
        learning_goal_score=_dim_score(row.learning_goal),
        time_flexibility_score=_dim_score(row.time_flexibility),
        modality_preference_score=_dim_score(getattr(row, "modality_preference", None)),
        motivation_level_score=_dim_score(getattr(row, "motivation_level", None)),
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


async def get_latest_floors(session: AsyncSession, user_id: str) -> dict:
    latest = await get_latest_profile(session, user_id=user_id)
    if latest is None:
        return {}
    floors = latest.dimension_floors_json or {}
    return floors if isinstance(floors, dict) else {}


async def get_latest_warnings(session: AsyncSession, user_id: str) -> list:
    latest = await get_latest_profile(session, user_id=user_id)
    if latest is None:
        return []
    warnings = latest.warnings_json or []
    return warnings if isinstance(warnings, list) else []


async def save_student_profile(
    session: AsyncSession,
    profile: StudentProfileExtract,
    *,
    user_id: str = "",
    dimension_floors: dict | None = None,
    warnings: list | None = None,
    apply_floor_merge: bool = True,
    update_source: str = "profiler",
) -> StudentProfile:
    floors = dimension_floors
    prev_warnings: list = []
    if user_id:
        latest = await get_latest_profile(session, user_id=user_id)
        if floors is None and latest is not None:
            floors = latest.dimension_floors_json or {}
        if warnings is None and latest is not None:
            prev_warnings = list(latest.warnings_json or [])
        elif warnings is not None:
            prev_warnings = warnings
        else:
            prev_warnings = []
    else:
        prev_warnings = list(warnings or [])

    floors = floors or {}
    if apply_floor_merge and floors:
        profile = _merge_floors(profile, floors)

    payload = profile.model_dump()
    src = (update_source or "profiler").strip() or "profiler"

    def _new_row() -> StudentProfile:
        kwargs = {
            "user_id": user_id or "",
            "student_name": profile.student_name,
            "summary": profile.summary,
            "raw_evidence": {"update_source": src},
            "missing_dimensions": list(profile.missing_dimensions or []),
            "follow_up_questions": list(profile.follow_up_questions or []),
            "dimension_floors_json": floors,
            "warnings_json": prev_warnings,
            "update_source": src,
        }
        for dim in PROFILE_DIMENSIONS:
            kwargs[dim] = payload.get(dim) or {}
        return StudentProfile(**kwargs)

    row = _new_row()
    session.add(row)
    session.add(
        ProfileExtraction(
            student_name=profile.student_name,
            summary=profile.summary,
            source=src,
        )
    )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        # 审计表结构异常时，仍保证主画像可落库
        row = _new_row()
        session.add(row)
        await session.commit()
    await session.refresh(row)
    return row


async def get_latest_profile(
    session: AsyncSession,
    student_name: str | None = None,
    *,
    user_id: str | None = None,
) -> StudentProfile | None:
    stmt = select(StudentProfile).order_by(desc(StudentProfile.created_at))
    if user_id:
        stmt = stmt.where(StudentProfile.user_id == user_id)
    elif student_name:
        stmt = stmt.where(StudentProfile.student_name == student_name)
    return (await session.execute(stmt.limit(1))).scalar_one_or_none()


async def get_profile_by_id(session: AsyncSession, profile_id: str) -> StudentProfile | None:
    if not profile_id:
        return None
    return (
        await session.execute(select(StudentProfile).where(StudentProfile.id == profile_id))
    ).scalar_one_or_none()


async def list_profile_history(
    session: AsyncSession,
    *,
    student_name: str | None = None,
    user_id: str | None = None,
) -> list[ProfileHistoryItem]:
    stmt = select(StudentProfile).order_by(desc(StudentProfile.created_at)).limit(50)
    if user_id:
        stmt = stmt.where(StudentProfile.user_id == user_id)
    elif student_name:
        stmt = stmt.where(StudentProfile.student_name == student_name)
    rows = (await session.execute(stmt)).scalars().all()
    return [_profile_to_history(row) for row in rows]
