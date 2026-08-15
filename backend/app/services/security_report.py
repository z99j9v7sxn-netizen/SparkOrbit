"""安全日报：数据汇聚（规则层）+ LLM 摘要（可降级），落库 security_reports。"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trace import AgentRun
from app.models.ops import Feedback, LoginLog, SecurityReport, SystemAlert
from app.models.system import ApiUsageLog
from app.models.user import User
from app.services.llm import llm_available, llm_chat_raw

logger = logging.getLogger(__name__)


def _day_bounds(report_date: str) -> tuple[datetime, datetime]:
    day = date.fromisoformat(report_date)
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


async def aggregate_daily(session: AsyncSession, report_date: str) -> dict:
    """汇聚指定日期（UTC）的运营与安全指标，永远可用的规则层。"""
    start, end = _day_bounds(report_date)

    calls = (
        await session.execute(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.created_at >= start, ApiUsageLog.created_at < end
            )
        )
    ).scalar() or 0
    errors = (
        await session.execute(
            select(func.count()).select_from(ApiUsageLog).where(
                ApiUsageLog.created_at >= start,
                ApiUsageLog.created_at < end,
                ApiUsageLog.success.is_(False),
            )
        )
    ).scalar() or 0
    tokens = (
        await session.execute(
            select(func.coalesce(func.sum(ApiUsageLog.total_tokens), 0)).where(
                ApiUsageLog.created_at >= start, ApiUsageLog.created_at < end
            )
        )
    ).scalar() or 0
    active_users = (
        await session.execute(
            select(func.count(func.distinct(ApiUsageLog.user_id))).where(
                ApiUsageLog.created_at >= start,
                ApiUsageLog.created_at < end,
                ApiUsageLog.user_id != "",
            )
        )
    ).scalar() or 0
    top_endpoints = (
        await session.execute(
            select(
                ApiUsageLog.endpoint,
                func.count().label("calls"),
                func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
            )
            .where(ApiUsageLog.created_at >= start, ApiUsageLog.created_at < end)
            .group_by(ApiUsageLog.endpoint)
            .order_by(desc("tokens"))
            .limit(5)
        )
    ).all()

    login_ok = (
        await session.execute(
            select(func.count()).select_from(LoginLog).where(
                LoginLog.created_at >= start, LoginLog.created_at < end, LoginLog.success.is_(True)
            )
        )
    ).scalar() or 0
    login_fail = (
        await session.execute(
            select(func.count()).select_from(LoginLog).where(
                LoginLog.created_at >= start, LoginLog.created_at < end, LoginLog.success.is_(False)
            )
        )
    ).scalar() or 0

    agent_rows = (
        await session.execute(
            select(AgentRun.mode, AgentRun.status, func.count().label("n"))
            .where(AgentRun.created_at >= start, AgentRun.created_at < end)
            .group_by(AgentRun.mode, AgentRun.status)
        )
    ).all()
    agent_by_mode: dict[str, dict[str, int]] = {}
    for row in agent_rows:
        bucket = agent_by_mode.setdefault(row.mode, {"total": 0, "failed": 0})
        bucket["total"] += int(row.n)
        if row.status in {"failed", "error"}:
            bucket["failed"] += int(row.n)

    alerts_created = (
        await session.execute(
            select(func.count()).select_from(SystemAlert).where(
                SystemAlert.created_at >= start, SystemAlert.created_at < end
            )
        )
    ).scalar() or 0
    alerts_resolved = (
        await session.execute(
            select(func.count()).select_from(SystemAlert).where(
                SystemAlert.resolved_at >= start, SystemAlert.resolved_at < end
            )
        )
    ).scalar() or 0
    alerts_open = (
        await session.execute(
            select(func.count()).select_from(SystemAlert).where(SystemAlert.status == "open")
        )
    ).scalar() or 0

    new_users = (
        await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= start, User.created_at < end)
        )
    ).scalar() or 0
    new_feedback = (
        await session.execute(
            select(func.count()).select_from(Feedback).where(
                Feedback.created_at >= start, Feedback.created_at < end
            )
        )
    ).scalar() or 0

    return {
        "report_date": report_date,
        "api": {
            "calls": int(calls),
            "errors": int(errors),
            "error_rate": round(int(errors) / int(calls), 4) if calls else 0,
            "tokens": int(tokens),
            "top_endpoints": [
                {"endpoint": r.endpoint, "calls": int(r.calls), "tokens": int(r.tokens)} for r in top_endpoints
            ],
        },
        "login": {"success": int(login_ok), "failed": int(login_fail)},
        "agents": agent_by_mode,
        "alerts": {"created": int(alerts_created), "resolved": int(alerts_resolved), "open_now": int(alerts_open)},
        "users": {"active": int(active_users), "new": int(new_users)},
        "feedback": {"new": int(new_feedback)},
    }


def _rule_markdown(data: dict) -> str:
    """LLM 不可用时的纯规则模板日报。"""
    api = data["api"]
    login = data["login"]
    alerts = data["alerts"]
    users = data["users"]
    lines = [
        f"# 安全运营日报 · {data['report_date']}",
        "",
        "## 总体态势",
        f"- API 调用 {api['calls']} 次，失败 {api['errors']} 次（错误率 {api['error_rate']:.1%}），消耗 {api['tokens']} tokens",
        f"- 活跃用户 {users['active']} 人，新注册 {users['new']} 人",
        f"- 登录成功 {login['success']} 次，失败 {login['failed']} 次",
        f"- 新增告警 {alerts['created']} 条，处置 {alerts['resolved']} 条，当前待处理 {alerts['open_now']} 条",
        "",
        "## 重点风险",
    ]
    risks: list[str] = []
    if api["calls"] and api["error_rate"] >= 0.1:
        risks.append(f"- API 错误率 {api['error_rate']:.1%} 偏高，建议检查接口异常页定位失败端点")
    if login["failed"] >= 10:
        risks.append(f"- 登录失败 {login['failed']} 次，建议核查登录安全日志中的异常账号")
    if alerts["open_now"] > 0:
        risks.append(f"- 仍有 {alerts['open_now']} 条告警未处置，请到告警中心跟进")
    for mode, stat in data.get("agents", {}).items():
        if stat["total"] and stat["failed"] / stat["total"] >= 0.3:
            risks.append(f"- Agent 模式 {mode} 失败 {stat['failed']}/{stat['total']}，建议回放失败步骤")
    lines.extend(risks or ["- 无明显风险，系统运行平稳"])
    lines += [
        "",
        "## 处置建议",
        "- 每日跟进告警中心待处理项，及时标记误报",
        "- Token 用量接近配额时评估限流或扩容",
        "",
        "> 本日报由规则模板生成（LLM 未配置或调用失败）。",
    ]
    return "\n".join(lines)


REPORT_SYSTEM = """你是 SparkOrbit 教育平台的安全运营分析师。
根据给定的当日运营与安全 JSON 数据，撰写一份结构化 Markdown 安全日报，要求：
1. 一级标题：`# 安全运营日报 · <日期>`
2. 依次包含三个二级标题：`## 总体态势`、`## 重点风险`、`## 处置建议`
3. 数据必须忠实于输入 JSON，不得编造数字；风险按严重程度排序；建议要具体可执行
4. 全文 300 字以内，直接输出 Markdown，不要代码块包裹"""


async def generate_report(
    session: AsyncSession, report_date: str, *, force: bool = False, user_id: str = ""
) -> dict:
    existing = (
        await session.execute(select(SecurityReport).where(SecurityReport.report_date == report_date))
    ).scalar_one_or_none()
    if existing is not None and not force:
        return _out(existing)

    data = await aggregate_daily(session, report_date)
    markdown = ""
    generated_by = "rule"
    if llm_available():
        raw = await llm_chat_raw(
            [
                {"role": "system", "content": REPORT_SYSTEM},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
            ],
            temperature=0.3,
            timeout=60.0,
            user_id=user_id,
            endpoint="admin_security_report",
        )
        if raw and raw.strip():
            markdown = raw.strip()
            generated_by = "llm"
    if not markdown:
        markdown = _rule_markdown(data)

    if existing is None:
        existing = SecurityReport(report_date=report_date)
        session.add(existing)
    existing.summary = data
    existing.markdown_content = markdown
    existing.generated_by = generated_by
    await session.commit()
    await session.refresh(existing)
    return _out(existing)


def _out(row: SecurityReport) -> dict:
    return {
        "id": row.id,
        "report_date": row.report_date,
        "summary": row.summary or {},
        "markdown_content": row.markdown_content,
        "generated_by": row.generated_by,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def list_reports(session: AsyncSession, limit: int = 30) -> list[dict]:
    rows = (
        await session.execute(
            select(SecurityReport).order_by(desc(SecurityReport.report_date)).limit(limit)
        )
    ).scalars().all()
    out = []
    for row in rows:
        item = _out(row)
        item["markdown_content"] = ""  # 列表不带全文，减小载荷
        out.append(item)
    return out


async def get_report(session: AsyncSession, report_date: str) -> dict | None:
    row = (
        await session.execute(select(SecurityReport).where(SecurityReport.report_date == report_date))
    ).scalar_one_or_none()
    return _out(row) if row else None
