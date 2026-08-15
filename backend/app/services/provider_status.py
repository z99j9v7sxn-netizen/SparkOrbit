"""Provider 状态服务：DeepSeek 余额查询/缓存、平台列表（掩码 Key）、连通性测试、在线换 Key。"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import runtime_config
from app.services.llm import conf_source, resolve_conf

logger = logging.getLogger(__name__)

BALANCE_CACHE_KEY = "provider:deepseek:balance"

# 平台注册表：key_conf/model_conf 对应 OVERRIDABLE_CONF 中可在线覆盖的配置名
PROVIDERS_META: list[dict[str, Any]] = [
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "description": "全系统智能体大脑（文本对话 / 研判 / 生成）",
        "key_conf": "deepseek_api_key",
        "model_conf": "deepseek_model",
        "balance_supported": True,
        "editable": True,
    },
    {
        "id": "doubao",
        "label": "豆包（火山方舟）",
        "description": "文本兜底 + 视觉理解 + Seedance 视频生成",
        "key_conf": "ark_api_key",
        "model_conf": "ark_chat_model",
        "balance_supported": False,
        "editable": True,
    },
    {
        "id": "qwen",
        "label": "通义千问",
        "description": "自拍卡通化（DashScope 多模态）",
        "key_conf": "qwen_api_key",
        "model_conf": "",
        "balance_supported": False,
        "editable": True,
    },
    {
        "id": "xunfei",
        "label": "讯飞",
        "description": "语音听写 / 口语评测 / TTS / 数字人（AppId+Secret 三元组，仅 .env 配置）",
        "key_conf": "",
        "model_conf": "",
        "balance_supported": False,
        "editable": False,
    },
]


def mask_key(key: str) -> str:
    """掩码显示：保留前缀与尾 4 位，永不返回明文。"""
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}***{key[-4:]}"


def _meta(provider: str) -> Optional[dict[str, Any]]:
    return next((m for m in PROVIDERS_META if m["id"] == provider), None)


async def fetch_deepseek_balance() -> dict[str, Any]:
    """调 DeepSeek 官方余额接口，返回解析后的快照（不含缓存逻辑）。"""
    api_key = resolve_conf("deepseek_api_key")
    if not api_key:
        return {"ok": False, "error": "未配置 DeepSeek API Key"}
    base = get_settings().deepseek_base_url.rstrip("/")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base}/user/balance",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code != 200:
            return {
                "ok": False,
                "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                "latency_ms": latency_ms,
            }
        data = resp.json()
        infos = data.get("balance_infos") or []
        first = infos[0] if infos else {}
        return {
            "ok": True,
            "is_available": bool(data.get("is_available", False)),
            "total_balance": float(first.get("total_balance", 0) or 0),
            "granted_balance": float(first.get("granted_balance", 0) or 0),
            "topped_up_balance": float(first.get("topped_up_balance", 0) or 0),
            "currency": str(first.get("currency", "CNY")),
            "latency_ms": latency_ms,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("deepseek balance fetch failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300]}


async def refresh_deepseek_balance(session: AsyncSession) -> dict[str, Any]:
    """刷新余额快照并缓存到 setting_entries（含 checked_at）。"""
    snapshot = await fetch_deepseek_balance()
    snapshot["checked_at"] = datetime.now(timezone.utc).isoformat()
    await runtime_config.set_value(
        session, BALANCE_CACHE_KEY, json.dumps(snapshot, ensure_ascii=False)
    )
    return snapshot


def get_balance_snapshot() -> dict[str, Any]:
    """读取缓存的余额快照（进程内缓存，随 set_value 更新）。"""
    raw = runtime_config.get_str(BALANCE_CACHE_KEY, "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _provider_out(meta: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    out: dict[str, Any] = {
        "id": meta["id"],
        "label": meta["label"],
        "description": meta["description"],
        "balance_supported": meta["balance_supported"],
        "editable": meta["editable"],
        "configured": False,
        "key_masked": "",
        "key_source": "none",
        "model": "",
        "model_source": "none",
        "balance": None,
    }
    if meta["id"] == "xunfei":
        out["configured"] = bool(settings.xf_app_id and settings.xf_api_key)
        out["key_masked"] = mask_key(settings.xf_api_key)
        out["key_source"] = "env" if out["configured"] else "none"
        return out
    key_conf = meta["key_conf"]
    key = resolve_conf(key_conf)
    out["configured"] = bool(key)
    out["key_masked"] = mask_key(key)
    out["key_source"] = conf_source(key_conf)
    if meta["model_conf"]:
        out["model"] = resolve_conf(meta["model_conf"])
        out["model_source"] = conf_source(meta["model_conf"])
    elif meta["id"] == "qwen":
        out["model"] = settings.qwen_image_model
        out["model_source"] = "env"
    if meta["id"] == "deepseek":
        out["balance"] = get_balance_snapshot() or None
        out["balance_warn_threshold"] = runtime_config.get_int("deepseek_balance_warn", 10)
    return out


async def list_providers(session: AsyncSession) -> list[dict[str, Any]]:
    """平台列表：配置状态、掩码 Key、来源、模型、余额快照。"""
    _ = session
    return [_provider_out(meta) for meta in PROVIDERS_META]


async def update_provider(
    session: AsyncSession,
    provider: str,
    *,
    api_key: str = "",
    model: str = "",
) -> dict[str, Any]:
    """在线更换 Key / 模型：写 override:* 键；客户端按 Key 值缓存会自动重建。

    返回 {"ok": bool, "error": str, "provider": {...}}；调用方负责审计。
    """
    meta = _meta(provider)
    if meta is None or not meta["editable"]:
        return {"ok": False, "error": "该平台不支持在线修改"}
    api_key = (api_key or "").strip()
    model = (model or "").strip()
    if not api_key and not model:
        return {"ok": False, "error": "未提供任何要更新的字段"}
    if api_key:
        await runtime_config.set_value(
            session, f"override:{meta['key_conf']}", api_key, commit=False
        )
    if model and meta["model_conf"]:
        await runtime_config.set_value(
            session, f"override:{meta['model_conf']}", model, commit=False
        )
    await session.commit()
    return {"ok": True, "error": "", "provider": _provider_out(meta)}


async def _test_deepseek() -> dict[str, Any]:
    balance = await fetch_deepseek_balance()
    if not balance.get("ok"):
        return {"ok": False, "detail": f"余额接口失败：{balance.get('error', '未知错误')}"}
    from app.services.llm import _get_deepseek_client  # noqa: PLC0415

    client = _get_deepseek_client()
    if client is None:
        return {"ok": False, "detail": "客户端不可用"}
    started = time.perf_counter()
    resp = await client.chat.completions.create(
        model=resolve_conf("deepseek_model"),
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=4,
        timeout=20.0,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    _ = resp
    avail = "账户可用" if balance.get("is_available") else "账户不可用（余额耗尽）"
    return {
        "ok": True,
        "latency_ms": latency_ms,
        "detail": f"对话测试通过（{latency_ms}ms）；{avail}，余额 {balance.get('total_balance', 0)} {balance.get('currency', 'CNY')}",
    }


async def _test_doubao() -> dict[str, Any]:
    from app.services.llm import _ark_chat_model_id, _get_ark_client  # noqa: PLC0415

    client = _get_ark_client()
    model = _ark_chat_model_id()
    if client is None or not model:
        return {"ok": False, "detail": "豆包未配置（需要 ARK_API_KEY 与接入点 ID）"}
    started = time.perf_counter()
    await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=4,
        timeout=30.0,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {"ok": True, "latency_ms": latency_ms, "detail": f"对话测试通过（{latency_ms}ms）"}


async def _test_qwen() -> dict[str, Any]:
    """千问无对话端点，发一条最小多模态请求验证 Key 是否被接受（非 401/403 即认为鉴权通过）。"""
    api_key = resolve_conf("qwen_api_key")
    if not api_key:
        return {"ok": False, "detail": "未配置 QWEN_API_KEY"}
    settings = get_settings()
    url = f"{settings.qwen_base_url.rstrip('/')}/api/v1/services/aigc/multimodal-generation/generation"
    payload = {
        "model": settings.qwen_image_model,
        "input": {"messages": [{"role": "user", "content": [{"text": "ping"}]}]},
        "parameters": {"n": 1},
    }
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if resp.status_code in (401, 403):
            return {"ok": False, "latency_ms": latency_ms, "detail": f"鉴权失败（HTTP {resp.status_code}）"}
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "detail": f"鉴权通过（HTTP {resp.status_code}，{latency_ms}ms）",
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"请求失败：{str(exc)[:200]}"}


async def test_provider(provider: str) -> dict[str, Any]:
    """连通性测试：返回 {"ok", "latency_ms", "detail"}。"""
    try:
        if provider == "deepseek":
            return await _test_deepseek()
        if provider == "doubao":
            return await _test_doubao()
        if provider == "qwen":
            return await _test_qwen()
        return {"ok": False, "detail": "该平台不支持在线连通性测试"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("provider test failed (%s): %s", provider, exc)
        return {"ok": False, "detail": f"测试失败：{str(exc)[:300]}"}
