"""教学课件 PPT 主题：自有配色与版式，不依赖第三方母版。"""
from __future__ import annotations

from typing import Any

DEFAULT_THEME = "orbit"

DECK_THEMES: dict[str, dict[str, Any]] = {
    "orbit": {
        "id": "orbit",
        "name": "星轨深空",
        "description": "深蓝底 + 青强调，贴合星轨学图。",
        "suitable": "默认 · 学习区",
        "bg": (8, 18, 40),
        "accent": (56, 189, 248),
        "title": (224, 242, 254),
        "body": (186, 230, 253),
        "bar": (14, 116, 144),
        "dark": True,
    },
    "chalkboard": {
        "id": "chalkboard",
        "name": "课堂白板",
        "description": "深绿底 + 米色字，适合课堂讲解。",
        "suitable": "课堂",
        "bg": (18, 42, 32),
        "accent": (250, 250, 232),
        "title": (254, 252, 232),
        "body": (233, 237, 201),
        "bar": (74, 124, 89),
        "dark": True,
    },
    "academic": {
        "id": "academic",
        "name": "学术答辩",
        "description": "白底 + 藏青/金，适合答辩与升学汇报。",
        "suitable": "答辩 · 升学",
        "bg": (250, 250, 249),
        "accent": (180, 138, 58),
        "title": (15, 23, 42),
        "body": (51, 65, 85),
        "bar": (30, 58, 95),
        "dark": False,
    },
    "fresh": {
        "id": "fresh",
        "name": "清新教研",
        "description": "浅底 + 薄荷/天蓝，适合公开课与低龄课堂。",
        "suitable": "公开课",
        "bg": (240, 253, 250),
        "accent": (45, 212, 191),
        "title": (15, 118, 110),
        "body": (51, 65, 85),
        "bar": (20, 184, 166),
        "dark": False,
    },
    "minimal": {
        "id": "minimal",
        "name": "极简黑白",
        "description": "高对比单色，方便打印。",
        "suitable": "打印",
        "bg": (255, 255, 255),
        "accent": (15, 23, 42),
        "title": (15, 23, 42),
        "body": (30, 41, 59),
        "bar": (15, 23, 42),
        "dark": False,
    },
}


def resolve_theme(theme_id: str | None) -> dict[str, Any]:
    key = (theme_id or "").strip() or DEFAULT_THEME
    return DECK_THEMES.get(key) or DECK_THEMES[DEFAULT_THEME]


def list_deck_templates() -> list[dict[str, Any]]:
    out = []
    for spec in DECK_THEMES.values():
        out.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "description": spec["description"],
                "suitable": spec["suitable"],
                "dark": bool(spec["dark"]),
                "colors": {
                    "bg": _css(spec["bg"]),
                    "accent": _css(spec["accent"]),
                    "title": _css(spec["title"]),
                    "body": _css(spec["body"]),
                    "bar": _css(spec["bar"]),
                },
            }
        )
    return out


def _css(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)
