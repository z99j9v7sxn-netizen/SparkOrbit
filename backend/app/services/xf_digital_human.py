"""讯飞数字人视频大模型 WebAPI 客户端。

文档: https://www.xfyun.cn/doc/spark/videoGenerate.html
Host: vms.cn-huadong-1.xf-yun.com

路径说明（以文档「请求地址」为准，勿改成文中笔误的 /api/v1/...）：
  POST /v1/private/video/generate
  POST /v1/private/video/query
鉴权: hmac-sha256 URL query (host / date / authorization)
完成: task_status 为 "3"/"4" 且 payload 含 video
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import uuid
from email.utils import formatdate
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

XF_DH_HOST = "vms.cn-huadong-1.xf-yun.com"
XF_DH_GENERATE_PATH = "/v1/private/video/generate"
XF_DH_QUERY_PATH = "/v1/private/video/query"

_MEDIA_GENERATED = Path(__file__).resolve().parents[1] / "static" / "media" / "generated"

# 任务完成态（含回调等待）
_DONE_STATUSES = {"3", "4"}
_PENDING_STATUSES = {"1", "2", ""}


def _creds() -> tuple[str, str, str]:
    """优先 XF_DH_*，回退到通用讯飞 XF_*。"""
    s = get_settings()
    app_id = (getattr(s, "xf_dh_app_id", None) or s.xf_app_id or "").strip()
    api_key = (getattr(s, "xf_dh_api_key", None) or s.xf_api_key or "").strip()
    api_secret = (getattr(s, "xf_dh_api_secret", None) or s.xf_api_secret or "").strip()
    return app_id, api_key, api_secret


def xf_digital_human_available() -> bool:
    app_id, api_key, api_secret = _creds()
    return bool(app_id and api_key and api_secret)


def _host() -> str:
    s = get_settings()
    return (getattr(s, "xf_dh_host", None) or XF_DH_HOST).strip() or XF_DH_HOST


def _assemble_auth_url(path: str, method: str = "POST") -> str:
    """按文档用 hmac-sha256 拼装带鉴权参数的完整 URL。"""
    app_id, api_key, api_secret = _creds()
    if not (app_id and api_key and api_secret):
        raise RuntimeError(
            "未配置讯飞数字人密钥：请设置 XF_DH_APP_ID / XF_DH_API_KEY / XF_DH_API_SECRET"
            "（或回退使用 XF_APP_ID / XF_API_KEY / XF_API_SECRET）"
        )

    host = _host()
    # UTC RFC1123，时区标识为 GMT（文档示例）
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\n{method} {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"host": host, "date": date, "authorization": authorization})
    return f"https://{host}{path}?{query}"


_PROMPT_MAX_LEN = 300  # 文档/报错 10163：$.parameter.avatar.prompt 长度必须 ≤ 300


def _clamp_prompt(prompt: str) -> str:
    text = " ".join((prompt or "").strip().split())
    if not text:
        raise ValueError("prompt 不能为空")
    if len(text) <= _PROMPT_MAX_LEN:
        return text
    return text[: _PROMPT_MAX_LEN - 1].rstrip() + "…"


async def create_task(prompt: str, word_count: int = 120) -> str:
    """提交数字人视频生成任务，返回 task_id。"""
    app_id, _, _ = _creds()
    text = _clamp_prompt(prompt)

    wc = int(word_count or 120)
    wc = max(50, min(300, wc))

    url = _assemble_auth_url(XF_DH_GENERATE_PATH)
    body = {
        "header": {"app_id": app_id},
        "parameter": {
            "avatar": {
                "prompt": text,
                "word_count": wc,
            }
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
        if resp.status_code >= 400:
            detail = resp.text[:500]
            logger.error("XF DH create failed %s: %s", resp.status_code, detail)
            raise RuntimeError(f"讯飞数字人创建失败 HTTP {resp.status_code}: {detail}")
        data = resp.json()

    header = data.get("header") or {}
    code = header.get("code", -1)
    if code != 0:
        raise RuntimeError(f"讯飞数字人创建失败: {header.get('message') or data}")
    task_id = header.get("task_id") or ""
    if not task_id:
        raise RuntimeError(f"讯飞数字人未返回 task_id: {data}")
    return str(task_id)


async def query_task(task_id: str) -> dict[str, Any]:
    """查询任务状态，返回 {status, payload, code, message, raw}。"""
    app_id, _, _ = _creds()
    tid = (task_id or "").strip()
    if not tid:
        raise ValueError("task_id 不能为空")

    url = _assemble_auth_url(XF_DH_QUERY_PATH)
    body = {"header": {"app_id": app_id, "task_id": tid}}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
        if resp.status_code >= 400:
            detail = resp.text[:500]
            logger.error("XF DH query failed %s: %s", resp.status_code, detail)
            raise RuntimeError(f"讯飞数字人查询失败 HTTP {resp.status_code}: {detail}")
        data = resp.json()

    header = data.get("header") or {}
    code = header.get("code", -1)
    status = str(header.get("task_status") or "")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else None
    video = extract_video_url(payload)
    payload_keys = list(payload.keys()) if isinstance(payload, dict) else []
    logger.info(
        "XF DH query task_id=%s status=%s code=%s payload_keys=%s has_video=%s",
        tid,
        status,
        code,
        payload_keys,
        bool(video),
    )
    # 文档：3/4 为完成态；无回调时通常直接到 4。有 payload.video 才算真正可播放完成。
    done = code == 0 and status in _DONE_STATUSES and bool(video)
    pending = code == 0 and (
        status in _PENDING_STATUSES or (status in _DONE_STATUSES and not video)
    )
    return {
        "status": status,
        "payload": payload,
        "code": code,
        "message": str(header.get("message") or ""),
        "task_id": str(header.get("task_id") or tid),
        "raw": data,
        "done": done,
        "pending": pending,
        "video_url": video,
    }


async def poll_until_done(
    task_id: str,
    *,
    interval: float | None = None,
    timeout: float | None = None,
    on_poll: Any = None,
) -> dict[str, Any]:
    """轮询直到 task_status 为 3/4 并带 payload，返回完整 query 结果。"""
    settings = get_settings()
    poll_iv = float(interval if interval is not None else getattr(settings, "xf_dh_poll_interval", 5) or 5)
    poll_iv = max(2.0, poll_iv)
    # 默认 15 分钟，与前端 poll timeout 对齐；控制台并发常为 1，忙时易超时
    limit = float(timeout if timeout is not None else getattr(settings, "xf_dh_timeout", 900) or 900)
    limit = max(30.0, limit)

    elapsed = 0.0
    last: dict[str, Any] = {}
    while elapsed <= limit:
        last = await query_task(task_id)
        if on_poll:
            await on_poll(last.get("status"), last)
        code = last.get("code", -1)
        if code != 0:
            raise RuntimeError(f"讯飞数字人任务错误: {last.get('message') or last}")
        status = str(last.get("status") or "")
        if last.get("done"):
            return last
        # 完成态但无 video：再等一轮；若持续无 video 则当作失败返回给上层
        if status in _DONE_STATUSES and last.get("payload") and not last.get("video_url"):
            if elapsed >= min(limit, 60.0):
                return last
        await asyncio.sleep(poll_iv)
        elapsed += poll_iv

    header = ((last.get("raw") or {}).get("header") or {}) if last else {}
    raise TimeoutError(
        f"讯飞云端渲染排队超时（{int(limit)}s）。"
        f"最后状态={last.get('status') or 'unknown'}，"
        f"message={last.get('message') or header.get('message') or '—'}。"
        f"可先看文案讲解，稍后点「重新生成」。"
        f"控制台核对：数字人视频大模型额度与并发（常为 1）。"
        f"task_id={task_id}"
    )


async def download_video(video_url: str, *, planet_slug: str = "dh") -> str:
    """下载到 static/media/generated，返回可访问的 /static/... URL。"""
    remote = (video_url or "").strip()
    if not remote:
        raise ValueError("video_url 不能为空")
    _MEDIA_GENERATED.mkdir(parents=True, exist_ok=True)
    filename = f"dh_{uuid.uuid4().hex}.mp4"
    dest = _MEDIA_GENERATED / filename
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        resp = await client.get(remote)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return f"/static/media/generated/{filename}"


def extract_video_url(payload: Optional[dict[str, Any]]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("video", "video_url", "url"):
        val = payload.get(key)
        if val:
            return str(val)
    return None
