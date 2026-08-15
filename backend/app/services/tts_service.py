"""讯飞在线语音合成（TTS）WebSocket 客户端。

文档: https://www.xfyun.cn/doc/tts/online_tts/index.html
Host: tts-api.xfyun.cn  Path: /v2/tts
鉴权: hmac-sha256（与 IAT 相同的 XF_* 密钥）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.config import get_settings

logger = logging.getLogger(__name__)

XF_TTS_HOST = "tts-api.xfyun.cn"
XF_TTS_PATH = "/v2/tts"
# 单次合成建议控制长度，避免超时与额度浪费
_MAX_CHARS = 500


def tts_available() -> bool:
    s = get_settings()
    return bool(s.xf_app_id and s.xf_api_key and s.xf_api_secret)


def _vcn() -> str:
    s = get_settings()
    return (getattr(s, "xf_tts_vcn", None) or "xiaoyan").strip() or "xiaoyan"


def _build_ws_url() -> str:
    settings = get_settings()
    if not tts_available():
        raise RuntimeError("讯飞 TTS 未配置：请设置 XF_APP_ID / XF_API_KEY / XF_API_SECRET")

    host = XF_TTS_HOST
    path = XF_TTS_PATH
    date = format_date_time(mktime(datetime.now().timetuple()))
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        settings.xf_api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{settings.xf_api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"wss://{host}{path}?{query}"


def _sanitize_text(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise ValueError("合成文本为空")
    if len(cleaned) > _MAX_CHARS:
        cleaned = cleaned[:_MAX_CHARS] + "…"
    return cleaned


async def synthesize_speech(text: str, vcn: str | None = None) -> tuple[bytes, str]:
    """合成语音，返回 (audio_bytes, mime)。默认 mp3。"""
    payload_text = _sanitize_text(text)
    voice = (vcn or _vcn()).strip() or _vcn()
    url = _build_ws_url()
    settings = get_settings()

    frame = {
        "common": {"app_id": settings.xf_app_id},
        "business": {
            "aue": "lame",
            "sfl": 1,
            "auf": "audio/L16;rate=16000",
            "vcn": voice,
            "speed": 50,
            "volume": 50,
            "pitch": 50,
            "bgs": 0,
            "tte": "utf8",
        },
        "data": {
            "status": 2,
            "text": str(base64.b64encode(payload_text.encode("utf-8")), "UTF8"),
        },
    }

    chunks: list[bytes] = []
    try:
        async with websockets.connect(url, max_size=8 * 1024 * 1024, open_timeout=15) as ws:
            await ws.send(json.dumps(frame, ensure_ascii=False))
            while True:
                raw = await ws.recv()
                msg = json.loads(raw)
                code = msg.get("code", -1)
                if code != 0:
                    raise RuntimeError(msg.get("message") or f"讯飞 TTS 错误 code={code}")
                data = msg.get("data") or {}
                audio_b64 = data.get("audio")
                if audio_b64:
                    chunks.append(base64.b64decode(audio_b64))
                if data.get("status") == 2:
                    break
    except ConnectionClosed as exc:
        logger.warning("讯飞 TTS 连接关闭: %s", exc)
        raise RuntimeError("讯飞 TTS 连接中断") from exc

    if not chunks:
        raise RuntimeError("讯飞 TTS 未返回音频")
    return b"".join(chunks), "audio/mpeg"
