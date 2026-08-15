"""简历解析：复用档案馆文档抽取 + LLM 结构化。"""
from __future__ import annotations

from typing import Any

from fastapi import UploadFile

from app.core.paths import INTERVIEW_DIR
from app.services.archive_service import extract_document_text
from app.services.llm import extract_json, llm_available, llm_chat
from app.services.upload_service import save_upload_file

ALLOWED_RESUME_SUFFIX = {".pdf", ".docx", ".txt"}


async def save_and_parse_resume(file: UploadFile, user_id: str = "") -> dict[str, Any]:
    name = (file.filename or "resume.bin").lower()
    suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if suffix not in ALLOWED_RESUME_SUFFIX:
        raise ValueError("仅支持 PDF / DOCX / TXT 简历")
    url = await save_upload_file(file, INTERVIEW_DIR, "interview")
    # save_upload_file 已经读完文件；重新从磁盘取字节
    from pathlib import Path

    filename = url.rsplit("/", 1)[-1]
    data = (INTERVIEW_DIR / filename).read_bytes()
    text = extract_document_text(filename, data)
    profile = await structure_resume(text, user_id=user_id)
    preview = (text or "").strip().replace("\r", "")[:400]
    return {"url": url, "profile": profile, "text_preview": preview, "text": text}


async def structure_resume(text: str, user_id: str = "") -> dict[str, Any]:
    snippet = (text or "").strip()[:6000]
    empty = {
        "name": "",
        "education": [],
        "skills": [],
        "projects": [],
        "experience": [],
        "highlights": [],
        "raw_preview": snippet[:240],
    }
    if not snippet:
        return empty
    if not llm_available():
        empty["highlights"] = [line.strip() for line in snippet.splitlines() if line.strip()][:6]
        return empty
    raw = await llm_chat(
        [
            {
                "role": "system",
                "content": (
                    "你是简历解析器。只返回 JSON："
                    '{"name":"","education":["学校/专业/时间"],"skills":["技能"],'
                    '"projects":[{"name":"","role":"","highlight":""}],'
                    '"experience":[{"org":"","role":"","highlight":""}],'
                    '"highlights":["可追问的亮点"]}'
                ),
            },
            {"role": "user", "content": f"简历文本：\n{snippet}"},
        ],
        temperature=0.2,
        response_json=True,
        user_id=user_id,
        endpoint="interview_resume",
    )
    data = extract_json(raw or "") or {}
    empty["name"] = str(data.get("name") or "")
    empty["education"] = list(data.get("education") or [])[:8]
    empty["skills"] = list(data.get("skills") or [])[:20]
    empty["projects"] = list(data.get("projects") or [])[:8]
    empty["experience"] = list(data.get("experience") or [])[:8]
    empty["highlights"] = list(data.get("highlights") or [])[:8]
    return empty


def _profile_text(profile: dict[str, Any] | None, text: str = "") -> str:
    if (text or "").strip():
        return text.strip()[:6000]
    if not profile:
        return ""
    parts = [
        str(profile.get("name") or ""),
        "技能：" + "、".join(str(s) for s in (profile.get("skills") or [])[:16]),
        "教育：" + "；".join(str(s) for s in (profile.get("education") or [])[:6]),
        "亮点：" + "；".join(str(h) for h in (profile.get("highlights") or [])[:8]),
    ]
    return "\n".join(p for p in parts if p).strip()[:6000]


def _fallback_optimize(profile: dict[str, Any] | None, target_role: str) -> dict[str, Any]:
    skills = [str(s) for s in (profile or {}).get("skills") or []][:8]
    highlights = [str(h) for h in (profile or {}).get("highlights") or []][:6]
    issues = ["项目描述缺少可验证的量化结果（人数、耗时、指标前后对比）"]
    if not skills:
        issues.append("技能栏过空，ATS 很难匹配岗位关键词")
    bullets = highlights or skills or ["用 STAR 重写一条项目经历：情境、任务、行动、结果"]
    md = f"## {target_role or '目标岗位'} 要点\n" + "\n".join(f"- {b}" for b in bullets)
    return {
        "score": 52,
        "issues": issues[:6],
        "rewritten_markdown": md,
        "ats_keywords": skills or [target_role or "实习"],
        "degraded": True,
    }


