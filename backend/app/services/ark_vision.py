"""火山方舟豆包视觉聊天（OpenAI 兼容 chat/completions），供画笔问伴学 / 错题识图。"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union

import httpx

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

ContentPart = Union[str, List[Dict[str, Any]]]
ChatMessage = Dict[str, Any]


async def _write_usage_log(
    *,
    user_id: str = "",
    endpoint: str = "ark_vision_chat",
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
        logger.warning("ark vision usage log failed: %s", exc)


def ark_vision_available() -> bool:
    from app.services.llm import resolve_conf

    s = get_settings()
    return bool(resolve_conf("ark_api_key") and s.ark_base_url and s.ark_vision_model)


def _headers() -> dict[str, str]:
    from app.services.llm import resolve_conf

    return {
        "Authorization": f"Bearer {resolve_conf('ark_api_key')}",
        "Content-Type": "application/json",
    }


async def ark_vision_chat(
    messages: List[ChatMessage],
    *,
    temperature: float = 0.6,
    timeout: float = 90.0,
    user_id: str = "",
    endpoint: str = "ark_vision_chat",
    apply_shield: bool = True,
) -> Optional[str]:
    """调用方舟 /chat/completions；支持多模态 content list。失败返回 None。"""
    settings = get_settings()
    if not ark_vision_available():
        return None

    model = settings.ark_vision_model
    url = f"{settings.ark_base_url.rstrip('/')}/chat/completions"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        msg = (choices[0] or {}).get("message") if choices else None
        content = (msg or {}).get("content") if isinstance(msg, dict) else None
        if not isinstance(content, str) or not content.strip():
            await _write_usage_log(
                user_id=user_id,
                endpoint=endpoint,
                model=model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error_message="empty content",
            )
            return None

        usage = data.get("usage") or {}
        await _write_usage_log(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=int((time.perf_counter() - started) * 1000),
            success=True,
        )

        if apply_shield:
            from app.services.shield import filter_text

            return await filter_text(content.strip())
        return content.strip()
    except Exception as exc:  # noqa: BLE001
        await _write_usage_log(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            latency_ms=int((time.perf_counter() - started) * 1000),
            success=False,
            error_message=str(exc)[:500],
        )
        logger.exception("ark_vision_chat failed: %s", exc)
        return None
