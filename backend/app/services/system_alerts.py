"""系统告警中心：规则引擎生成告警 + 状态流转 + LLM 研判处置建议。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trace import AgentRun
from app.models.ops import LoginLog, SystemAlert
from app.models.system import ApiUsageLog
from app.services import runtime_config
from app.services.llm import extract_json, llm_available, llm_chat_raw

logger = logging.getLogger(__name__)

VALID_STATUS = {"open", "acked", "resolved", "false_positive"}


def _out(row: SystemAlert) -> dict:
    return {
        "id": row.id,
        "level": row.level,
        "category": row.category,
        "title": row.title,
        "detail": row.detail,
        "status": row.status,
        "triage_verdict": row.triage_verdict,
        "triage_note": row.triage_note,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else "",
    }


async def _has_recent_open(session: AsyncSession, category: str, title: str, hours: int = 12) -> bool:
    """同类告警去重：近 N 小时内已有未关闭同标题告警则不再重复生成。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    row = (
        await session.execute(
            select(SystemAlert.id)
            .where(
                SystemAlert.category == category,
                SystemAlert.title == title,
                SystemAlert.status.in_(["open", "acked"]),
                SystemAlert.created_at >= since,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def _emit(
    session: AsyncSession, *, level: str, category: str, title: str, detail: str
) -> SystemAlert | None:
    if await _has_recent_open(session, category, title):
        return None
    alert = SystemAlert(level=level, category=category, title=title, detail=detail)
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    logger.info("system alert emitted: [%s] %s", level, title)
    return alert


async def scan_alerts(session: AsyncSession) -> list[dict]:
    """执行全部告警规则，返回本次新生成的告警。"""
    created: list[dict] = []
    now = datetime.now(timezone.utc)

    # 规则 1：LLM 连续调用失败（最近 15 条 llm 日志中最新的连续失败 >= 3）
    llm_rows = (
        await session.execute(
            select(ApiUsageLog.success, ApiUsageLog.error_message)
            .where(ApiUsageLog.endpoint.like("llm%"))
            .order_by(desc(ApiUsageLog.created_at))
            .limit(15)
        )
    ).all()
    consecutive = 0
    last_error = ""
    for row in llm_rows:
        if row.success:
            break
        consecutive += 1
        last_error = last_error or (row.error_message or "")
    if consecutive >= 3:
        alert = await _emit(
            session,
            level="critical",
            category="llm_failure",
            title=f"LLM 连续调用失败 {consecutive} 次",
            detail=f"最近一次错误：{last_error[:500] or '未知'}。请检查 DeepSeek / 豆包 API Key、余额与网络。",
        )
        if alert:
            created.append(_out(alert))

    # 规则 2：当日 token 用量超配额阈值
    quota = runtime_config.get_int("daily_token_quota", 200000)
    if quota > 0:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        used = (
            await session.execute(
                select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0)).where(
                    ApiUsageLog.created_at >= day_start
                )
            )
        ).scalar() or 0
        ratio = used / quota
        if ratio >= 1.0:
            alert = await _emit(
                session,
                level="critical",
                category="token_quota",
                title="当日 Token 用量已超配额",
                detail=f"今日已消耗 {int(used)} tokens，配额 {quota}（{ratio:.0%}）。请评估是否临时限流或调高配额。",
            )
        elif ratio >= 0.8:
            alert = await _emit(
                session,
                level="warning",
                category="token_quota",
                title="当日 Token 用量达配额 80%",
                detail=f"今日已消耗 {int(used)} tokens，配额 {quota}（{ratio:.0%}）。",
            )
        else:
            alert = None
        if alert:
            created.append(_out(alert))

    # 规则 3：Agent 运行失败率突增（近 24h，样本 >= 5 且失败率 >= 30%）
    day_ago = now - timedelta(hours=24)
    agent_rows = (
        await session.execute(
            select(AgentRun.status, func.count().label("n"))
            .where(AgentRun.created_at >= day_ago)
            .group_by(AgentRun.status)
        )
    ).all()
    total_runs = sum(int(r.n) for r in agent_rows)
    failed_runs = sum(int(r.n) for r in agent_rows if r.status in {"failed", "error"})
    if total_runs >= 5 and failed_runs / total_runs >= 0.3:
        alert = await _emit(
            session,
            level="warning",
            category="agent_failure",
            title=f"Agent 运行失败率 {failed_runs}/{total_runs}",
            detail="近 24 小时 Agent run 失败率超过 30%，建议到 /admin/agents 回放失败步骤定位原因。",
        )
        if alert:
            created.append(_out(alert))

    # 规则 4：DeepSeek 余额低于阈值 / 账户不可用（快照由告警扫描循环顺带刷新）
    from app.services.llm import deepseek_available
    from app.services.provider_status import get_balance_snapshot

    balance = get_balance_snapshot()
    if deepseek_available() and balance.get("ok"):
        threshold = runtime_config.get_int("deepseek_balance_warn", 10)
        total = float(balance.get("total_balance", 0) or 0)
        currency = balance.get("currency", "CNY")
        if not balance.get("is_available", True):
            alert = await _emit(
                session,
                level="critical",
                category="provider_balance",
                title="DeepSeek 账户不可用（余额耗尽）",
                detail=f"官方余额接口返回 is_available=false，当前余额 {total} {currency}。请尽快充值，否则全部智能体功能将降级到兜底方案。",
            )
            if alert:
                created.append(_out(alert))
        elif threshold > 0 and total < threshold:
            alert = await _emit(
                session,
                level="warning",
                category="provider_balance",
                title=f"DeepSeek 余额低于预警阈值（{total} {currency}）",
                detail=f"当前余额 {total} {currency}，低于预警阈值 {threshold} 元。请在管理端「设置 → API 密钥管理」检查或提前充值。",
            )
            if alert:
                created.append(_out(alert))

    # 规则 5：同一账号短时间多次登录失败（近 30 分钟 >= 5 次）
    half_hour = now - timedelta(minutes=30)
    login_rows = (
        await session.execute(
            select(LoginLog.username, func.count().label("fails"))
            .where(LoginLog.created_at >= half_hour, LoginLog.success.is_(False))
            .group_by(LoginLog.username)
            .having(func.count() >= 5)
        )
    ).all()
    for row in login_rows:
        alert = await _emit(
            session,
            level="warning",
            category="login_security",
            title=f"账号 {row.username} 半小时内登录失败 {int(row.fails)} 次",
            detail="可能是暴力破解或用户遗忘密码。可在用户管理中核实账号状态，必要时停用或重置密码。",
        )
        if alert:
            created.append(_out(alert))

    return created


async def list_alerts(
    session: AsyncSession, *, status: str = "", level: str = "", limit: int = 100
) -> dict:
    stmt = select(SystemAlert)
    if status:
        stmt = stmt.where(SystemAlert.status == status)
    if level:
        stmt = stmt.where(SystemAlert.level == level)
    rows = (
        await session.execute(stmt.order_by(desc(SystemAlert.created_at)).limit(min(limit, 300)))
    ).scalars().all()
    open_count = (
        await session.execute(
            select(func.count()).select_from(SystemAlert).where(SystemAlert.status == "open")
        )
    ).scalar() or 0
    return {"items": [_out(r) for r in rows], "open_count": int(open_count)}


async def update_alert(session: AsyncSession, alert_id: str, status: str) -> dict | None:
    if status not in VALID_STATUS:
        return None
    alert = (
        await session.execute(select(SystemAlert).where(SystemAlert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        return None
    alert.status = status
    alert.resolved_at = (
        datetime.now(timezone.utc) if status in {"resolved", "false_positive"} else None
    )
    await session.commit()
    await session.refresh(alert)
    return _out(alert)


TRIAGE_SYSTEM = """你是 SparkOrbit 教育平台的安全运营研判 Agent。
管理员会给你一条系统告警与相关上下文数据，请判断它是否真阳性并给出处置建议。
严格返回 JSON：
{"verdict": "true_positive|false_positive|uncertain", "analysis": "研判分析（100 字内）", "actions": ["处置建议 1", "处置建议 2"]}"""


async def _triage_context(session: AsyncSession, alert: SystemAlert) -> dict:
    """按告警类别捞取真实数据供 LLM 研判（呼应「能调用真实数据」）。"""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    ctx: dict = {}
    if alert.category == "llm_failure":
        rows = (
            await session.execute(
                select(ApiUsageLog.endpoint, ApiUsageLog.success, ApiUsageLog.error_message, ApiUsageLog.created_at)
                .where(ApiUsageLog.endpoint.like("llm%"))
                .order_by(desc(ApiUsageLog.created_at))
                .limit(10)
            )
        ).all()
        ctx["recent_llm_calls"] = [
            {
                "endpoint": r.endpoint,
                "success": bool(r.success),
                "error": (r.error_message or "")[:200],
                "at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
    elif alert.category == "token_quota":
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        rows = (
            await session.execute(
                select(ApiUsageLog.endpoint, func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"))
                .where(ApiUsageLog.created_at >= day_start)
                .group_by(ApiUsageLog.endpoint)
                .order_by(desc("tokens"))
                .limit(8)
            )
        ).all()
        ctx["today_top_endpoints"] = [{"endpoint": r.endpoint, "tokens": int(r.tokens)} for r in rows]
        ctx["daily_quota"] = runtime_config.get_int("daily_token_quota", 200000)
    elif alert.category == "agent_failure":
        rows = (
            await session.execute(
                select(AgentRun.scene, AgentRun.mode, AgentRun.status, AgentRun.error_message)
                .where(AgentRun.created_at >= day_ago, AgentRun.status.in_(["failed", "error"]))
                .order_by(desc(AgentRun.created_at))
                .limit(8)
            )
        ).all()
        ctx["failed_runs"] = [
            {"scene": r.scene, "mode": r.mode, "status": r.status, "error": (r.error_message or "")[:200]}
            for r in rows
        ]
    elif alert.category == "provider_balance":
        from app.services.provider_status import get_balance_snapshot

        ctx["balance_snapshot"] = get_balance_snapshot()
        ctx["balance_warn_threshold"] = runtime_config.get_int("deepseek_balance_warn", 10)
    elif alert.category == "login_security":
        rows = (
            await session.execute(
                select(LoginLog.username, LoginLog.success, LoginLog.ip, LoginLog.reason, LoginLog.created_at)
                .where(LoginLog.created_at >= now - timedelta(hours=2), LoginLog.success.is_(False))
                .order_by(desc(LoginLog.created_at))
                .limit(15)
            )
        ).all()
        ctx["recent_failed_logins"] = [
            {
                "username": r.username,
                "ip": r.ip,
                "reason": r.reason,
                "at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
    return ctx


async def triage_alert(session: AsyncSession, alert_id: str, *, user_id: str = "") -> dict | None:
    """LLM 研判：真阳性判断 + 处置建议，写回 triage 字段。"""
    alert = (
        await session.execute(select(SystemAlert).where(SystemAlert.id == alert_id))
    ).scalar_one_or_none()
    if alert is None:
        return None
    if not llm_available():
        alert.triage_verdict = "uncertain"
        alert.triage_note = "LLM 未配置，无法自动研判。请人工核查告警详情。"
        await session.commit()
        await session.refresh(alert)
        return _out(alert)

    context = await _triage_context(session, alert)
    payload = {
        "alert": {
            "level": alert.level,
            "category": alert.category,
            "title": alert.title,
            "detail": alert.detail,
            "created_at": alert.created_at.isoformat() if alert.created_at else "",
        },
        "context": context,
    }
    raw = await llm_chat_raw(
        [
            {"role": "system", "content": TRIAGE_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2,
        response_json=True,
        timeout=45.0,
        user_id=user_id,
        endpoint="admin_alert_triage",
    )
    data = extract_json(raw or "") or {}
    verdict = str(data.get("verdict", "uncertain"))
    if verdict not in {"true_positive", "false_positive", "uncertain"}:
        verdict = "uncertain"
    analysis = str(data.get("analysis", "")) or "模型未返回有效研判结果，请人工核查。"
    actions = [str(a) for a in data.get("actions", []) if str(a).strip()]
    note_lines = [f"**研判分析**：{analysis}"]
    if actions:
        note_lines.append("**处置建议**：")
        note_lines.extend(f"{i}. {a}" for i, a in enumerate(actions, 1))
    alert.triage_verdict = verdict
    alert.triage_note = "\n".join(note_lines)
    await session.commit()
    await session.refresh(alert)
    return _out(alert)
