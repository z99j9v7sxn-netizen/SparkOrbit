"""音频预处理：尽量转为 16k 单声道 PCM，供讯飞 ISE 使用。"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path


@lru_cache
def _resolve_ffmpeg() -> str | None:
    """优先使用配置 FFMPEG_PATH，否则在 PATH 中查找 ffmpeg。"""
    from app.core.config import get_settings

    configured = (get_settings().ffmpeg_path or "").strip().strip('"').strip("'")
    if configured:
        p = Path(configured)
        if p.is_dir():
            exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
            p = p / exe
        if p.is_file():
            return str(p.resolve())

    found = shutil.which("ffmpeg")
    return found


def ffmpeg_available() -> bool:
    return _resolve_ffmpeg() is not None


def _guess_suffix(filename: str, content_type: str = "") -> str:
    name = (filename or "").lower()
    if name.endswith((".webm", ".m4a", ".mp3", ".wav", ".ogg", ".mp4", ".flac")):
        return Path(name).suffix
    if "webm" in content_type:
        return ".webm"
    if "mp4" in content_type or "m4a" in content_type:
        return ".m4a"
    if "ogg" in content_type:
        return ".ogg"
    if "mpeg" in content_type or "mp3" in content_type:
        return ".mp3"
    return ".webm"


def convert_to_pcm16k(audio_bytes: bytes, filename: str = "audio.webm", content_type: str = "") -> bytes | None:
    """使用 ffmpeg 转为 16kHz mono s16le PCM；无 ffmpeg 时返回 None。"""
    if not audio_bytes:
        return None
    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg:
        return None
    suffix = _guess_suffix(filename, content_type)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{suffix}"
        dst = Path(tmp) / "output.pcm"
        src.write_bytes(audio_bytes)
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                str(dst),
            ],
            capture_output=True,
            timeout=45,
        )
        if proc.returncode != 0 or not dst.exists():
            return None
        return dst.read_bytes()


def scorable_filename(filename: str, content_type: str = "") -> tuple[str, str]:
    """为 cantonese.ai 选择可接受的扩展名与 MIME。"""
    suffix = _guess_suffix(filename, content_type)
    mime = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
    }.get(suffix, "application/octet-stream")
    return f"oral{suffix}", mime


_CANTONESE_NATIVE_SUFFIXES = {".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".flac"}


def convert_for_cantonese_ai(
    audio_bytes: bytes,
    filename: str = "oral.webm",
    content_type: str = "",
) -> tuple[bytes, str, str]:
    """将录音转为 cantonese.ai 支持的格式；返回 (bytes, filename, mime)。"""
    name, mime = scorable_filename(filename, content_type)
    suffix = Path(name).suffix.lower()
    if suffix in _CANTONESE_NATIVE_SUFFIXES:
        return audio_bytes, name, mime

    ffmpeg = _resolve_ffmpeg()
    if not ffmpeg or not audio_bytes:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("cantonese.ai: webm 需 ffmpeg 转 ogg，当前未转换")
        return audio_bytes, name, mime

    src_suffix = _guess_suffix(filename, content_type)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{src_suffix}"
        dst = Path(tmp) / "output.ogg"
        src.write_bytes(audio_bytes)
        proc = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-c:a", "libopus", str(dst)],
            capture_output=True,
            timeout=45,
        )
        if proc.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return dst.read_bytes(), "oral.ogg", "audio/ogg"

        dst_m4a = Path(tmp) / "output.m4a"
        proc2 = subprocess.run(
            [ffmpeg, "-y", "-i", str(src), "-ac", "1", "-c:a", "aac", str(dst_m4a)],
            capture_output=True,
            timeout=45,
        )
        if proc2.returncode == 0 and dst_m4a.exists() and dst_m4a.stat().st_size > 0:
            return dst_m4a.read_bytes(), "oral.m4a", "audio/mp4"

    return audio_bytes, name, mime
