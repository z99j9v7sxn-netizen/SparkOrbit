from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.paths import NOTES_DIR, RESOURCES_DIR, TREEHOLE_DIR


def _ext_from_content_type(content_type: str, fallback: str = ".bin") -> str:
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "pdf" in ct:
        return ".pdf"
    if "webm" in ct:
        return ".webm"
    if "ogg" in ct:
        return ".ogg"
    if "mpeg" in ct or "mp3" in ct:
        return ".mp3"
    if "mp4" in ct or "m4a" in ct:
        return ".m4a"
    if "wav" in ct:
        return ".wav"
    if "markdown" in ct or "text" in ct:
        return ".md"
    return fallback


async def save_upload_file(file: UploadFile, directory: Path, url_prefix: str) -> str:
    """将上传内容写入本地磁盘，返回静态 URL（不入库为 BLOB）。"""
    ext = Path(file.filename or "").suffix or _ext_from_content_type(file.content_type or "")
    filename = f"{uuid4().hex}{ext}"
    path = directory / filename
    content = await file.read()
    if not content:
        raise ValueError("文件为空")
    path.write_bytes(content)
    return f"/static/uploads/{url_prefix}/{filename}"


def save_upload_bytes(
    content: bytes,
    directory: Path,
    url_prefix: str,
    filename_hint: str = "",
    content_type: str = "",
) -> str:
    ext = Path(filename_hint or "").suffix or _ext_from_content_type(content_type or "")
    filename = f"{uuid4().hex}{ext}"
    path = directory / filename
    if not content:
        raise ValueError("文件为空")
    path.write_bytes(content)
    return f"/static/uploads/{url_prefix}/{filename}"
