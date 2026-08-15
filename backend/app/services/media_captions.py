"""教学短视频字幕：由分镜旁白生成可读中文字幕，并可选 ffmpeg 烧录。"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MEDIA_ROOT = Path(__file__).resolve().parents[1] / "static" / "media"


def build_caption_cues(
    slides: list[dict[str, Any]],
    *,
    duration_sec: float,
    planet_name: str = "",
) -> list[dict[str, Any]]:
    """按均分时长把分镜转为字幕 cues：[{start,end,text}]。"""
    dur = max(2.0, float(duration_sec or 12))
    cleaned: list[dict[str, Any]] = []
    for s in slides or []:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or "").strip()
        narr = str(s.get("narration") or "").strip()
        text = f"{title}：{narr}" if title and narr else (narr or title)
        text = " ".join(text.split())
        if text:
            cleaned.append({"text": text[:100]})
    if not cleaned:
        label = planet_name or "本知识点"
        cleaned = [{"text": f"今天学习{label}，请结合旁白理解核心概念。"}]

    slot = dur / len(cleaned)
    cues: list[dict[str, Any]] = []
    for i, item in enumerate(cleaned):
        start = round(i * slot, 3)
        end = round(dur if i == len(cleaned) - 1 else (i + 1) * slot, 3)
        cues.append({"start": start, "end": end, "text": item["text"]})
    return cues


def build_teaching_seedance_prompt(
    planet_name: str,
    slides: list[dict[str, Any]],
    *,
    extra: str = "",
) -> str:
    """
    构造适合 Seedance 1.0 的「无文字」教学画面描述。
    模型无法可靠渲染中文，必须禁止片内文字，字幕改由后期烧录/前端叠加。
    """
    scenes: list[str] = []
    for i, s in enumerate((slides or [])[:6], 1):
        if not isinstance(s, dict):
            continue
        hint = str(s.get("visual_hint") or s.get("title") or "").strip()
        if hint:
            scenes.append(f"第{i}段仅用图形表达：{hint[:80]}")
    if not scenes:
        scenes = [
            f"第1段：用简洁图标引入主题「{planet_name}」",
            "第2段：核心概念的几何示意图缓慢展开",
            "第3段：步骤流程用箭头与色块演示",
            "第4段：收束为简洁总结图形",
        ]
    scene_text = "；".join(scenes)
    extra_bit = (extra or "").strip()[:120]
    return (
        f"纯视觉高等教育教学动画，主题必须严格为「{planet_name}」，16:9横屏，示意图风格，色块清晰，镜头缓慢推进。"
        f"画面只允许图形、图标、流程图、色块、几何连线，不要任何人物故事。"
        f"绝对禁止画面出现任何文字、字母、汉字、数字、字幕、水印、Logo、乱码或伪文字。"
        f"禁止风景航拍、禁止无人机、禁止与「{planet_name}」无关的场景。"
        f"分镜节奏：{scene_text}。"
        f"{extra_bit}"
    ).strip()


def cues_to_srt(cues: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, c in enumerate(cues, 1):
        start = _fmt_ts(float(c.get("start") or 0))
        end = _fmt_ts(float(c.get("end") or 0))
        text = str(c.get("text") or "").strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _fmt_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def media_url_to_path(media_url: str) -> Path | None:
    """把 /static/media/... 映射到本地文件。"""
    url = (media_url or "").strip()
    if not url.startswith("/static/media/"):
        return None
    rel = url[len("/static/media/") :]
    path = (_MEDIA_ROOT / rel).resolve()
    if not str(path).startswith(str(_MEDIA_ROOT.resolve())):
        return None
    return path if path.is_file() else None


def _pick_cjk_font() -> Path | None:
    candidates: list[Path] = []
    if sys.platform == "win32":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        candidates.extend(
            [
                windir / "Fonts" / "msyh.ttc",
                windir / "Fonts" / "msyhbd.ttc",
                windir / "Fonts" / "simhei.ttf",
                windir / "Fonts" / "simsun.ttc",
            ]
        )
    else:
        candidates.extend(
            [
                Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
                Path("/System/Library/Fonts/PingFang.ttc"),
            ]
        )
    for p in candidates:
        if p.is_file():
            return p
    return None


def burn_subtitles_into_mp4(
    media_url: str,
    cues: list[dict[str, Any]],
) -> str | None:
    """用 ffmpeg 把中文字幕烧进 MP4，成功返回新的 /static/... URL；失败返回 None。"""
    from app.services.audio_preprocess import _resolve_ffmpeg, ffmpeg_available

    if not cues or not ffmpeg_available():
        return None
    src = media_url_to_path(media_url)
    ffmpeg = _resolve_ffmpeg()
    if src is None or not ffmpeg:
        return None

    srt_body = cues_to_srt(cues)
    if not srt_body.strip():
        return None

    out_name = f"{src.stem}_cap{src.suffix}"
    dest = src.with_name(out_name)
    font = _pick_cjk_font()

    with tempfile.TemporaryDirectory(prefix="seedance_subs_") as tmp:
        srt_path = Path(tmp) / "captions.srt"
        srt_path.write_text(srt_body, encoding="utf-8-sig")
        srt_escaped = srt_path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
        style = (
            "FontName=Microsoft YaHei,FontSize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H80000000,BorderStyle=3,Outline=2,Shadow=0,"
            "MarginV=28,Alignment=2"
        )
        vf = f"subtitles='{srt_escaped}':force_style='{style}'"
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-vf",
            vf,
            "-c:a",
            "copy",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            str(dest),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("字幕烧录失败: %s", exc)
            return _burn_with_drawtext(ffmpeg, src, dest, cues, font)

        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            rel = dest.relative_to(_MEDIA_ROOT).as_posix()
            return f"/static/media/{rel}"

        logger.warning(
            "字幕烧录 ffmpeg 退出 %s: %s",
            proc.returncode,
            (proc.stderr or "")[-400:],
        )
        return _burn_with_drawtext(ffmpeg, src, dest, cues, font)


def _burn_with_drawtext(
    ffmpeg: str,
    src: Path,
    dest: Path,
    cues: list[dict[str, Any]],
    font: Path | None,
) -> str | None:
    """subtitles 滤镜失败时，用 drawtext 逐段叠加。"""
    if not font:
        return None
    fontfile = font.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    filters: list[str] = []
    for c in cues:
        start = float(c.get("start") or 0)
        end = float(c.get("end") or 0)
        text = str(c.get("text") or "").replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
        text = text.replace("%", "%%")[:56]
        filters.append(
            f"drawtext=fontfile='{fontfile}':text='{text}':fontsize=22:fontcolor=white:"
            f"borderw=2:bordercolor=black@0.7:x=(w-text_w)/2:y=h-72:"
            f"enable='between(t,{start},{end})'"
        )
    if not filters:
        return None
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vf",
        ",".join(filters),
        "-c:a",
        "copy",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        str(dest),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("drawtext 烧录失败: %s", exc)
        return None
    if proc.returncode != 0 or not dest.is_file():
        logger.warning("drawtext 烧录失败: %s", (proc.stderr or "")[-400:])
        return None
    rel = dest.relative_to(_MEDIA_ROOT).as_posix()
    return f"/static/media/{rel}"
