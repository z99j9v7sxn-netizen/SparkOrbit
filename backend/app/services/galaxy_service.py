"""星系 / 行星查询与点亮状态计算。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.galaxy import Galaxy, Planet
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.user import User
from app.schemas.galaxy import (
    AccuracyDailyOut,
    AvatarStateOut,
    GalaxyDetailOut,
    GalaxyMasteryOut,
    GalaxyOut,
    MasteryOverviewOut,
    MasterySeriesOut,
    MasteryTrendOut,
    OrbitPlanetSnapshot,
    OrbitSnapshotOut,
    PlanetOut,
    StudentAlertOut,
    WeakPlanetOut,
    WeeklyActivityOut,
)
from app.services.memory_decay import apply_decay_to_user, compute_decay_state

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


async def _mastery_map(session: AsyncSession, user_id: str) -> dict[str, PlanetMastery]:
    rows = (
        await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == user_id))
    ).scalars().all()
    return {row.planet_id: row for row in rows}


def _planet_status(planet: Planet, mastery: dict[str, PlanetMastery], lit_slugs: set[str]) -> str:
    m = mastery.get(planet.id)
    if m:
        if m.is_permanent and m.status == "lit":
            return "lit"
        decay = compute_decay_state(m)
        if decay in ("fading", "meteor"):
            return decay
        if m.status == "lit":
            return "lit"
    # 前置行星全部点亮才可挑战，否则锁定
    if planet.prerequisites and not all(slug in lit_slugs for slug in planet.prerequisites):
        return "locked"
    return "dim"


async def list_galaxies(session: AsyncSession, user_id: str) -> list[GalaxyOut]:
    galaxies = (
        await session.execute(select(Galaxy).where(Galaxy.is_active.is_(True)).order_by(Galaxy.sort_order))
    ).scalars().all()
    mastery = await _mastery_map(session, user_id)
    lit_ids = {pid for pid, m in mastery.items() if m.status == "lit"}

    out: list[GalaxyOut] = []
    for g in galaxies:
        planets = (
            await session.execute(select(Planet).where(Planet.galaxy_id == g.id))
        ).scalars().all()
        lit_count = sum(1 for p in planets if p.id in lit_ids)
        out.append(
            GalaxyOut(
                id=g.id,
                slug=g.slug,
                name=g.name,
                description=g.description,
                color=g.color,
                orbit_radius=g.orbit_radius,
                sort_order=g.sort_order,
                planet_count=len(planets),
                lit_count=lit_count,
            )
        )
    return out


async def get_galaxy_detail(session: AsyncSession, slug: str, user_id: str) -> GalaxyDetailOut | None:
    await apply_decay_to_user(session, user_id)

    galaxy = (
        await session.execute(select(Galaxy).where(Galaxy.slug == slug))
    ).scalar_one_or_none()
    if galaxy is None:
        return None

    planets = (
        await session.execute(
            select(Planet).where(Planet.galaxy_id == galaxy.id).order_by(Planet.sort_order)
        )
    ).scalars().all()
    mastery = await _mastery_map(session, user_id)

    # 点亮的行星 slug 集合（跨星系，用于前置判断）
    all_planets = (await session.execute(select(Planet))).scalars().all()
    id_to_slug = {p.id: p.slug for p in all_planets}
    lit_slugs = {id_to_slug[pid] for pid, m in mastery.items() if m.status == "lit" and pid in id_to_slug}

    planet_out: list[PlanetOut] = []
    lit_count = 0
    for p in planets:
        status = _planet_status(p, mastery, lit_slugs)
        if status == "lit":
            lit_count += 1
        m = mastery.get(p.id)
        planet_out.append(
            PlanetOut(
                id=p.id,
                slug=p.slug,
                name=p.name,
                description=p.description,
                difficulty=p.difficulty,
                orbit_index=p.orbit_index,
                angle_deg=p.angle_deg,
                radius_offset=p.radius_offset,
                prerequisites=list(p.prerequisites or []),
                status=status,
                score=m.score if m else 0,
                attempts=m.attempts if m else 0,
                decay_state=m.decay_state if m else "lit",
                is_permanent=bool(m.is_permanent) if m else False,
            )
        )

    return GalaxyDetailOut(
        id=galaxy.id,
        slug=galaxy.slug,
        name=galaxy.name,
        description=galaxy.description,
        color=galaxy.color,
        orbit_radius=galaxy.orbit_radius,
        sort_order=galaxy.sort_order,
        planet_count=len(planets),
        lit_count=lit_count,
        planets=planet_out,
    )


async def get_avatar_state(session: AsyncSession, user: User) -> AvatarStateOut:
    total_planets = (await session.execute(select(Planet))).scalars().all()
    mastery = await _mastery_map(session, user.id)
    lit_count = sum(1 for m in mastery.values() if m.status == "lit")
    total = len(total_planets)
    rate = round((lit_count / total) * 100) if total else 0
    return AvatarStateOut(
        display_name=user.display_name,
        points=user.points,
        mood=user.mood,
        streak_days=user.streak_days,
        lit_count=lit_count,
        total_planets=total,
        mastery_rate=rate,
        avatar_cartoon_url=user.avatar_cartoon_url or None,
    )


def _weekday_label(dt: datetime) -> str:
    return WEEKDAY_LABELS[dt.weekday()]


async def get_weekly_activity(session: AsyncSession, user_id: str) -> WeeklyActivityOut:
    """近 7 天答题活跃度，按天聚合（每题按 0.5 小时估算学习时长）。"""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await session.execute(
            select(ChallengeQuestion)
            .where(
                ChallengeQuestion.user_id == user_id,
                ChallengeQuestion.answered.is_(True),
                ChallengeQuestion.created_at >= start,
            )
            .order_by(ChallengeQuestion.created_at.asc())
        )
    ).scalars().all()

    buckets: dict[str, float] = {}
    for i in range(7):
        day = (start + timedelta(days=i)).date()
        buckets[day.isoformat()] = 0.0

    for row in rows:
        if not row.created_at:
            continue
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        if key in buckets:
            buckets[key] += 0.5

    labels: list[str] = []
    hours: list[float] = []
    for i in range(7):
        day = start + timedelta(days=i)
        labels.append(_weekday_label(day))
        hours.append(round(buckets[day.date().isoformat()], 1))

    return WeeklyActivityOut(labels=labels, hours=hours)


async def get_planet_mastery_trend(session: AsyncSession, user_id: str, slug: str) -> MasteryTrendOut | None:
    planet = (
        await session.execute(select(Planet).where(Planet.slug == slug))
    ).scalar_one_or_none()
    if planet is None:
        return None

    rows = (
        await session.execute(
            select(ChallengeQuestion)
            .where(
                ChallengeQuestion.user_id == user_id,
                ChallengeQuestion.planet_id == planet.id,
                ChallengeQuestion.answered.is_(True),
            )
            .order_by(ChallengeQuestion.created_at.desc())
            .limit(7)
        )
    ).scalars().all()
    rows = list(reversed(rows))

    labels: list[str] = []
    scores: list[int] = []
    running = 25
    for idx, row in enumerate(rows):
        labels.append(f"T{idx + 1}")
        if row.correct:
            running = min(100, running + 12)
        else:
            running = max(10, running - 8)
        scores.append(running)

    if not scores:
        mastery = (
            await session.execute(
                select(PlanetMastery).where(
                    PlanetMastery.user_id == user_id,
                    PlanetMastery.planet_id == planet.id,
                )
            )
        ).scalar_one_or_none()
        base = mastery.score if mastery else 20
        labels = ["T-2", "T-1", "当前"]
        scores = [max(10, base - 15), max(10, base - 8), base]

    return MasteryTrendOut(labels=labels, scores=scores)


def _running_scores_from_challenges(rows: list[ChallengeQuestion]) -> tuple[list[str], list[int]]:
    labels: list[str] = []
    scores: list[int] = []
    running = 25
    for idx, row in enumerate(rows):
        labels.append(f"T{idx + 1}")
        if row.correct:
            running = min(100, running + 12)
        else:
            running = max(10, running - 8)
        scores.append(running)
    return labels, scores


async def get_mastery_overview(session: AsyncSession, user_id: str) -> MasteryOverviewOut:
    planets = (await session.execute(select(Planet).order_by(Planet.sort_order))).scalars().all()
    galaxies = (await session.execute(select(Galaxy))).scalars().all()
    galaxy_by_id = {g.id: g for g in galaxies}
    mastery = await _mastery_map(session, user_id)

    # Top planets by score / attempts for series
    ranked = sorted(
        planets,
        key=lambda p: (
            mastery.get(p.id).score if mastery.get(p.id) else 0,
            mastery.get(p.id).attempts if mastery.get(p.id) else 0,
        ),
        reverse=True,
    )
    top = [p for p in ranked if mastery.get(p.id) and (mastery[p.id].attempts > 0 or mastery[p.id].score > 0)][:5]
    if not top:
        top = ranked[:3]

    series: list[MasterySeriesOut] = []
    for planet in top:
        rows = (
            await session.execute(
                select(ChallengeQuestion)
                .where(
                    ChallengeQuestion.user_id == user_id,
                    ChallengeQuestion.planet_id == planet.id,
                    ChallengeQuestion.answered.is_(True),
                )
                .order_by(ChallengeQuestion.created_at.desc())
                .limit(7)
            )
        ).scalars().all()
        rows = list(reversed(rows))
        sample_sparse = False
        if rows:
            labels, scores = _running_scores_from_challenges(rows)
        else:
            sample_sparse = True
            m = mastery.get(planet.id)
            base = m.score if m else 20
            labels = ["T-2", "T-1", "当前"]
            scores = [max(10, base - 15), max(10, base - 8), base]
        series.append(
            MasterySeriesOut(
                planet_slug=planet.slug,
                planet_name=planet.name,
                labels=labels,
                scores=scores,
                sample_sparse=sample_sparse,
            )
        )

    # By galaxy averages
    by_galaxy_acc: dict[str, list[int]] = {}
    for planet in planets:
        g = galaxy_by_id.get(planet.galaxy_id)
        if g is None:
            continue
        m = mastery.get(planet.id)
        if m is None:
            continue
        by_galaxy_acc.setdefault(g.name, []).append(m.score)
    by_galaxy = [
        GalaxyMasteryOut(
            galaxy_name=name,
            avg_score=round(sum(vals) / len(vals), 1) if vals else 0,
            planet_count=len(vals),
        )
        for name, vals in sorted(by_galaxy_acc.items(), key=lambda x: -sum(x[1]) / max(len(x[1]), 1))
    ]

    # Daily accuracy last 30 days
    since = datetime.now(timezone.utc) - timedelta(days=30)
    answered = (
        await session.execute(
            select(ChallengeQuestion)
            .where(
                ChallengeQuestion.user_id == user_id,
                ChallengeQuestion.answered.is_(True),
                ChallengeQuestion.created_at >= since,
            )
            .order_by(ChallengeQuestion.created_at.asc())
        )
    ).scalars().all()
    day_stats: dict[str, list[int]] = {}
    for row in answered:
        if row.created_at is None:
            continue
        key = row.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
        bucket = day_stats.setdefault(key, [0, 0])
        bucket[1] += 1
        if row.correct:
            bucket[0] += 1
    accuracy_daily = [
        AccuracyDailyOut(
            date=day,
            correct_rate=round(correct / attempts * 100, 1) if attempts else 0,
            attempts=attempts,
        )
        for day, (correct, attempts) in sorted(day_stats.items())
    ]

    # Weak planets table
    weak_planets: list[WeakPlanetOut] = []
    for planet in planets:
        m = mastery.get(planet.id)
        if m is None or m.attempts == 0:
            continue
        recent = (
            await session.execute(
                select(ChallengeQuestion)
                .where(
                    ChallengeQuestion.user_id == user_id,
                    ChallengeQuestion.planet_id == planet.id,
                    ChallengeQuestion.answered.is_(True),
                )
                .order_by(ChallengeQuestion.created_at.desc())
                .limit(5)
            )
        ).scalars().all()
        recent_list = list(recent)
        if recent_list:
            recent_acc = sum(1 for r in recent_list if r.correct) / len(recent_list) * 100
            chronological = list(reversed(recent_list))
            _, scores = _running_scores_from_challenges(chronological)
            if len(scores) >= 2:
                delta = scores[-1] - scores[0]
                trend = "up" if delta > 5 else "down" if delta < -5 else "flat"
            else:
                trend = "flat"
            last_at = recent_list[0].created_at.isoformat() if recent_list[0].created_at else None
        else:
            recent_acc = (m.correct_count / m.attempts * 100) if m.attempts else 0
            trend = "flat"
            last_at = m.updated_at.isoformat() if m.updated_at else None

        g = galaxy_by_id.get(planet.galaxy_id)
        weak_planets.append(
            WeakPlanetOut(
                planet_slug=planet.slug,
                planet_name=planet.name,
                galaxy_name=g.name if g else "",
                score=m.score,
                status=m.status,
                recent_accuracy=round(recent_acc, 1),
                trend=trend,
                last_practiced_at=last_at,
            )
        )

    weak_planets.sort(key=lambda w: (w.score, w.recent_accuracy))
    weak_planets = weak_planets[:12]

    return MasteryOverviewOut(
        series=series,
        by_galaxy=by_galaxy,
        accuracy_daily=accuracy_daily,
        weak_planets=weak_planets,
    )


async def list_student_alerts(session: AsyncSession, user_id: str) -> list[StudentAlertOut]:
    rows = (
        await session.execute(
            select(Alert)
            .where(
                Alert.student_id == user_id,
                Alert.resolved.is_(False),
                Alert.alert_type.in_(("rescue_assistant", "review_task")),
            )
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    title_map = {
        "rescue_assistant": "教师救援助手",
        "review_task": "复习任务派发",
    }
    level_map = {
        "rescue_assistant": "warning",
        "review_task": "info",
    }
    out: list[StudentAlertOut] = []
    for a in rows:
        msg = a.message or ""
        planet_slug = None
        if msg.startswith("[planet:") and "]" in msg:
            planet_slug = msg[len("[planet:") : msg.index("]")]
            msg = msg[msg.index("]") + 1 :].strip()
        out.append(
            StudentAlertOut(
                id=a.id,
                alert_type=a.alert_type,
                title=title_map.get(a.alert_type, "系统通知"),
                message=msg,
                level=level_map.get(a.alert_type, a.alert_level or "info"),
                planet_slug=planet_slug,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
        )
    return out


async def get_orbit_snapshot(session: AsyncSession, user_id: str) -> OrbitSnapshotOut:
    await apply_decay_to_user(session, user_id)
    planets = (await session.execute(select(Planet).order_by(Planet.sort_order))).scalars().all()
    mastery = await _mastery_map(session, user_id)
    id_to_slug = {p.id: p.slug for p in planets}
    lit_slugs = {id_to_slug[pid] for pid, m in mastery.items() if m.status == "lit" and pid in id_to_slug}

    snapshots: list[OrbitPlanetSnapshot] = []
    for p in planets:
        status = _planet_status(p, mastery, lit_slugs)
        m = mastery.get(p.id)
        snapshots.append(
            OrbitPlanetSnapshot(
                slug=p.slug,
                status=status,
                score=m.score if m else 0,
                attempts=m.attempts if m else 0,
            )
        )

    return OrbitSnapshotOut(
        planets=snapshots,
        synced_at=datetime.now(timezone.utc).isoformat(),
    )
