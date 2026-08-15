"""运行时 key-value 配置：配额 / 思想防火墙 / 功能开关，带进程内缓存供同步读取。"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.ops import SettingEntry

logger = logging.getLogger(__name__)

# 管理端可编辑项的注册表；job:* 等内部键不在此列
SETTINGS_META: list[dict[str, Any]] = [
    {
        "key": "daily_token_quota",
        "label": "每日 Token 配额上限",
        "type": "int",
        "group": "quota",
        "description": "全站每日 LLM Token 消耗上限，用于告警阈值（0 表示不限制）",
    },
    {
        "key": "deepseek_balance_warn",
        "label": "DeepSeek 余额预警阈值（元）",
        "type": "int",
        "group": "quota",
        "description": "DeepSeek 账户余额低于该金额时生成 warning 告警（0 表示不预警）",
    },
    {
        "key": "shield_use_llm",
        "label": "思想防火墙 LLM 复审",
        "type": "bool",
        "group": "shield",
        "description": "开启后每条 AI 输出额外调用 LLM 审核（更安全但更慢）",
    },
    {
        "key": "shield_extra_words",
        "label": "补充敏感词",
        "type": "text",
        "group": "shield",
        "description": "本地快筛的补充敏感词，逗号或换行分隔",
    },
    {
        "key": "feature_simulation",
        "label": "镜像预演入口",
        "type": "bool",
        "group": "features",
        "description": "是否对学生开放镜像预演（LangGraph handoff）功能",
    },
    {
        "key": "feature_council",
        "label": "平行宇宙入口",
        "type": "bool",
        "group": "features",
        "description": "是否对学生开放平行宇宙（council 多策略）功能",
    },
]

_cache: dict[str, str] = {}
_cache_loaded = False


def _defaults() -> dict[str, str]:
    settings = get_settings()
    return {
        "daily_token_quota": "200000",
        "deepseek_balance_warn": "10",
        "shield_use_llm": "true" if settings.shield_use_llm else "false",
        "shield_extra_words": "",
        "feature_simulation": "true",
        "feature_council": "true",
    }


async def load_cache(session: AsyncSession) -> None:
    """启动或更新后刷新进程内缓存。"""
    global _cache_loaded
    rows = (await session.execute(select(SettingEntry))).scalars().all()
    _cache.clear()
    _cache.update({row.key: row.value for row in rows})
    _cache_loaded = True


def get_str(key: str, default: str | None = None) -> str:
    if key in _cache:
        return _cache[key]
    if default is not None:
        return default
    return _defaults().get(key, "")


def get_bool(key: str, default: bool | None = None) -> bool:
    raw = get_str(key, None if default is None else ("true" if default else "false"))
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get_str(key, str(default)).strip() or default)
    except ValueError:
        return default


async def get_value(session: AsyncSession, key: str) -> str:
    row = (await session.execute(select(SettingEntry).where(SettingEntry.key == key))).scalar_one_or_none()
    if row is not None:
        return row.value
    return _defaults().get(key, "")


async def set_value(session: AsyncSession, key: str, value: str, *, commit: bool = True) -> None:
    row = (await session.execute(select(SettingEntry).where(SettingEntry.key == key))).scalar_one_or_none()
    if row is None:
        row = SettingEntry(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    if commit:
        await session.commit()
    _cache[key] = value


async def list_settings(session: AsyncSession) -> list[dict[str, Any]]:
    """管理端配置中心：注册表 + 当前值。"""
    rows = (await session.execute(select(SettingEntry))).scalars().all()
    current = {row.key: row.value for row in rows}
    defaults = _defaults()
    out: list[dict[str, Any]] = []
    for meta in SETTINGS_META:
        key = meta["key"]
        out.append({**meta, "value": current.get(key, defaults.get(key, "")), "default": defaults.get(key, "")})
    return out


async def update_settings(session: AsyncSession, values: dict[str, str]) -> list[dict[str, Any]]:
    allowed = {meta["key"] for meta in SETTINGS_META}
    for key, value in values.items():
        if key not in allowed:
            continue
        await set_value(session, key, str(value), commit=False)
    await session.commit()
    return await list_settings(session)


def feature_flags() -> dict[str, bool]:
    """暴露给 /system/status 的功能开关（前端按需读取）。"""
    return {
        "simulation": get_bool("feature_simulation", True),
        "council": get_bool("feature_council", True),
    }
