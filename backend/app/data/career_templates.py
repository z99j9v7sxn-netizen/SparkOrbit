"""站内高级简历模板：校招金标 / 藏青侧栏 / 学术卷宗 / 网申安全稿。"""
from __future__ import annotations

from typing import Any

RESUME_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "editorial",
        "name": "金标校招",
        "description": "右上证件照、求职意向顶栏、32/68 双栏，适合投本地与线下。",
        "suitable": "校招 · 带照片",
        "accent": "#b8860b",
        "allow_photo": True,
        "tier": "premium",
    },
    {
        "id": "navy_rail",
        "name": "藏青侧栏",
        "description": "左栏深蓝放照片与技能标签，右栏时间轴经历。高端主视觉。",
        "suitable": "校招 · 高端",
        "accent": "#1e3a5f",
        "allow_photo": True,
        "tier": "premium",
    },
    {
        "id": "folio",
        "name": "学术卷宗",
        "description": "证件照 + 衬线章节，教育 / 论文 / 竞赛 / 项目，适合升学。",
        "suitable": "升学 · 科研",
        "accent": "#4c1d95",
        "allow_photo": True,
        "tier": "premium",
    },
    {
        "id": "ats_plain",
        "name": "网申安全稿",
        "description": "单栏无图无侧栏，给大厂 ATS 网申。此套不放照片。",
        "suitable": "ATS · 无照片",
        "accent": "#334155",
        "allow_photo": False,
        "tier": "ats",
    },
]

# 旧 id 兼容
_ALIASES = {
    "campus_one_pager": "editorial",
    "intern_star": "navy_rail",
    "academic": "folio",
    "ats_en": "ats_plain",
}

OPEN_SOURCE_LINKS: list[dict[str, str]] = [
    {
        "id": "hijiangtao",
        "name": "hijiangtao/resume",
        "license": "MIT",
        "url": "https://github.com/hijiangtao/resume/",
        "note": "仅排版参考，请用上方站内模板导出。",
    },
]


def resolve_template_id(template_id: str) -> str:
    key = (template_id or "").strip() or "editorial"
    return _ALIASES.get(key, key)


def list_resume_templates() -> dict[str, Any]:
    return {"templates": list(RESUME_TEMPLATES), "open_source": list(OPEN_SOURCE_LINKS)}


def get_resume_template(template_id: str) -> dict[str, Any] | None:
    key = resolve_template_id(template_id)
    for item in RESUME_TEMPLATES:
        if item["id"] == key:
            return item
    return None
