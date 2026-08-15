"""恒星档案馆：提取论文文本并生成结构化润色建议。"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional

from app.services.galaxy_forge import extract_pdf_text
from app.services.llm import extract_json, llm_available, llm_chat

logger = logging.getLogger(__name__)

# 短文本可返回全文润色；长文本只返回逐条修改，避免超时/截断
FULL_REVISE_CHAR_LIMIT = 3000


def extract_document_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_text(data)
    if suffix == ".txt":
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return ""
    if suffix == ".docx":
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("服务端未安装 Word 文档解析组件") from exc
        document = Document(io.BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
    if suffix == ".doc":
        raise ValueError("旧版 .doc 暂不支持解析，请在 Word 中另存为 .docx 后上传")
    raise ValueError("仅支持 PDF、DOCX、DOC 和 TXT 文件")


def _fallback_result(text: str, *, reason: str = "unconfigured") -> dict[str, Any]:
    if reason == "unconfigured":
        suggestion = "当前未配置智能润色服务，已完成文本提取，暂时无法生成润色结果。"
        detail = "请配置 DEEPSEEK_API_KEY 后重新扫描。"
    else:
        suggestion = "智能服务暂时不可用，已完成文本提取，暂时无法生成润色结果。"
        detail = "请检查网络连接、API 密钥有效性或稍后重试。"
    return {
        "original": text,
        "revised": text,
        "issues": [{"original": "", "suggestion": suggestion, "reason": detail}],
        "originality_tips": [
            "明确标注所有直接引用的来源。",
            "用自己的论证结构重述观点，不要只替换同义词。",
            "提交前核对参考文献格式与正文引用是否对应。",
        ],
    }


async def _call_polish_llm(system: str, user_content: str) -> Optional[str]:
    """调用润色模型，失败后重试一次。"""
    raw = await llm_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.25,
        response_json=True,
        timeout=300,
    )
    if raw:
        return raw
    logger.warning("polish_archive_text: first llm_chat attempt empty, retrying once")
    return await llm_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=0.25,
        response_json=True,
        timeout=300,
    )


async def polish_archive_text(text: str) -> dict[str, Any]:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("文档中没有可供润色的文本")
    if not llm_available():
        return _fallback_result(clean_text, reason="unconfigured")

    short_mode = len(clean_text) <= FULL_REVISE_CHAR_LIMIT
    if short_mode:
        system = (
            "你是 SparkOrbit 恒星档案馆的学术写作导师。请对论文文本进行严谨润色，"
            "修复语法、用词、逻辑衔接和学术表达问题，同时提供降低无意重复风险的原创性写作建议。"
            "不得捏造事实或文献。严格返回 JSON 对象："
            '{"revised":"完整润色文本","issues":[{"original":"原片段","suggestion":"建议片段",'
            '"reason":"修改原因"}],"originality_tips":["建议"]}。issues 最多 12 条。'
        )
    else:
        system = (
            "你是 SparkOrbit 恒星档案馆的学术写作导师。当前文档较长，请勿返回完整润色全文，"
            "只挑选最重要的语法、用词、逻辑与学术表达问题给出逐条修改建议，"
            "并提供降低无意重复风险的原创性写作建议。不得捏造事实或文献。"
            "严格返回 JSON 对象："
            '{"revised":"","issues":[{"original":"原片段","suggestion":"建议片段",'
            '"reason":"修改原因"}],"originality_tips":["建议"]}。'
            "issues 最多 12 条；revised 请返回空字符串。"
        )

    raw = await _call_polish_llm(system, clean_text[:16000])
    if not raw:
        logger.warning("polish_archive_text: llm_chat returned empty after retry")
        return _fallback_result(clean_text, reason="service_error")
    result = extract_json(raw)
    if not result:
        logger.warning("polish_archive_text: failed to parse JSON from llm response")
        return _fallback_result(clean_text, reason="service_error")
    issues = result.get("issues")
    tips = result.get("originality_tips")
    revised = str(result.get("revised") or "").strip()
    if not revised or not short_mode:
        revised = clean_text
    return {
        "original": clean_text,
        "revised": revised,
        "issues": issues if isinstance(issues, list) else [],
        "originality_tips": tips if isinstance(tips, list) else [],
    }
