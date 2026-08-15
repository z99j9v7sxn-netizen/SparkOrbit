"""作业题目 AI 提取：PDF/图片/文本 → 结构化题目。"""
from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any, Optional

from app.core.paths import RESOURCES_DIR, UPLOADS_DIR
from app.services.galaxy_forge import extract_pdf_text
from app.services.llm import (
    extract_json,
    extract_json_list,
    llm_available,
    llm_chat,
    llm_status,
)

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """你是教学助手。请从下列材料中提取可用于布置作业的题目。
严格输出 JSON：
{"title_suggestion":"作业标题建议","questions":[{"stem":"题干","kind":"choice|short|essay","options":["A. ..","B. .."],"answer":"参考答案或正确选项","score":5}]}
要求：
1. 尽量保留原题编号与选项；无选项的填空/简答题 kind 用 short 或 essay。
2. 不要编造材料中不存在的题目；若几乎提不出题，questions 可为空数组。
3. 最多提取 30 题。
"""


def _normalize_questions(raw: list[Any]) -> list[dict]:
    out: list[dict] = []
    for i, item in enumerate(raw[:30]):
        if not isinstance(item, dict):
            continue
        stem = str(item.get("stem") or item.get("question") or "").strip()
        if not stem:
            continue
        options = item.get("options") or []
        if not isinstance(options, list):
            options = []
        kind = str(item.get("kind") or ("choice" if options else "short")).strip().lower()
        if kind not in ("choice", "short", "essay"):
            kind = "choice" if options else "short"
        try:
            score = int(item.get("score") or 5)
        except (TypeError, ValueError):
            score = 5
        out.append(
            {
                "index": i + 1,
                "stem": stem,
                "kind": kind,
                "options": [str(o) for o in options][:8],
                "answer": str(item.get("answer") or item.get("correct_answer") or "").strip(),
                "score": max(1, min(score, 100)),
            }
        )
    return out


def questions_to_description(questions: list[dict], intro: str = "") -> str:
    lines: list[str] = []
    if intro.strip():
        lines.append(intro.strip())
        lines.append("")
    for q in questions:
        idx = q.get("index") or ""
        lines.append(f"{idx}. [{q.get('kind', 'short')}] {q.get('stem', '')}")
        for opt in q.get("options") or []:
            lines.append(f"   {opt}")
        ans = q.get("answer") or ""
        if ans:
            lines.append(f"   （参考答案：{ans}）")
        lines.append("")
    return "\n".join(lines).strip()


async def _ocr_image_to_text(image_bytes: bytes, content_type: str) -> str:
    from app.services.ark_vision import ark_vision_available, ark_vision_chat

    if not ark_vision_available():
        return ""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = content_type or "image/jpeg"
    raw = await ark_vision_chat(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "请完整识别图片中的文字（尤其是题目与选项），只输出识别到的纯文本，不要解释。",
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        temperature=0.2,
        timeout=90.0,
        endpoint="assignment_ocr_vision",
    )
    return (raw or "").strip()


async def extract_text_from_upload(
    *,
    filename: str,
    data: bytes,
    content_type: str = "",
) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".pdf") or "pdf" in ctype:
        text = extract_pdf_text(data)
        return (text or "").strip()
    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) or ctype.startswith("image/"):
        return await _ocr_image_to_text(data, content_type or "image/jpeg")
    if name.endswith((".md", ".txt", ".csv")) or ctype.startswith("text/"):
        for enc in ("utf-8", "gbk", "utf-16"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")
    # 其它类型：尝试按文本解码
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def resolve_resource_file(file_url: str) -> Optional[Path]:
    url = (file_url or "").strip()
    if not url:
        return None
    # /static/uploads/resources/xxx.md
    m = re.search(r"/static/uploads/(.+)$", url)
    if m:
        path = UPLOADS_DIR / m.group(1)
        if path.exists() and path.is_file():
            return path
    # 直接相对 resources
    name = Path(url).name
    if name:
        cand = RESOURCES_DIR / name
        if cand.exists():
            return cand
    return None


async def extract_questions_from_text(text: str, *, hint_title: str = "") -> dict:
    status = llm_status()
    preview = (text or "").strip()
    if len(preview) < 8:
        return {
            "title_suggestion": hint_title or "练习作业",
            "raw_text_preview": "",
            "questions": [],
            "provider": status.get("provider") or "",
            "message": "未能从文件中读取到有效文字，请换 PDF/图片/文本后重试",
        }
    if not llm_available():
        # 启发式切题：按「数字.」分行
        rough: list[dict] = []
        chunks = re.split(r"\n(?=\s*\d+[\.、．]\s*)", preview[:8000])
        for i, ch in enumerate(chunks[:20]):
            stem = ch.strip()
            if len(stem) < 4:
                continue
            rough.append(
                {
                    "index": i + 1,
                    "stem": stem[:800],
                    "kind": "short",
                    "options": [],
                    "answer": "",
                    "score": 5,
                }
            )
        return {
            "title_suggestion": hint_title or "练习作业",
            "raw_text_preview": preview[:1200],
            "questions": rough,
            "provider": "offline",
            "message": "未配置 DeepSeek/豆包，已按编号粗切题目，请人工校对",
        }

    clipped = preview[:12000]
    raw = await llm_chat(
        [
            {"role": "system", "content": "只输出 JSON，不要 Markdown 围栏外的说明。"},
            {"role": "user", "content": f"{EXTRACT_PROMPT}\n\n材料：\n{clipped}"},
        ],
        temperature=0.2,
        response_json=True,
        timeout=120.0,
        endpoint="assignment_extract",
    )
    questions: list[dict] = []
    title_suggestion = hint_title or "练习作业"
    if raw:
        parsed = extract_json(raw) or {}
        if isinstance(parsed, dict):
            title_suggestion = str(parsed.get("title_suggestion") or title_suggestion).strip() or title_suggestion
            qs = parsed.get("questions")
            if isinstance(qs, list):
                questions = _normalize_questions(qs)
        if not questions:
            lst = extract_json_list(raw)
            if lst:
                questions = _normalize_questions(lst)

    return {
        "title_suggestion": title_suggestion,
        "raw_text_preview": preview[:1200],
        "questions": questions,
        "provider": status.get("label") or status.get("provider") or "",
        "message": f"已提取 {len(questions)} 题" if questions else "未识别到题目，请检查文件或改用更清晰的扫描件",
    }


async def extract_questions_from_upload(
    *,
    filename: str,
    data: bytes,
    content_type: str = "",
    hint_title: str = "",
) -> dict:
    text = await extract_text_from_upload(filename=filename, data=data, content_type=content_type)
    return await extract_questions_from_text(text, hint_title=hint_title or Path(filename or "").stem)


async def extract_questions_from_resource_file(file_url: str, *, hint_title: str = "") -> dict:
    path = resolve_resource_file(file_url)
    if path is None:
        return {
            "title_suggestion": hint_title or "练习作业",
            "raw_text_preview": "",
            "questions": [],
            "provider": "",
            "message": "找不到知识库文件，请确认资料已上传",
        }
    data = path.read_bytes()
    return await extract_questions_from_upload(
        filename=path.name,
        data=data,
        content_type="",
        hint_title=hint_title,
    )
