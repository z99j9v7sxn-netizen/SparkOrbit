"""讯飞大模型语音识别（方言大模型 / 多语种识别）WebSocket 签名与帧构造。

协议文档：
- 方言大模型：https://www.xfyun.cn/doc/spark/spark_slm_iat.html
- 多语种识别：https://www.xfyun.cn/doc/spark/spark_mul_cn_iat.html

地址：wss://iat.cn-huabei-1.xf-yun.com/v1
结构：header / parameter / payload（结果 text 为 base64 JSON）
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

from app.core.config import get_settings

XF_IAT_HOST = "iat.cn-huabei-1.xf-yun.com"
XF_IAT_PATH = "/v1"


def _xf_configured() -> bool:
    settings = get_settings()
    return bool(settings.xf_app_id and settings.xf_api_key and settings.xf_api_secret)


def build_iat_ws_url() -> str:
    settings = get_settings()
    if not _xf_configured():
        raise RuntimeError("讯飞语音识别未配置")

    host = XF_IAT_HOST
    path = XF_IAT_PATH
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


def _iat_parameter(language: str = "zh_cn", accent: str = "mandarin", *, eos: int | None = None) -> dict:
    """按语言选择方言大模型或多语种大模型参数。"""
    del accent  # 新协议由 language 映射到 mulacc / mul_cn
    eos_ms = 6000 if eos is None else max(1000, min(int(eos), 20000))
    result_fmt = {"encoding": "utf8", "compress": "raw", "format": "json"}
    if language == "en_us":
        # 大模型多语种识别：指定英文
        return {
            "iat": {
                "domain": "slm",
                "language": "mul_cn",
                "accent": "mandarin",
                "ln": "en",
                "eos": eos_ms,
                "dwa": "wpgs",
                "result": result_fmt,
            }
        }
    # 方言大模型：普通话 + 202 种方言免切换（含粤语）
    return {
        "iat": {
            "domain": "slm",
            "language": "zh_cn",
            "accent": "mulacc",
            "eos": eos_ms,
            "dwa": "wpgs",
            "ptt": 1,
            "nunum": 1,
            "result": result_fmt,
        }
    }


def _audio_payload(audio_b64: str, status: int, seq: int = 0) -> dict:
    return {
        "audio": {
            "encoding": "raw",
            "sample_rate": 16000,
            "channels": 1,
            "bit_depth": 16,
            "seq": seq,
            "status": status,
            "audio": audio_b64,
        }
    }


def build_iat_first_frame(
    language: str = "zh_cn",
    accent: str = "mandarin",
    *,
    eos: int | None = None,
) -> dict:
    """首帧：带 parameter + header.status=0。accent 保留入参以兼容调用方，实际由 language 决定服务选型。"""
    settings = get_settings()
    return {
        "header": {"app_id": settings.xf_app_id, "status": 0},
        "parameter": _iat_parameter(language, accent, eos=eos),
        "payload": _audio_payload("", status=0, seq=0),
    }


def build_iat_audio_frame(audio_b64: str, status: int = 1, seq: int = 1) -> dict:
    settings = get_settings()
    return {
        "header": {"app_id": settings.xf_app_id, "status": status},
        "payload": _audio_payload(audio_b64, status=status, seq=seq),
    }


def build_iat_end_frame(seq: int = 999) -> dict:
    return build_iat_audio_frame("", status=2, seq=seq)


def _decode_iat_result(payload: dict) -> dict:
    body = payload.get("payload") or {}
    result = body.get("result") or {}
    text_b64 = result.get("text")
    if not text_b64:
        data = payload.get("data") or {}
        return data.get("result") or {}
    try:
        raw = base64.b64decode(text_b64).decode("utf-8")
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def extract_iat_text(payload: dict) -> str:
    """从大模型 IAT 响应中提取识别文本（payload.result.text 为 base64 JSON）。"""
    decoded = _decode_iat_result(payload)
    if decoded:
        return _join_ws(decoded.get("ws") or [])
    data = payload.get("data") or {}
    legacy = data.get("result") or {}
    return _join_ws(legacy.get("ws") or [])


def extract_iat_segment(payload: dict) -> tuple[int, list[str], str, list[int]]:
    """解析 wpgs 动态修正帧：返回 (sn, words, pgs, rg)。

    pgs=apd 把本帧写入 sn；pgs=rpl 时 rg 为 sn 闭区间，先删后写。
    不改动 extract_iat_text 的对外语义，以免影响短语音链路。
    """
    decoded = _decode_iat_result(payload)
    words: list[str] = []
    for ws in decoded.get("ws") or []:
        for cw in ws.get("cw") or []:
            word = cw.get("w")
            if word:
                words.append(str(word))
    pgs = str(decoded.get("pgs") or "")
    rg_raw = decoded.get("rg") or []
    rg: list[int] = []
    for item in rg_raw:
        try:
            rg.append(int(item))
        except (TypeError, ValueError):
            continue
    try:
        sn = int(decoded.get("sn") or 0)
    except (TypeError, ValueError):
        sn = 0
    return sn, words, pgs, rg


def _join_ws(ws_list: list) -> str:
    parts: list[str] = []
    for ws in ws_list:
        for cw in ws.get("cw") or []:
            word = cw.get("w")
            if word:
                parts.append(str(word))
    return "".join(parts)


def iat_header_code(payload: dict) -> int:
    header = payload.get("header") or {}
    if "code" in header:
        return int(header.get("code") or 0)
    return int(payload.get("code") or 0)


def iat_header_message(payload: dict) -> str:
    header = payload.get("header") or {}
    return str(header.get("message") or payload.get("message") or "")


def iat_is_final(payload: dict) -> bool:
    header = payload.get("header") or {}
    if header.get("status") == 2:
        return True
    body = payload.get("payload") or {}
    result = body.get("result") or {}
    return result.get("status") == 2


async def transcribe_pcm(pcm_bytes: bytes, language: str = "zh_cn") -> str:
    """服务端 IAT 转写 16k PCM 单声道音频。"""
    import asyncio
    import json

    import websockets

    if not pcm_bytes or not _xf_configured():
        return ""

    lang = language if language in {"zh_cn", "en_us"} else "zh_cn"
    url = build_iat_ws_url()
    transcript = ""
    chunk_size = 6400
    chunks = [pcm_bytes[i : i + chunk_size] for i in range(0, len(pcm_bytes), chunk_size)] or [b""]

    try:
        async with websockets.connect(url, max_size=None) as xf:
            await xf.send(json.dumps(build_iat_first_frame(lang, "mandarin")))
            seq = 1
            for idx, chunk in enumerate(chunks):
                status = 2 if idx == len(chunks) - 1 else 1
                audio_b64 = base64.b64encode(chunk).decode("utf-8")
                await xf.send(json.dumps(build_iat_audio_frame(audio_b64, status=status, seq=seq)))
                seq += 1
                await asyncio.sleep(0.03)

            while True:
                raw = await asyncio.wait_for(xf.recv(), timeout=30)
                payload = json.loads(raw)
                if iat_header_code(payload) != 0:
                    break
                text = extract_iat_text(payload)
                if text:
                    transcript += text
                if iat_is_final(payload):
                    break
    except Exception:
        return transcript
    return transcript.strip()