async def optimize_resume(
    *,
    text: str = "",
    profile: dict[str, Any] | None = None,
    target_role: str = "",
    jd: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    snippet = _profile_text(profile, text)
    if not snippet:
        return {
            "score": 0,
            "issues": ["请先上传或粘贴简历"],
            "rewritten_markdown": "",
            "ats_keywords": [],
            "degraded": True,
        }
    if not llm_available():
        return _fallback_optimize(profile, target_role)
    raw = await llm_chat(
        [
            {
                "role": "system",
                "content": (
                    "你是校招简历教练。只返回 JSON："
                    '{"score":0,"issues":["问题"],"rewritten_markdown":"Markdown要点",'
                    '"ats_keywords":["关键词"]}'
                    "score 为 0-100。issues 指出空泛、缺量化、动词弱、版式不利于 ATS。"
                    "rewritten_markdown 用 STAR 改写 4-8 条要点，不要编造经历。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"目标岗位：{target_role or '未指定'}\n"
                    f"职位描述：{(jd or '未提供')[:2500]}\n"
                    f"简历：\n{snippet}"
                ),
            },
        ],
        temperature=0.3,
        response_json=True,
        user_id=user_id,
        endpoint="interview_resume_optimize",
    )
    data = extract_json(raw or "") or {}
    try:
        score = int(float(data.get("score") or 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    issues = [str(x) for x in (data.get("issues") or []) if str(x).strip()][:8]
    keywords = [str(x) for x in (data.get("ats_keywords") or []) if str(x).strip()][:16]
    md = str(data.get("rewritten_markdown") or "").strip()
    if not md:
        fallback = _fallback_optimize(profile, target_role)
        md = fallback["rewritten_markdown"]
        issues = issues or fallback["issues"]
        keywords = keywords or fallback["ats_keywords"]
    return {
        "score": score,
        "issues": issues or ["表述可以更具体"],
        "rewritten_markdown": md[:6000],
        "ats_keywords": keywords,
        "degraded": False,
    }


def _fallback_match(profile: dict[str, Any] | None, target_role: str) -> dict[str, Any]:
    from app.data.career_portals import portal_brief

    skills = [str(s) for s in (profile or {}).get("skills") or []][:8]
    return {
        "score": 45 if skills else 30,
        "matched": skills[:4],
        "gaps": ["补充与目标岗位直接相关的项目量化结果", "把课程作业改写成可验证的产出"],
        "prep_suggestions": [
            f"去练习舱练「{target_role or '目标岗位'}」项目经历题",
            "用优化后的要点再开一场面试舱",
        ],
        "recommended_portals": portal_brief(),
        "degraded": True,
    }


async def match_resume(
    *,
    text: str = "",
    profile: dict[str, Any] | None = None,
    target_role: str = "",
    jd: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    from app.data.career_portals import portal_brief

    snippet = _profile_text(profile, text)
    if not snippet:
        empty = _fallback_match(profile, target_role)
        empty["score"] = 0
        empty["gaps"] = ["请先上传或粘贴简历"]
        return empty
    if not llm_available():
        return _fallback_match(profile, target_role)
    raw = await llm_chat(
        [
            {
                "role": "system",
                "content": (
                    "你是校招岗位匹配官。只返回 JSON："
                    '{"score":0,"matched":["已覆盖"],"gaps":["缺口"],"prep_suggestions":["建议"]}'
                    "score 为 0-100。不要编造简历里没有的技能。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"目标岗位：{target_role or '未指定'}\n"
                    f"职位描述：{(jd or '未提供')[:2500]}\n"
                    f"简历：\n{snippet}"
                ),
            },
        ],
        temperature=0.2,
        response_json=True,
        user_id=user_id,
        endpoint="interview_resume_match",
    )
    data = extract_json(raw or "") or {}
    try:
        score = int(float(data.get("score") or 0))
    except (TypeError, ValueError):
        score = 0
    return {
        "score": max(0, min(100, score)),
        "matched": [str(x) for x in (data.get("matched") or []) if str(x).strip()][:12],
        "gaps": [str(x) for x in (data.get("gaps") or []) if str(x).strip()][:8],
        "prep_suggestions": [str(x) for x in (data.get("prep_suggestions") or []) if str(x).strip()][:6],
        "recommended_portals": portal_brief(),
        "degraded": False,
    }


def export_resume_docx(fields: dict[str, Any], template_id: str = "editorial") -> bytes:
    from app.services.resume_export import export_resume_docx as _export

    return _export(fields, template_id)


def resume_brief(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "（未提供简历）"
    skills = "、".join(str(s) for s in (profile.get("skills") or [])[:8]) or "未列出"
    projects = profile.get("projects") or []
    proj = ""
    if projects:
        first = projects[0] if isinstance(projects[0], dict) else {"name": str(projects[0])}
        proj = str(first.get("name") or first.get("highlight") or "")
    highlights = "；".join(str(h) for h in (profile.get("highlights") or [])[:4])
    return f"技能：{skills}。代表项目：{proj or '无'}。亮点：{highlights or '无'}"
