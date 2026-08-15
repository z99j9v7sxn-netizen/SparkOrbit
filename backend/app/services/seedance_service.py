"""火山方舟 Seedance 视频生成（对齐官方 Rest 示例：参数写入 prompt）。"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MEDIA_GENERATED = Path(__file__).resolve().parents[1] / "static" / "media" / "generated"

# 仅在显式配置封面时使用；未配置则走文生视频，避免无关官方示例图
_DEFAULT_I2V_IMAGE = "https://ark-project.tos-cn-beijing.volces.com/doc_image/seepro_i2v.png"


def seedance_available() -> bool:
    from app.services.llm import resolve_conf

    s = get_settings()
    return bool(resolve_conf("ark_api_key") and s.ark_base_url and s.ark_seedance_model)


def _headers() -> dict[str, str]:
    from app.services.llm import resolve_conf

    return {
        "Authorization": f"Bearer {resolve_conf('ark_api_key')}",
        "Content-Type": "application/json",
    }


def _base() -> str:
    return get_settings().ark_base_url.rstrip("/")


def compose_seedance_prompt(
    prompt: str,
    *,
    duration: int,
    watermark: bool,
    camerafixed: bool = False,
    resolution: str = "720p",
    ratio: str = "16:9",
) -> str:
    """官方示例把 --duration / --watermark 等写在 text 末尾。"""
    base = (prompt or "").strip()
    # 去掉已有控制参数，避免重复
    for token in ("--duration", "--watermark", "--camerafixed", "--ratio", "--resolution"):
        if token in base:
            idx = base.find(token)
            base = base[:idx].rstrip()
    res = (resolution or "720p").strip() or "720p"
    rat = (ratio or "16:9").strip() or "16:9"
    flags = (
        f" --resolution {res}"
        f" --ratio {rat}"
        f" --duration {duration}"
        f" --camerafixed {'true' if camerafixed else 'false'}"
        f" --watermark {'true' if watermark else 'false'}"
    )
    return f"{base}{flags}"


async def create_video_task(
    prompt: str,
    *,
    duration: int | None = None,
    watermark: bool = False,
    image_url: str | None = None,
    use_image: bool | None = None,
) -> dict[str, Any]:
    """
    提交视频生成任务（对齐控制台示例）。

    - 有自定义封面 URL 时走图生视频（text + image_url）
    - 无封面时走文生视频（仅 text），避免无关官方示例图
    - 参数写在 text：`--resolution 720p --ratio 16:9 --duration 12 ...`
    """
    settings = get_settings()
    dur = duration if duration is not None else settings.ark_seedance_duration
    dur = max(2, min(12, int(dur)))
    text = compose_seedance_prompt(
        prompt,
        duration=dur,
        watermark=watermark,
        resolution=getattr(settings, "ark_seedance_resolution", "720p") or "720p",
        ratio=getattr(settings, "ark_seedance_ratio", "16:9") or "16:9",
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]

    img = (image_url or getattr(settings, "ark_seedance_image_url", "") or "").strip()
    # 未显式指定 use_image 时：仅当有自定义封面才启用图生视频
    if use_image is None:
        use_image = bool(img)
    if use_image:
        content.append({"type": "image_url", "image_url": {"url": img or _DEFAULT_I2V_IMAGE}})

    body = {
        "model": settings.ark_seedance_model,
        "content": content,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{_base()}/contents/generations/tasks",
            headers=_headers(),
            json=body,
        )
        if resp.status_code >= 400:
            # 附带响应体，便于前端/日志看到 ModelNotOpen 等
            detail = resp.text[:500]
            logger.error("Seedance create failed %s: %s", resp.status_code, detail)
            raise RuntimeError(f"Seedance HTTP {resp.status_code}: {detail}")
        data = resp.json()
    task_id = data.get("id") or data.get("task_id")
    if not task_id:
        raise RuntimeError(f"Seedance 未返回 task id: {data}")
    return {"id": str(task_id), "raw": data, "mode": "i2v" if len(content) > 1 else "t2v"}


async def get_video_task(task_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            f"{_base()}/contents/generations/tasks/{task_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


def extract_video_url(payload: dict[str, Any]) -> Optional[str]:
    content = payload.get("content")
    if isinstance(content, dict):
        url = content.get("video_url") or content.get("url")
        if url:
            return str(url)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                url = item.get("video_url") or item.get("url")
                if url:
                    return str(url)
                video = item.get("video")
                if isinstance(video, dict) and video.get("url"):
                    return str(video["url"])
    for key in ("video_url", "url"):
        if payload.get(key):
            return str(payload[key])
    output = payload.get("output")
    if isinstance(output, dict) and output.get("video_url"):
        return str(output["video_url"])
    return None


async def download_video(video_url: str, *, planet_slug: str) -> str:
    """下载到 static/media/generated，返回可访问的 /static/... URL。"""
    _MEDIA_GENERATED.mkdir(parents=True, exist_ok=True)
    filename = f"{planet_slug}_{uuid.uuid4().hex[:10]}.mp4"
    dest = _MEDIA_GENERATED / filename
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return f"/static/media/generated/{filename}"


async def wait_and_download(
    task_id: str,
    *,
    planet_slug: str,
    on_poll: Any = None,
) -> dict[str, Any]:
    """
    轮询直到 succeeded/failed/超时。
    成功返回 {media_url, task_id, remote_url, status}。
    on_poll 可选 async callable(status, payload)。
    """
    settings = get_settings()
    interval = max(5, settings.ark_seedance_poll_interval)
    timeout = max(60, settings.ark_seedance_timeout)
    elapsed = 0
    last_status = "submitted"

    while elapsed <= timeout:
        import asyncio

        payload = await get_video_task(task_id)
        status = str(payload.get("status") or "").lower()
        last_status = status or last_status
        if on_poll:
            await on_poll(status, payload)
        if status in ("succeeded", "success", "completed"):
            remote = extract_video_url(payload)
            if not remote:
                raise RuntimeError(f"Seedance 成功但无 video_url: {payload}")
            local = await download_video(remote, planet_slug=planet_slug)
            return {
                "media_url": local,
                "task_id": task_id,
                "remote_url": remote,
                "status": status,
                "provider": "seedance_1_0_pro_fast",
                "model": settings.ark_seedance_foundation_model or settings.ark_seedance_model,
            }
        if status in ("failed", "error", "cancelled", "canceled"):
            err = payload.get("error") or payload.get("message") or payload
            raise RuntimeError(f"Seedance 任务失败: {err}")
        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Seedance 轮询超时（{timeout}s），最后状态={last_status}")
