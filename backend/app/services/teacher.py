"""教师端：班级星图热力、低迷学生预警、AI 派发复习任务、画像矩阵、引力陷阱、时空干预。"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.galaxy import Galaxy, Planet
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.school_class import SchoolClass
from app.models.student_profile import PROFILE_DIMENSIONS, StudentProfile
from app.models.user import User
from app.schemas.teacher import (
    ClassBriefOut,
    ClassOverviewOut,
    DispatchTaskRequest,
    DispatchTaskResponse,
    GalaxyHeatItem,
    GravityWellItem,
    InterventionRequest,
    InterventionResponse,
    ProfileMatrixOut,
    StudentRiskItem,
)


async def list_teacher_classes(session: AsyncSession, teacher: User) -> list[ClassBriefOut]:
    if teacher.role == "admin":
        rows = (await session.execute(select(SchoolClass).order_by(SchoolClass.name))).scalars().all()
    else:
        rows = (
            await session.execute(
                select(SchoolClass).where(SchoolClass.teacher_id == teacher.id).order_by(SchoolClass.name)
            )
        ).scalars().all()
    return [ClassBriefOut(id=c.id, name=c.name, invite_code=c.invite_code) for c in rows]


async def _class_ids_for_teacher(session: AsyncSession, teacher: User, class_id: str = "") -> list[str]:
    if class_id:
        cls = (await session.execute(select(SchoolClass).where(SchoolClass.id == class_id))).scalar_one_or_none()
        if cls is None:
            return []
        if teacher.role != "admin" and cls.teacher_id != teacher.id:
            return []
        return [class_id]
    if teacher.role == "admin":
        rows = (await session.execute(select(SchoolClass.id))).scalars().all()
        return list(rows)
    rows = (
        await session.execute(select(SchoolClass.id).where(SchoolClass.teacher_id == teacher.id))
    ).scalars().all()
    return list(rows)


async def _students(session: AsyncSession, teacher: User, class_id: str = "") -> list[User]:
    class_ids = await _class_ids_for_teacher(session, teacher, class_id)
    if not class_ids:
        return []
    return (
        await session.execute(
            select(User).where(User.role == "student", User.class_id.in_(class_ids)).order_by(User.display_name)
        )
    ).scalars().all()


async def class_overview(session: AsyncSession, teacher: User, class_id: str = "") -> ClassOverviewOut:
    students = await _students(session, teacher, class_id)
    total_students = len(students)
    student_ids = {s.id for s in students}
    galaxies = (await session.execute(select(Galaxy).order_by(Galaxy.sort_order))).scalars().all()
    galaxy_map = {g.id: g for g in galaxies}
    planets = (await session.execute(select(Planet).order_by(Planet.sort_order))).scalars().all()

    lit_map: dict[str, int] = {}
    if student_ids:
        lit_rows = (
            await session.execute(
                select(PlanetMastery.planet_id, func.count())
                .where(PlanetMastery.status == "lit", PlanetMastery.user_id.in_(student_ids))
                .group_by(PlanetMastery.planet_id)
            )
        ).all()
        lit_map = {pid: c for pid, c in lit_rows}

    heatmap: list[GalaxyHeatItem] = []
    for p in planets:
        g = galaxy_map.get(p.galaxy_id)
        if g is None:
            continue
        lit = lit_map.get(p.id, 0)
        rate = round((lit / total_students) * 100) if total_students else 0
        heatmap.append(
            GalaxyHeatItem(
                galaxy_slug=g.slug,
                galaxy_name=g.name,
                planet_slug=p.slug,
                planet_name=p.name,
                lit_count=lit,
                total_students=total_students,
                mastery_rate=rate,
            )
        )

    weakest = sorted(heatmap, key=lambda h: h.mastery_rate)[:6]
    avg = round(sum(h.mastery_rate for h in heatmap) / len(heatmap)) if heatmap else 0

    return ClassOverviewOut(
        total_students=total_students,
        total_planets=len(planets),
        avg_mastery_rate=avg,
        weakest_planets=weakest,
        heatmap=heatmap,
    )


async def student_risks(session: AsyncSession, teacher: User, class_id: str = "") -> list[StudentRiskItem]:
    students = await _students(session, teacher, class_id)
    total_planets = len((await session.execute(select(Planet))).scalars().all())

    items: list[StudentRiskItem] = []
    for u in students:
        mastery = (
            await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == u.id))
        ).scalars().all()
        lit = sum(1 for m in mastery if m.status == "lit")
        recent_wrong = sum(len(m.last_wrong_tags or []) for m in mastery)
        rate = round((lit / total_planets) * 100) if total_planets else 0
        if rate < 25 or recent_wrong >= 6:
            risk = "high"
        elif rate < 50:
            risk = "medium"
        else:
            risk = "low"
        items.append(
            StudentRiskItem(
                user_id=u.id,
                display_name=u.display_name,
                username=u.username,
                lit_count=lit,
                total_planets=total_planets,
                mastery_rate=rate,
                recent_wrong=recent_wrong,
                risk_level=risk,
            )
        )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(items, key=lambda x: (order[x.risk_level], x.mastery_rate))


async def dispatch_task(session: AsyncSession, teacher: User, req: DispatchTaskRequest) -> DispatchTaskResponse:
    planet_hint = ""
    if req.planet_slug:
        planet = (
            await session.execute(select(Planet).where(Planet.slug == req.planet_slug))
        ).scalar_one_or_none()
        if planet:
            planet_hint = f"[planet:{req.planet_slug}] 目标行星：{planet.name}。"
        else:
            planet_hint = f"[planet:{req.planet_slug}] "
    alert = Alert(
        user_id=teacher.id,
        student_id=req.student_id,
        alert_type="review_task",
        alert_level="medium",
        message=f"{planet_hint}{req.message}",
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return DispatchTaskResponse(ok=True, alert_id=alert.id)


async def class_profile_matrix(session: AsyncSession, teacher: User, class_id: str = "") -> ProfileMatrixOut:
    students = await _students(session, teacher, class_id)
    student_names = {s.display_name for s in students}
    profiles = (await session.execute(select(StudentProfile))).scalars().all()
    profiles = [p for p in profiles if p.student_name in student_names]

    dim_scores: dict[str, list[int]] = {d: [] for d in PROFILE_DIMENSIONS}
    for p in profiles:
        for dim in PROFILE_DIMENSIONS:
            data = getattr(p, dim) or {}
            score = data.get("score", 0) if isinstance(data, dict) else 0
            if score:
                dim_scores[dim].append(int(score))

    averages = {}
    for dim, scores in dim_scores.items():
        averages[dim] = round(sum(scores) / len(scores)) if scores else 50

    explore_score = round(
        (averages.get("cognitive_style", 50) + averages.get("learning_goal", 50)) / 2
    )
    conservative_score = round(
        (averages.get("prior_knowledge", 50) + averages.get("mistake_tendency", 50)) / 2
    )
    tendency = "explore" if explore_score >= conservative_score else "conservative"
    tendency_label = "探索型" if tendency == "explore" else "保守型"

    return ProfileMatrixOut(
        total_students=len(students),
        profile_count=len(profiles),
        dimension_averages=averages,
        explore_score=explore_score,
        conservative_score=conservative_score,
        class_tendency=tendency,
        class_tendency_label=tendency_label,
    )


async def gravity_wells(session: AsyncSession, teacher: User, class_id: str = "") -> list[GravityWellItem]:
    students = await _students(session, teacher, class_id)
    total = len(students)
    if total == 0:
        return []

    planets = (await session.execute(select(Planet).order_by(Planet.sort_order))).scalars().all()
    galaxy_map = {g.id: g for g in (await session.execute(select(Galaxy))).scalars().all()}
    student_ids = {s.id for s in students}

    wells: list[GravityWellItem] = []
    for p in planets:
        mastery = (
            await session.execute(
                select(PlanetMastery).where(
                    PlanetMastery.planet_id == p.id, PlanetMastery.user_id.in_(student_ids)
                )
            )
        ).scalars().all()
        lit = sum(1 for m in mastery if m.status == "lit")
        stuck = total - lit
        stuck_rate = round((stuck / total) * 100)
        if stuck_rate >= 60:
            g = galaxy_map.get(p.galaxy_id)
            wells.append(
                GravityWellItem(
                    galaxy_slug=g.slug if g else "",
                    galaxy_name=g.name if g else "",
                    planet_slug=p.slug,
                    planet_name=p.name,
                    stuck_count=stuck,
                    total_students=total,
                    stuck_rate=stuck_rate,
                    severity="critical" if stuck_rate >= 80 else "high",
                )
            )
    return sorted(wells, key=lambda w: w.stuck_rate, reverse=True)


async def intervene(
    session: AsyncSession, teacher: User, req: InterventionRequest
) -> InterventionResponse:
    student = (
        await session.execute(select(User).where(User.id == req.student_id))
    ).scalar_one_or_none()
    if student is None:
        return InterventionResponse(ok=False, message="学生不存在")

    planet_hint = ""
    if req.planet_slug:
        planet = (
            await session.execute(select(Planet).where(Planet.slug == req.planet_slug))
        ).scalar_one_or_none()
        if planet:
            planet_hint = f"目标行星：{planet.name}。"

    rescue_context = (
        f"【救援助手】{planet_hint}{req.message}\n"
        "老师已为你派遣专属辅导，请聚焦薄弱点逐步突破。"
    )
    alert = Alert(
        user_id=teacher.id,
        student_id=req.student_id,
        alert_type="rescue_assistant",
        alert_level="high",
        message=rescue_context,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return InterventionResponse(ok=True, alert_id=alert.id, message="救援助手已送达")
