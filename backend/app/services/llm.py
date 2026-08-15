"""大模型统一调用层：DeepSeek 优先，豆包（火山方舟）兜底，供多智能体复用。"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

_deepseek_client: Optional[AsyncOpenAI] = None
_deepseek_client_key: str = ""
_ark_client: Optional[AsyncOpenAI] = None
_ark_client_key: str = ""

# 支持管理端在线覆盖（setting_entries 的 override:* 键）的配置项
OVERRIDABLE_CONF = {
    "deepseek_api_key",
    "deepseek_model",
    "ark_api_key",
    "ark_chat_model",
    "qwen_api_key",
}


def resolve_conf(name: str) -> str:
    """解析配置：数据库 override:* 覆盖层优先，其次 .env（get_settings）。"""
    from app.services import runtime_config

    if name in OVERRIDABLE_CONF:
        override = runtime_config.get_str(f"override:{name}", "").strip()
        if override:
            return override
    return str(getattr(get_settings(), name, "") or "")


def conf_source(name: str) -> str:
    """配置来源：override（在线覆盖）/ env / none。"""
    from app.services import runtime_config

    if name in OVERRIDABLE_CONF and runtime_config.get_str(f"override:{name}", "").strip():
        return "override"
    if str(getattr(get_settings(), name, "") or "").strip():
        return "env"
    return "none"


async def _write_usage_log(
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
    try:
        from app.services.admin import log_api_usage

        async with AsyncSessionLocal() as session:
            await log_api_usage(
                session,
                user_id=user_id,
                endpoint=endpoint,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage log failed: %s", exc)


def _ark_chat_model_id() -> str:
    s = get_settings()
    return (resolve_conf("ark_chat_model") or s.ark_vision_model or "").strip()


def deepseek_available() -> bool:
    return bool(resolve_conf("deepseek_api_key"))


def doubao_available() -> bool:
    s = get_settings()
    return bool(resolve_conf("ark_api_key") and s.ark_base_url and _ark_chat_model_id())


def llm_available() -> bool:
    return deepseek_available() or doubao_available()


def active_llm_provider() -> str:
    """返回当前将优先使用的提供方：deepseek / doubao / none。"""
    s = get_settings()
    pref = (s.llm_provider or "auto").strip().lower()
    if pref == "doubao":
        return "doubao" if doubao_available() else ("deepseek" if deepseek_available() else "none")
    if pref == "deepseek":
        return "deepseek" if deepseek_available() else ("doubao" if doubao_available() else "none")
    # auto
    if deepseek_available():
        return "deepseek"
    if doubao_available():
        return "doubao"
    return "none"


def llm_status() -> dict:
    provider = active_llm_provider()
    s = get_settings()
    model = ""
    if provider == "deepseek":
        model = resolve_conf("deepseek_model") or s.deepseek_model
    elif provider == "doubao":
        model = _ark_chat_model_id() or s.ark_vision_foundation_model
    return {
        "available": provider != "none",
        "provider": provider,
        "model": model,
        "deepseek": deepseek_available(),
        "doubao": doubao_available(),
        "label": {
            "deepseek": "DeepSeek",
            "doubao": "豆包（火山方舟）",
            "none": "未配置",
        }.get(provider, provider),
    }


def _get_deepseek_client() -> Optional[AsyncOpenAI]:
    """按 Key 值缓存：管理端换 Key 后自动重建客户端。"""
    global _deepseek_client, _deepseek_client_key
    api_key = resolve_conf("deepseek_api_key")
    if not api_key:
        return None
    if _deepseek_client is None or _deepseek_client_key != api_key:
        _deepseek_client = AsyncOpenAI(
            api_key=api_key,
            base_url=get_settings().deepseek_base_url,
        )
        _deepseek_client_key = api_key
    return _deepseek_client


def _get_ark_client() -> Optional[AsyncOpenAI]:
    global _ark_client, _ark_client_key
    if not doubao_available():
        return None
    api_key = resolve_conf("ark_api_key")
    if _ark_client is None or _ark_client_key != api_key:
        _ark_client = AsyncOpenAI(
            api_key=api_key,
            base_url=get_settings().ark_base_url.rstrip("/"),
        )
        _ark_client_key = api_key
    return _ark_client


def _provider_order() -> list[str]:
    primary = active_llm_provider()
    if primary == "none":
        return []
    order = [primary]
    alt = "doubao" if primary == "deepseek" else "deepseek"
    if alt == "deepseek" and deepseek_available():
        order.append(alt)
    if alt == "doubao" and doubao_available():
        order.append(alt)
    return order


async def _chat_once(
    provider: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    response_json: bool,
    thinking: bool,
    timeout: float,
    user_id: str,
    endpoint: str,
) -> Optional[str]:
    if provider == "deepseek":
        client = _get_deepseek_client()
        model = resolve_conf("deepseek_model")
    else:
        client = _get_ark_client()
        model = _ark_chat_model_id()
    if client is None or not model:
        return None

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout,
    }
    # 豆包部分接入点对 json_object 支持不稳，易超时；改为提示约束即可
    if response_json and provider == "deepseek":
        kwargs["response_format"] = {"type": "json_object"}
    # thinking 仅 DeepSeek 支持
    if thinking and provider == "deepseek":
        kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        kwargs["reasoning_effort"] = "high"

    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        latency_ms = int((time.perf_counter() - started) * 1000)
        await _write_usage_log(
            user_id=user_id,
            endpoint=f"{endpoint}:{provider}",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            success=True,
        )
        return content if isinstance(content, str) else None
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        await _write_usage_log(
            user_id=user_id,
            endpoint=f"{endpoint}:{provider}",
            model=model,
            latency_ms=latency_ms,
            success=False,
            error_message=str(exc),
        )
        logger.warning("llm_chat via %s failed: %s", provider, exc)
        return None


async def llm_chat_raw(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.5,
    response_json: bool = False,
    thinking: bool = False,
    timeout: float = 60.0,
    user_id: str = "",
    endpoint: str = "llm_chat",
) -> Optional[str]:
    """调用文本模型（DeepSeek / 豆包），不经思想防火墙。"""
    for provider in _provider_order():
        # 豆包首跳用更短超时，超时后迅速切 DeepSeek，避免 SSE 被拖死
        per_timeout = min(timeout, 35.0) if provider == "doubao" else timeout
        content = await _chat_once(
            provider,
            messages,
            temperature=temperature,
            response_json=response_json,
            thinking=thinking,
            timeout=per_timeout,
            user_id=user_id,
            endpoint=endpoint,
        )
        if content is not None:
            return content
    return None


async def llm_chat(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.5,
    response_json: bool = False,
    thinking: bool = False,
    timeout: float = 60.0,
    user_id: str = "",
    endpoint: str = "llm_chat",
) -> Optional[str]:
    """调用文本模型并经思想防火墙过滤；失败返回 None。"""
    content = await llm_chat_raw(
        messages,
        temperature=temperature,
        response_json=response_json,
        thinking=thinking,
        timeout=timeout,
        user_id=user_id,
        endpoint=endpoint,
    )
    if content is None:
        return None
    from app.services.shield import filter_text

    return await filter_text(content)


def _estimate_tokens(text: str) -> int:
    """无 usage 时的粗略估算：中文约 1 token/字，英文约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return cjk + max(other // 4, 0)


async def llm_chat_stream(
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.5,
    timeout: float = 90.0,
    user_id: str = "",
    endpoint: str = "llm_chat_stream",
) -> AsyncGenerator[str, None]:
    """流式调用；优先 DeepSeek，否则豆包。结束后写用量日志（token 统计真实化）。"""
    provider = active_llm_provider()
    if provider == "none":
        yield "（未配置 DeepSeek / 豆包 API Key，当前为离线演示模式。）"
        return

    if provider == "deepseek":
        client = _get_deepseek_client()
        model = resolve_conf("deepseek_model")
    else:
        client = _get_ark_client()
        model = _ark_chat_model_id()

    if client is None or not model:
        yield "（模型客户端不可用，请检查 API 配置。）"
        return

    parts: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    usage_seen = False
    started = time.perf_counter()
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
            stream=True,
            # DeepSeek / 火山方舟 OpenAI 兼容端点：最后一个 chunk 携带 usage
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                usage_seen = True
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                parts.append(delta)
                yield delta
    except Exception as exc:  # noqa: BLE001
        logger.exception("llm_chat_stream failed: %s", exc)
        latency_ms = int((time.perf_counter() - started) * 1000)
        await _write_usage_log(
            user_id=user_id,
            endpoint=f"{endpoint}:{provider}",
            model=model,
            latency_ms=latency_ms,
            success=False,
            error_message=str(exc),
        )
        yield "（生成中断，请稍后重试。）"
        return

    full = "".join(parts)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if not usage_seen:
        # 端点未返回 usage 时按字符估算，避免流式调用漏记
        prompt_text = "".join(m.get("content", "") for m in messages)
        prompt_tokens = _estimate_tokens(prompt_text)
        completion_tokens = _estimate_tokens(full)
    await _write_usage_log(
        user_id=user_id,
        endpoint=f"{endpoint}:{provider}",
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        success=True,
        error_message="" if usage_seen else "estimated",
    )
    if full:
        from app.services.shield import filter_text

        filtered = await filter_text(full)
        if filtered != full and len(filtered) < len(full):
            logger.info("stream output filtered by shield")


def extract_json(content: str) -> Optional[Dict[str, Any]]:
    """从模型返回文本中稳健地提取一个 JSON 对象。"""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def extract_json_list(content: str) -> Optional[list]:
    """提取 JSON 数组，或从对象的 questions 字段取出列表。"""
    if not content:
        return None
    obj = extract_json(content)
    if isinstance(obj, dict):
        qs = obj.get("questions")
        if isinstance(qs, list):
            return qs
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None
