"""cantonese.ai 粤语转写与发音评分。"""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.services.audio_preprocess import convert_for_cantonese_ai

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(get_settings().cantonese_ai_api_key.strip())


def _prepare_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
) -> tuple[bytes, str, str]:
    return convert_for_cantonese_ai(audio_bytes, filename, content_type)


def _parse_score_payload(payload: dict, ref_text: str, language: str) -> dict:
    total = payload.get("score")
    if total is None:
        total = payload.get("pronunciationScore")

    result: dict = {
        "total": int(round(float(total))) if total is not None else None,
        "passed": bool(payload.get("passed", False)),
        "engine": "cantonese.ai",
        "language": str(payload.get("language") or language),
    }

    if language == "cantonese":
        result["expected_jyutping"] = str(payload.get("expectedJyutping") or "")
        result["transcribed_jyutping"] = str(payload.get("transcribedJyutping") or "")
        result["transcribed_text"] = result["transcribed_jyutping"]
        result["expected_text"] = ref_text
        if result["total"] is not None:
            result["accuracy"] = result["total"]
    else:
        result["transcribed_text"] = str(payload.get("transcribedText") or "")
        result["expected_text"] = str(payload.get("expectedText") or ref_text)
        pron = payload.get("pronunciationScore")
        result["accuracy"] = (
            int(round(float(pron))) if pron is not None else result.get("total")
        )
        if payload.get("fluencyScore") is not None:
            result["fluency"] = int(round(float(payload["fluencyScore"])))
        if payload.get("integrityScore") is not None:
            result["integrity"] = int(round(float(payload["integrityScore"])))

    return result


async def cantonese_stt(audio_bytes: bytes, filename: str = "oral.webm", content_type: str = "") -> str:
    settings = get_settings()
    if not _configured():
        return ""
    audio_bytes, name, mime = _prepare_audio(audio_bytes, filename, content_type)
    base = settings.cantonese_ai_base_url.rstrip("/")
    url = f"{base}/stt"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                url,
                data={
                    "api_key": settings.cantonese_ai_api_key,
                    "with_timestamp": "false",
                    "wait_for_completion": "true",
                },
                files={"data": (name, audio_bytes, mime)},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "cantonese.ai STT HTTP %s: %s",
                    resp.status_code,
                    resp.text[:240],
                )
                return ""
            payload = resp.json()
    except Exception as exc:
        logger.warning("cantonese.ai STT failed: %s", exc)
        return ""
    return str(
        payload.get("text")
        or payload.get("transcription")
        or payload.get("fused_transcription")
        or ""
    ).strip()


async def cantonese_score_pronunciation(
    audio_bytes: bytes,
    ref_text: str,
    filename: str = "oral.webm",
    content_type: str = "",
    language: str = "cantonese",
) -> dict | None:
    settings = get_settings()
    if not _configured() or not ref_text.strip():
        return None
    audio_bytes, name, mime = _prepare_audio(audio_bytes, filename, content_type)
    base = settings.cantonese_ai_base_url.rstrip("/")
    url = f"{base}/score-pronunciation"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                url,
                data={
                    "api_key": settings.cantonese_ai_api_key,
                    "text": ref_text.strip(),
                    "language": language,
                },
                files={"audio": (name, audio_bytes, mime)},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "cantonese.ai score HTTP %s: %s",
                    resp.status_code,
                    resp.text[:240],
                )
                return None
            payload = resp.json()
    except Exception as exc:
        logger.warning("cantonese.ai score failed: %s", exc)
        return None
    if not payload.get("success", True) and "score" not in payload:
        return None
    return _parse_score_payload(payload, ref_text.strip(), language)
