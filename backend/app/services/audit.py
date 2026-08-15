"""操作审计与登录日志：埋点写入 + 管理端查询。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops import AuditLog, LoginLog
from app.models.user import User

logger = logging.getLogger(__name__)


def client_meta(request: Request | None) -> tuple[str, str]:
    if request is None:
        return "", ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "")
    user_agent = (request.headers.get("user-agent") or "")[:250]
    return ip, user_agent


async def record_audit(
    session: AsyncSession,
    *,
    user: User | None,
    action: str,
    target_type: str = "",
    target_id: str = "",
    detail: dict | None = None,
    request: Request | None = None,
) -> None:
    """记录管理员敏感操作；审计失败不影响业务。"""
    try:
        ip, user_agent = client_meta(request)
        session.add(
            AuditLog(
                user_id=user.id if user else "",
                username=user.username if user else "",
                action=action,
                target_type=target_type,
                target_id=str(target_id)[:120],
                detail=detail or {},
                ip=ip,
                user_agent=user_agent,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_audit failed: %s", exc)


async def record_login(
    session: AsyncSession,
    *,
    user_id: str,
    username: str,
    success: bool,
    reason: str = "",
    request: Request | None = None,
) -> None:
    try:
        ip, user_agent = client_meta(request)
        session.add(
            LoginLog(
                user_id=user_id,
                username=username[:60],
                success=success,
                reason=reason[:120],
                ip=ip,
                user_agent=user_agent,
            )
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("record_login failed: %s", exc)


def _audit_out(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": row.username,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "detail": row.detail or {},
        "ip": row.ip,
        "user_agent": row.user_agent,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _login_out(row: LoginLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": row.username,
        "success": bool(row.success),
        "reason": row.reason,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def list_audit_logs(
    session: AsyncSession,
    *,
    action: str = "",
    username: str = "",
    days: int = 7,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    stmt = select(AuditLog).where(AuditLog.created_at >= since)
    count_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if username:
        stmt = stmt.where(AuditLog.username == username)
        count_stmt = count_stmt.where(AuditLog.username == username)
    total = (await session.execute(count_stmt)).scalar() or 0
    rows = (
        await session.execute(stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(min(limit, 200)))
    ).scalars().all()
    actions = (
        await session.execute(select(AuditLog.action).where(AuditLog.created_at >= since).distinct())
    ).scalars().all()
    return {"total": int(total), "items": [_audit_out(r) for r in rows], "actions": sorted(actions)}


async def list_login_logs(
    session: AsyncSession,
    *,
    username: str = "",
    success: str = "",
    days: int = 7,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    stmt = select(LoginLog).where(LoginLog.created_at >= since)
    count_stmt = select(func.count()).select_from(LoginLog).where(LoginLog.created_at >= since)
    if username:
        stmt = stmt.where(LoginLog.username == username)
        count_stmt = count_stmt.where(LoginLog.username == username)
    if success in {"true", "false"}:
        flag = success == "true"
        stmt = stmt.where(LoginLog.success.is_(flag))
        count_stmt = count_stmt.where(LoginLog.success.is_(flag))
    total = (await session.execute(count_stmt)).scalar() or 0
    rows = (
        await session.execute(stmt.order_by(desc(LoginLog.created_at)).offset(offset).limit(min(limit, 200)))
    ).scalars().all()
    # 近 1 小时连续失败账号（管理端标红）
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    risky_rows = (
        await session.execute(
            select(LoginLog.username, func.count().label("fails"))
            .where(LoginLog.created_at >= hour_ago, LoginLog.success.is_(False))
            .group_by(LoginLog.username)
            .having(func.count() >= 5)
        )
    ).all()
    return {
        "total": int(total),
        "items": [_login_out(r) for r in rows],
        "risky_accounts": [{"username": r.username, "fails": int(r.fails)} for r in risky_rows],
    }


async def recent_user_logins(session: AsyncSession, user_id: str, limit: int = 10) -> list[dict]:
    rows = (
        await session.execute(
            select(LoginLog).where(LoginLog.user_id == user_id).order_by(desc(LoginLog.created_at)).limit(limit)
        )
    ).scalars().all()
    return [_login_out(r) for r in rows]
