"""讯飞口语评测 ISE WebSocket 客户端。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import websockets

from app.core.config import get_settings

logger = logging.getLogger(__name__)

XF_ISE_HOST = "ise-api.xfyun.cn"
XF_ISE_PATH = "/v2/open-ise"
CHUNK_SIZE = 6400  # ~200ms @16k


def _configured() -> bool:
    settings = get_settings()
    return bool(settings.xf_app_id and settings.xf_api_key and settings.xf_api_secret)


def build_ise_ws_url() -> str:
    settings = get_settings()
    if not _configured():
        raise RuntimeError("讯飞口语评测未配置")

    host = XF_ISE_HOST
    path = XF_ISE_PATH
    now = datetime.now()
    date = format_date_time(mktime(now.timetuple()))
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


def _format_ref_text(text: str, lang: str) -> str:
    clean = text.strip()
    if not clean:
        return clean
    if lang == "en":
        body = clean if clean.startswith("[content]") else f"[content]\n{clean}"
        return "\uFEFF" + body
    return "\uFEFF" + clean


def _parse_ise_xml(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    node = root.find(".//read_sentence") or root.find(".//rec_paper") or root
    attrs = node.attrib if node is not None else {}

    def pick(*keys: str) -> float | None:
        for key in keys:
            raw = attrs.get(key)
            if raw is None:
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return None

    total = pick("total_score")
    accuracy = pick("accuracy_score", "phone_score")
    fluency = pick("fluency_score")
    integrity = pick("integrity_score")
    return {
        "total": int(round(total)) if total is not None else None,
        "accuracy": int(round(accuracy)) if accuracy is not None else None,
        "fluency": int(round(fluency)) if fluency is not None else None,
        "integrity": int(round(integrity)) if integrity is not None else None,
        "engine": "xfyun-ise",
    }


async def evaluate_pronunciation(pcm_bytes: bytes, ref_text: str, lang: str = "cn") -> dict | None:
    """lang: cn | en"""
    if not pcm_bytes or not ref_text.strip() or not _configured():
        return None

    ent = "en_vip" if lang == "en" else "cn_vip"
    ise_text = _format_ref_text(ref_text, "en" if lang == "en" else "cn")
    settings = get_settings()
    url = build_ise_ws_url()

    ssb = {
        "common": {"app_id": settings.xf_app_id},
        "business": {
            "sub": "ise",
            "ent": ent,
            "category": "read_sentence",
            "cmd": "ssb",
            "text": ise_text,
            "tte": "utf-8",
            "ttp_skip": True,
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "rst": "entirety",
            "ise_unite": "1",
            "extra_ability": "multi_dimension",
        },
        "data": {"status": 0},
    }

    final_xml = ""
    try:
        async with websockets.connect(url, max_size=None) as ws:
            await ws.send(json.dumps(ssb))
            chunks = [pcm_bytes[i : i + CHUNK_SIZE] for i in range(0, len(pcm_bytes), CHUNK_SIZE)] or [b""]
            total = len(chunks)
            for idx, chunk in enumerate(chunks):
                aus = 1 if idx == 0 else (4 if idx == total - 1 else 2)
                status = 2 if idx == total - 1 else 1
                frame = {
                    "business": {"cmd": "auw", "aus": aus},
                    "data": {
                        "status": status,
                        "data": base64.b64encode(chunk).decode("utf-8"),
                    },
                }
                await ws.send(json.dumps(frame))
                await asyncio.sleep(0.04)

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                payload = json.loads(raw)
                code = int(payload.get("code") or 0)
                if code != 0:
                    logger.warning("ISE error %s: %s", code, payload.get("message"))
                    return None
                data = payload.get("data") or {}
                if data.get("data"):
                    try:
                        final_xml = base64.b64decode(data["data"]).decode("utf-8", errors="ignore")
                    except Exception:
                        pass
                if int(data.get("status") or 0) == 2:
                    break
    except Exception as exc:
        logger.warning("ISE evaluate failed: %s", exc)
        return None

    if not final_xml:
        return None
    try:
        return _parse_ise_xml(final_xml)
    except ET.ParseError:
        match = re.search(r'total_score="([\d.]+)"', final_xml)
        if not match:
            return None
        return {"total": int(round(float(match.group(1)))), "engine": "xfyun-ise"}
