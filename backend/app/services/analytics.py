"""管理端数据分析：看业务行为（区别于 Token 用量页看成本）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, desc, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import AssignmentSubmission
from app.models.galaxy import Galaxy, Planet
from app.models.mastery import PlanetMastery
from app.models.system import ApiUsageLog
from app.models.user import User


async def build_analytics(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    dau = (
        await session.execute(
            select(func.count(func.distinct(ApiUsageLog.user_id))).where(
                ApiUsageLog.created_at >= day_ago, ApiUsageLog.user_id != ""
            )
        )
    ).scalar() or 0
    wau = (
        await session.execute(
            select(func.count(func.distinct(ApiUsageLog.user_id))).where(
                ApiUsageLog.created_at >= week_ago, ApiUsageLog.user_id != ""
            )
        )
    ).scalar() or 0
    total_users = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    new_users_7d = (
        await session.execute(select(func.count()).select_from(User).where(User.created_at >= week_ago))
    ).scalar() or 0

    # 近 14 天活跃趋势（按天：活跃用户数 + 调用量）
    active_rows = (
        await session.execute(
            select(
                func.date(ApiUsageLog.created_at).label("day"),
                func.count(func.distinct(ApiUsageLog.user_id)).label("users"),
                func.count().label("calls"),
            )
            .where(ApiUsageLog.created_at >= two_weeks_ago)
            .group_by(func.date(ApiUsageLog.created_at))
            .order_by("day")
        )
    ).all()
    active_trend = [
        {"date": str(r.day), "active_users": int(r.users), "calls": int(r.calls)} for r in active_rows
    ]

    # 近 14 天注册趋势
    reg_rows = (
        await session.execute(
            select(func.date(User.created_at).label("day"), func.count().label("n"))
            .where(User.created_at >= two_weeks_ago)
            .group_by(func.date(User.created_at))
            .order_by("day")
        )
    ).all()
    registration_trend = [{"date": str(r.day), "count": int(r.n)} for r in reg_rows]

    # 近 7 天活跃时段分布（UTC 小时）
    hour_rows = (
        await session.execute(
            select(extract("hour", ApiUsageLog.created_at).label("hour"), func.count().label("n"))
            .where(ApiUsageLog.created_at >= week_ago)
            .group_by(extract("hour", ApiUsageLog.created_at))
        )
    ).all()
    hour_map = {int(r.hour): int(r.n) for r in hour_rows if r.hour is not None}
    hour_distribution = [{"hour": h, "calls": hour_map.get(h, 0)} for h in range(24)]

    # 行星学习热度 Top10（掌握记录数 + 点亮数）
    planet_rows = (
        await session.execute(
            select(
                Planet.name,
                Galaxy.name.label("galaxy_name"),
                func.count(PlanetMastery.id).label("learners"),
                func.sum(case((PlanetMastery.status == "lit", 1), else_=0)).label("lit"),
            )
            .join(PlanetMastery, PlanetMastery.planet_id == Planet.id)
            .join(Galaxy, Galaxy.id == Planet.galaxy_id)
            .group_by(Planet.id, Planet.name, Galaxy.name)
            .order_by(desc("learners"))
            .limit(10)
        )
    ).all()
    top_planets = [
        {
            "planet": r.name,
            "galaxy": r.galaxy_name,
            "learners": int(r.learners or 0),
            "lit": int(r.lit or 0),
        }
        for r in planet_rows
    ]

    # 近 7 天教师批阅趋势
    grade_rows = (
        await session.execute(
            select(func.date(AssignmentSubmission.graded_at).label("day"), func.count().label("n"))
            .where(AssignmentSubmission.graded_at >= week_ago)
            .group_by(func.date(AssignmentSubmission.graded_at))
            .order_by("day")
        )
    ).all()
    grading_trend = [{"date": str(r.day), "count": int(r.n)} for r in grade_rows]

    return {
        "kpis": {
            "dau": int(dau),
            "wau": int(wau),
            "total_users": int(total_users),
            "new_users_7d": int(new_users_7d),
        },
        "active_trend": active_trend,
        "registration_trend": registration_trend,
        "hour_distribution": hour_distribution,
        "top_planets": top_planets,
        "grading_trend": grading_trend,
    }
