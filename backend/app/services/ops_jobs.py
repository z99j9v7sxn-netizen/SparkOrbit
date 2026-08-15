"""安全运营后台任务：定时告警扫描 + 每日安全日报，心跳写入 setting_entries。"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from app.db.session import AsyncSessionLocal
from app.services import runtime_config

logger = logging.getLogger(__name__)

ALERT_SCAN_INTERVAL = 600  # 10 分钟
REPORT_CHECK_INTERVAL = 1800  # 每 30 分钟检查昨日日报是否已生成
INTERVIEW_MEDIA_INTERVAL = 21600  # 每 6 小时清理过期面试媒体

JOBS_META = [
    {"id": "alert_scan", "label": "告警规则扫描", "interval": "每 10 分钟"},
    {"id": "daily_report", "label": "安全日报生成", "interval": "每日（生成前一日）"},
    {"id": "interview_media", "label": "面试媒体 30 天清理", "interval": "每 6 小时"},
]

_tasks: list[asyncio.Task] = []


async def _heartbeat(job_id: str, ok: bool, detail: str = "") -> None:
    try:
        async with AsyncSessionLocal() as session:
            await runtime_config.set_value(
                session,
                f"job:{job_id}",
                json.dumps(
                    {
                        "last_run": datetime.now(timezone.utc).isoformat(),
                        "ok": ok,
                        "detail": detail[:300],
                    },
                    ensure_ascii=False,
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("job heartbeat write failed (%s): %s", job_id, exc)


async def _alert_scan_loop() -> None:
    from app.services.llm import deepseek_available
    from app.services.provider_status import refresh_deepseek_balance
    from app.services.system_alerts import scan_alerts

    while True:
        try:
            # 顺带刷新 DeepSeek 余额快照，供余额预警规则与管理端卡片使用
            if deepseek_available():
                try:
                    async with AsyncSessionLocal() as session:
                        await refresh_deepseek_balance(session)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("deepseek balance refresh failed: %s", exc)
            async with AsyncSessionLocal() as session:
                created = await scan_alerts(session)
            await _heartbeat("alert_scan", True, f"新增告警 {len(created)} 条")
        except Exception as exc:  # noqa: BLE001
            logger.warning("alert scan loop error: %s", exc)
            await _heartbeat("alert_scan", False, str(exc))
        await asyncio.sleep(ALERT_SCAN_INTERVAL)


async def _daily_report_loop() -> None:
    from app.services.security_report import generate_report, get_report

    while True:
        try:
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
            async with AsyncSessionLocal() as session:
                existing = await get_report(session, yesterday)
                if existing is None:
                    report = await generate_report(session, yesterday)
                    await _heartbeat(
                        "daily_report", True, f"已生成 {yesterday} 日报（{report['generated_by']}）"
                    )
                else:
                    await _heartbeat("daily_report", True, f"{yesterday} 日报已存在，跳过")
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily report loop error: %s", exc)
            await _heartbeat("daily_report", False, str(exc))
        await asyncio.sleep(REPORT_CHECK_INTERVAL)


async def _interview_media_loop() -> None:
    from app.services.interview_service import purge_expired_interview_media

    while True:
        try:
            async with AsyncSessionLocal() as session:
                cleared = await purge_expired_interview_media(session)
            await _heartbeat("interview_media", True, f"清理过期媒体 {cleared} 条")
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview media purge error: %s", exc)
            await _heartbeat("interview_media", False, str(exc))
        await asyncio.sleep(INTERVIEW_MEDIA_INTERVAL)


async def _bootstrap() -> None:
    """启动时加载运行时配置缓存。"""
    try:
        async with AsyncSessionLocal() as session:
            await runtime_config.load_cache(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("runtime config cache load failed: %s", exc)


def start_background_jobs() -> None:
    """在 FastAPI startup 中调用；幂等。"""
    if _tasks:
        return
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(_bootstrap()))
    _tasks.append(loop.create_task(_alert_scan_loop()))
    _tasks.append(loop.create_task(_daily_report_loop()))
    _tasks.append(loop.create_task(_interview_media_loop()))
    logger.info("ops background jobs started: alert_scan / daily_report / interview_media")


async def job_status() -> list[dict]:
    """管理端心跳查询。"""
    out: list[dict] = []
    async with AsyncSessionLocal() as session:
        for meta in JOBS_META:
            raw = await runtime_config.get_value(session, f"job:{meta['id']}")
            info: dict = {}
            if raw:
                try:
                    info = json.loads(raw)
                except json.JSONDecodeError:
                    info = {}
            out.append(
                {
                    **meta,
                    "last_run": info.get("last_run", ""),
                    "ok": bool(info.get("ok", False)) if info else False,
                    "detail": info.get("detail", "尚未执行"),
                }
            )
    return out
