"""管理员端：学生导入、星系/行星管理、API 配额监控。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.galaxy import Galaxy, Planet
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.profile import ProfileExtraction
from app.models.system import ApiUsageLog, SystemSetting
from app.models.user import User
from app.schemas.admin import (
    ApiErrorItem,
    ApiQuotaOut,
    ApiUsageSummary,
    GalaxyBrief,
    GalaxyUpsertRequest,
    ImportStudentsRequest,
    ImportStudentsResponse,
    MaintenanceOut,
    MaintenanceUpdateRequest,
    ModelConfigItem,
    PlanetBrief,
    PlanetUpsertRequest,
    SystemOverviewOut,
    UserAdminItem,
    UserAdminUpdateRequest,
)


async def import_students(session: AsyncSession, req: ImportStudentsRequest) -> ImportStudentsResponse:
    created = skipped = 0
    class_id = req.class_id.strip()
    teacher_id = req.teacher_id.strip()
    if class_id and not teacher_id:
        from app.models.school_class import SchoolClass

        cls = (await session.execute(select(SchoolClass).where(SchoolClass.id == class_id))).scalar_one_or_none()
        if cls:
            teacher_id = cls.teacher_id
    for item in req.students:
        exists = (
            await session.execute(select(User).where(User.username == item.username))
        ).scalar_one_or_none()
        if exists is not None:
            skipped += 1
            continue
        session.add(
            User(
                username=item.username,
                password_hash=hash_password(item.password),
                role="student",
                display_name=item.display_name,
                class_id=class_id,
                teacher_id=teacher_id,
            )
        )
        created += 1
    await session.commit()
    return ImportStudentsResponse(created=created, skipped=skipped)


async def upsert_galaxy(session: AsyncSession, req: GalaxyUpsertRequest) -> Galaxy:
    galaxy = (
        await session.execute(select(Galaxy).where(Galaxy.slug == req.slug))
    ).scalar_one_or_none()
    if galaxy is None:
        galaxy = Galaxy(slug=req.slug)
        session.add(galaxy)
    galaxy.name = req.name
    galaxy.description = req.description
    galaxy.color = req.color
    galaxy.orbit_radius = req.orbit_radius
    galaxy.sort_order = req.sort_order
    await session.commit()
    await session.refresh(galaxy)
    return galaxy


async def upsert_planet(session: AsyncSession, req: PlanetUpsertRequest) -> Planet | None:
    galaxy = (
        await session.execute(select(Galaxy).where(Galaxy.slug == req.galaxy_slug))
    ).scalar_one_or_none()
    if galaxy is None:
        return None
    planet = (
        await session.execute(select(Planet).where(Planet.slug == req.slug))
    ).scalar_one_or_none()
    if planet is None:
        planet = Planet(slug=req.slug, galaxy_id=galaxy.id)
        session.add(planet)
    planet.galaxy_id = galaxy.id
    planet.name = req.name
    planet.description = req.description
    planet.difficulty = req.difficulty
    planet.orbit_index = req.orbit_index
    planet.angle_deg = req.angle_deg
    planet.prerequisites = req.prerequisites
    planet.question_tags = req.question_tags
    await session.commit()
    await session.refresh(planet)
    return planet


async def delete_planet(session: AsyncSession, slug: str) -> bool:
    planet = (await session.execute(select(Planet).where(Planet.slug == slug))).scalar_one_or_none()
    if planet is None:
        return False
    planet_id = planet.id
    await session.execute(delete(PlanetMastery).where(PlanetMastery.planet_id == planet_id))
    await session.execute(delete(ChallengeQuestion).where(ChallengeQuestion.planet_id == planet_id))
    others = (await session.execute(select(Planet))).scalars().all()
    for row in others:
        if slug in (row.prerequisites or []):
            row.prerequisites = [item for item in (row.prerequisites or []) if item != slug]
    await session.delete(planet)
    await session.commit()
    return True


async def list_galaxies(session: AsyncSession) -> list[GalaxyBrief]:
    galaxies = (await session.execute(select(Galaxy).order_by(Galaxy.sort_order, Galaxy.name))).scalars().all()
    planets = (await session.execute(select(Planet))).scalars().all()
    counts: dict[str, int] = {}
    for planet in planets:
        counts[planet.galaxy_id] = counts.get(planet.galaxy_id, 0) + 1
    return [
        GalaxyBrief(
            id=g.id,
            slug=g.slug,
            name=g.name,
            description=g.description,
            planet_count=counts.get(g.id, 0),
            is_active=g.is_active,
        )
        for g in galaxies
    ]


async def list_planets(session: AsyncSession, galaxy_slug: str = "") -> list[PlanetBrief]:
    stmt = select(Planet).order_by(Planet.orbit_index, Planet.name)
    if galaxy_slug:
        galaxy = (await session.execute(select(Galaxy).where(Galaxy.slug == galaxy_slug))).scalar_one_or_none()
        if galaxy is None:
            return []
        stmt = stmt.where(Planet.galaxy_id == galaxy.id)
    planets = (await session.execute(stmt)).scalars().all()
    galaxies = {g.id: g for g in (await session.execute(select(Galaxy))).scalars().all()}
    return [
        PlanetBrief(
            id=p.id,
            slug=p.slug,
            name=p.name,
            galaxy_slug=galaxies.get(p.galaxy_id).slug if galaxies.get(p.galaxy_id) else "",
            galaxy_name=galaxies.get(p.galaxy_id).name if galaxies.get(p.galaxy_id) else "",
            difficulty=p.difficulty,
            orbit_index=p.orbit_index,
        )
        for p in planets
    ]


async def _get_or_create_settings(session: AsyncSession) -> SystemSetting:
    row = (await session.execute(select(SystemSetting).limit(1))).scalar_one_or_none()
    if row is None:
        row = SystemSetting()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def get_maintenance(session: AsyncSession) -> MaintenanceOut:
    row = await _get_or_create_settings(session)
    return MaintenanceOut(enabled=row.maintenance_enabled, message=row.maintenance_message)


async def update_maintenance(session: AsyncSession, req: MaintenanceUpdateRequest) -> MaintenanceOut:
    row = await _get_or_create_settings(session)
    row.maintenance_enabled = req.enabled
    if req.message is not None:
        row.maintenance_message = req.message
    await session.commit()
    await session.refresh(row)
    return MaintenanceOut(enabled=row.maintenance_enabled, message=row.maintenance_message)


async def is_maintenance_enabled(session: AsyncSession) -> tuple[bool, str]:
    row = (await session.execute(select(SystemSetting).limit(1))).scalar_one_or_none()
    if row is None:
        return False, ""
    return bool(row.maintenance_enabled), row.maintenance_message or "系统维护中，请稍后再试"


async def list_users(session: AsyncSession, role: str = "") -> list[UserAdminItem]:
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    rows = (await session.execute(stmt.limit(200))).scalars().all()
    return [
        UserAdminItem(
            id=u.id,
            username=u.username,
            display_name=u.display_name,
            role=u.role,
            class_id=u.class_id,
            teacher_id=u.teacher_id,
            is_active=bool(getattr(u, "is_active", True)),
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in rows
    ]


async def update_user(session: AsyncSession, user_id: str, req: UserAdminUpdateRequest) -> UserAdminItem | None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return None
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.role is not None and req.role in {"student", "teacher", "admin"}:
        user.role = req.role
    await session.commit()
    await session.refresh(user)
    return UserAdminItem(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        class_id=user.class_id,
        teacher_id=user.teacher_id,
        is_active=bool(getattr(user, "is_active", True)),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


async def log_api_usage(
    session: AsyncSession,
    *,
    user_id: str = "",
    endpoint: str = "llm_chat",
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    success: bool = True,
    error_message: str = "",
) -> None:
    session.add(
        ApiUsageLog(
            user_id=user_id or "",
            endpoint=endpoint,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message[:2000],
        )
    )
    await session.commit()


async def list_usage_summary(session: AsyncSession, days: int = 7) -> list[ApiUsageSummary]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await session.execute(
            select(
                ApiUsageLog.endpoint,
                func.count().label("calls"),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(ApiUsageLog.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(ApiUsageLog.completion_tokens), 0).label("completion_tokens"),
            )
            .where(ApiUsageLog.created_at >= since)
            .group_by(ApiUsageLog.endpoint)
            .order_by(desc("tokens"))
        )
    ).all()
    return [
        ApiUsageSummary(
            endpoint=row.endpoint,
            calls=int(row.calls or 0),
            total_tokens=int(row.tokens or 0),
            prompt_tokens=int(row.prompt_tokens or 0),
            completion_tokens=int(row.completion_tokens or 0),
        )
        for row in rows
    ]


async def list_api_errors(session: AsyncSession, limit: int = 50) -> list[ApiErrorItem]:
    rows = (
        await session.execute(
            select(ApiUsageLog)
            .where(ApiUsageLog.success.is_(False))
            .order_by(desc(ApiUsageLog.created_at))
            .limit(limit)
        )
    ).scalars().all()
    return [
        ApiErrorItem(
            id=row.id,
            endpoint=row.endpoint,
            model=row.model,
            user_id=row.user_id,
            error_message=row.error_message,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in rows
    ]


async def system_overview(session: AsyncSession) -> SystemOverviewOut:
    settings = get_settings()
    maintenance = await get_maintenance(session)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    today_calls = (await session.execute(select(func.count()).select_from(ApiUsageLog).where(ApiUsageLog.created_at >= since))).scalar() or 0
    today_tokens = (
        await session.execute(select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0)).where(ApiUsageLog.created_at >= since))
    ).scalar() or 0
    today_errors = (
        await session.execute(
            select(func.count()).select_from(ApiUsageLog).where(ApiUsageLog.created_at >= since, ApiUsageLog.success.is_(False))
        )
    ).scalar() or 0
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar() or 0

    from app.services.ark_vision import ark_vision_available
    from app.services.llm import deepseek_available, doubao_available
    from app.services.seedance_service import seedance_available

    xf_speech_ok = bool(settings.xf_app_id and settings.xf_api_key and settings.xf_api_secret)
    xf_vms_ok = bool(
        (settings.xf_vms_app_id or "").strip()
        and (settings.xf_vms_api_key or "").strip()
        and (settings.xf_vms_api_secret or "").strip()
        and (settings.xf_vms_scene_id or "").strip()
    )
    doubao_chat_model = (
        (settings.ark_chat_model or settings.ark_vision_model or "").strip()
        or settings.ark_vision_foundation_model
    )
    vision_display = settings.ark_vision_foundation_model or settings.ark_vision_model
    if settings.ark_vision_foundation_model and settings.ark_vision_model:
        vision_display = f"{settings.ark_vision_foundation_model} ({settings.ark_vision_model})"
    vms_display = " / ".join(
        part for part in [(settings.xf_vms_avatar_id or "").strip(), (settings.xf_vms_vcn or "").strip()] if part
    )

    models = [
        ModelConfigItem(
            key="deepseek",
            name="DeepSeek 文本",
            model=settings.deepseek_model,
            configured=deepseek_available(),
        ),
        ModelConfigItem(
            key="doubao_chat",
            name="豆包文本（兜底）",
            model=doubao_chat_model,
            configured=doubao_available(),
        ),
        ModelConfigItem(
            key="ark_vision",
            name="豆包视觉",
            model=vision_display,
            configured=ark_vision_available(),
        ),
        ModelConfigItem(
            key="seedance",
            name="Seedance 视频",
            model=settings.ark_seedance_foundation_model or settings.ark_seedance_model,
            configured=seedance_available(),
        ),
        ModelConfigItem(
            key="qwen_image",
            name="千问图像",
            model=settings.qwen_image_model,
            configured=bool(settings.qwen_api_key),
        ),
        ModelConfigItem(
            key="xf_tts",
            name="讯飞 TTS",
            model=settings.xf_tts_vcn,
            configured=xf_speech_ok,
        ),
        ModelConfigItem(
            key="xf_vms",
            name="讯飞虚拟人",
            model=vms_display,
            configured=xf_vms_ok,
        ),
    ]

    return SystemOverviewOut(
        deepseek_configured=bool(settings.deepseek_api_key),
        deepseek_model=settings.deepseek_model,
        models=models,
        maintenance_enabled=maintenance.enabled,
        maintenance_message=maintenance.message,
        today_calls=int(today_calls),
        today_tokens=int(today_tokens),
        today_errors=int(today_errors),
        user_count=int(user_count),
    )


async def reset_user_password(session: AsyncSession, user_id: str) -> tuple[UserAdminItem, str] | None:
    """重置密码并返回一次性明文临时密码。"""
    import secrets
    import string

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return None
    alphabet = string.ascii_letters + string.digits
    temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
    user.password_hash = hash_password(temp_password)
    await session.commit()
    await session.refresh(user)
    item = UserAdminItem(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        class_id=user.class_id,
        teacher_id=user.teacher_id,
        is_active=bool(getattr(user, "is_active", True)),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )
    return item, temp_password


async def batch_set_active(session: AsyncSession, user_ids: list[str], is_active: bool) -> int:
    rows = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    for user in rows:
        user.is_active = is_active
    await session.commit()
    return len(rows)


async def user_admin_detail(session: AsyncSession, user_id: str) -> dict | None:
    """用户详情抽屉：登录历史 + 用量 + Agent 运行 + 学习进度概要。"""
    from app.models.agent_trace import AgentRun
    from app.models.mastery import PlanetMastery
    from app.services.audit import recent_user_logins

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return None
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    calls_7d = (
        await session.execute(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.user_id == user_id, ApiUsageLog.created_at >= week_ago
            )
        )
    ).scalar() or 0
    tokens_7d = (
        await session.execute(
            select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0)).where(
                ApiUsageLog.user_id == user_id, ApiUsageLog.created_at >= week_ago
            )
        )
    ).scalar() or 0
    mastery_total = (
        await session.execute(
            select(func.count()).select_from(PlanetMastery).where(PlanetMastery.user_id == user_id)
        )
    ).scalar() or 0
    mastery_lit = (
        await session.execute(
            select(func.count()).select_from(PlanetMastery).where(
                PlanetMastery.user_id == user_id, PlanetMastery.status == "lit"
            )
        )
    ).scalar() or 0
    agent_rows = (
        await session.execute(
            select(AgentRun).where(AgentRun.user_id == user_id).order_by(desc(AgentRun.created_at)).limit(5)
        )
    ).scalars().all()
    logins = await recent_user_logins(session, user_id, limit=10)
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "class_id": user.class_id,
            "is_active": bool(getattr(user, "is_active", True)),
            "points": user.points,
            "streak_days": user.streak_days,
            "created_at": user.created_at.isoformat() if user.created_at else "",
        },
        "usage_7d": {"calls": int(calls_7d), "tokens": int(tokens_7d)},
        "mastery": {"total": int(mastery_total), "lit": int(mastery_lit)},
        "recent_agent_runs": [
            {
                "id": r.id,
                "scene": r.scene,
                "mode": r.mode,
                "status": r.status,
                "topic": r.topic,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in agent_rows
        ],
        "recent_logins": logins,
    }


async def send_announcement(session: AsyncSession, *, title: str, body: str, role: str = "all") -> int:
    """按角色群发系统公告（复用 user_notifications）。"""
    import uuid as _uuid

    from app.models.notification import UserNotification

    stmt = select(User.id).where(User.is_active.is_(True))
    if role in {"student", "teacher"}:
        stmt = stmt.where(User.role == role)
    user_ids = (await session.execute(stmt)).scalars().all()
    for uid in user_ids:
        session.add(
            UserNotification(
                id=str(_uuid.uuid4()),
                user_id=uid,
                kind="announcement",
                title=title[:120],
                body=body[:4000],
            )
        )
    await session.commit()
    return len(user_ids)


def list_upload_files() -> dict:
    """文件与存储管理：uploads 目录分类汇总 + 文件清单。"""
    from app.core.paths import UPLOADS_DIR

    categories: list[dict] = []
    files: list[dict] = []
    total_size = 0
    if UPLOADS_DIR.is_dir():
        for sub in sorted(UPLOADS_DIR.iterdir()):
            if not sub.is_dir():
                continue
            cat_size = 0
            cat_count = 0
            for path in sub.rglob("*"):
                if not path.is_file():
                    continue
                size = path.stat().st_size
                cat_size += size
                cat_count += 1
                files.append(
                    {
                        "path": path.relative_to(UPLOADS_DIR).as_posix(),
                        "category": sub.name,
                        "size": size,
                        "modified_at": datetime.fromtimestamp(
                            path.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
            categories.append({"name": sub.name, "file_count": cat_count, "total_size": cat_size})
            total_size += cat_size
    files.sort(key=lambda f: f["size"], reverse=True)
    return {"categories": categories, "files": files[:200], "total_size": total_size, "total_files": len(files)}


def delete_upload_file(rel_path: str) -> bool:
    """删除 uploads 下的文件；路径穿越防护。"""
    from app.core.paths import UPLOADS_DIR

    target = (UPLOADS_DIR / rel_path).resolve()
    try:
        target.relative_to(UPLOADS_DIR.resolve())
    except ValueError:
        return False
    if not target.is_file():
        return False
    target.unlink()
    return True


async def export_csv(session: AsyncSession, kind: str, days: int = 30) -> tuple[str, str] | None:
    """导出 CSV：users / usage / audit / login。返回 (filename, content)。"""
    import csv
    import io

    from app.models.ops import AuditLog, LoginLog

    since = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if kind == "users":
        rows = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
        writer.writerow(["id", "username", "display_name", "role", "class_id", "is_active", "created_at"])
        for u in rows:
            writer.writerow(
                [
                    u.id,
                    u.username,
                    u.display_name,
                    u.role,
                    u.class_id,
                    int(bool(getattr(u, "is_active", True))),
                    u.created_at.isoformat() if u.created_at else "",
                ]
            )
    elif kind == "usage":
        rows = (
            await session.execute(
                select(ApiUsageLog).where(ApiUsageLog.created_at >= since).order_by(ApiUsageLog.created_at)
            )
        ).scalars().all()
        writer.writerow(
            ["id", "user_id", "endpoint", "model", "prompt_tokens", "completion_tokens", "total_tokens", "latency_ms", "success", "created_at"]
        )
        for r in rows:
            writer.writerow(
                [
                    r.id,
                    r.user_id,
                    r.endpoint,
                    r.model,
                    r.prompt_tokens,
                    r.completion_tokens,
                    r.total_tokens,
                    r.latency_ms,
                    int(bool(r.success)),
                    r.created_at.isoformat() if r.created_at else "",
                ]
            )
    elif kind == "audit":
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.created_at >= since).order_by(AuditLog.created_at)
            )
        ).scalars().all()
        writer.writerow(["id", "username", "action", "target_type", "target_id", "ip", "created_at"])
        for r in rows:
            writer.writerow(
                [r.id, r.username, r.action, r.target_type, r.target_id, r.ip, r.created_at.isoformat() if r.created_at else ""]
            )
    elif kind == "login":
        rows = (
            await session.execute(
                select(LoginLog).where(LoginLog.created_at >= since).order_by(LoginLog.created_at)
            )
        ).scalars().all()
        writer.writerow(["id", "username", "success", "reason", "ip", "created_at"])
        for r in rows:
            writer.writerow(
                [r.id, r.username, int(bool(r.success)), r.reason, r.ip, r.created_at.isoformat() if r.created_at else ""]
            )
    else:
        return None
    filename = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
    # BOM 便于 Excel 直接打开中文
    return filename, "\ufeff" + buffer.getvalue()


async def api_quota(session: AsyncSession) -> ApiQuotaOut:
    settings = get_settings()
    extractions = (await session.execute(select(func.count()).select_from(ProfileExtraction))).scalar() or 0
    challenges = (await session.execute(select(func.count()).select_from(ChallengeQuestion))).scalar() or 0
    since = datetime.now(timezone.utc) - timedelta(days=7)
    total_tokens = (
        await session.execute(select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0)).where(ApiUsageLog.created_at >= since))
    ).scalar() or 0
    total_calls = (await session.execute(select(func.count()).select_from(ApiUsageLog).where(ApiUsageLog.created_at >= since))).scalar() or 0
    return ApiQuotaOut(
        deepseek_configured=bool(settings.deepseek_api_key),
        deepseek_model=settings.deepseek_model,
        deepseek_base_url=settings.deepseek_base_url,
        total_extractions=extractions,
        total_challenges=challenges,
        total_tokens_7d=int(total_tokens),
        total_calls_7d=int(total_calls),
    )
