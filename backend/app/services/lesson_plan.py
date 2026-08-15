"""为知识点行星生成结构化学习教案。"""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.schemas.galaxy import LessonPlanOut
from app.services.llm import extract_json, llm_chat, llm_available

LESSON_SYSTEM = """你是 SparkOrbit 星轨学图中的教案教练。请为给定知识点生成一份简洁、可执行的自学教案。
严格返回 JSON，不要 Markdown 或多余文字，格式：
{
  "learning_goals": ["学习目标1", "学习目标2", "学习目标3"],
  "teaching_approach": "80-150字的讲解思路，说明如何理解与学习该知识点",
  "example_problems": ["典型例题或思考题1", "典型例题或思考题2"],
  "common_mistakes": ["易错点1", "易错点2"],
  "practice_plan": ["练习安排1", "练习安排2", "练习安排3"],
  "self_check": ["自测清单1", "自测清单2", "自测清单3"]
}
要求：目标具体可检验；讲解思路面向学生自学；例题难度适中；易错点真实常见。"""


def _as_str_list(value: Any, fallback: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or fallback


def _fallback_plan(planet: Planet) -> LessonPlanOut:
    name = planet.name
    return LessonPlanOut(
        planet_slug=planet.slug,
        planet_name=name,
        learning_goals=[
            f"理解「{name}」的核心定义与适用场景",
            f"能用自己的话复述「{name}」的关键步骤或公式",
            f"完成至少一道与「{name}」相关的基础练习",
        ],
        teaching_approach=(
            f"先明确「{name}」要解决什么问题，再对照定义拆解关键要素，"
            f"最后用一道简单例题把概念落到解题步骤上。遇到卡点时对照易错点自查。"
        ),
        example_problems=[
            f"用一句话解释「{name}」是什么，并举一个生活或学科中的例子。",
            f"写出一道可用「{name}」解决的基础题，并列出解题步骤。",
        ],
        common_mistakes=[
            f"只背术语，不理解「{name}」的适用边界",
            "跳过例题直接做难题，导致步骤混乱",
        ],
        practice_plan=[
            "阅读教导摘要并勾画出关键词",
            "完成 1–2 道基础题并对照解析",
            "用错题本记录仍不清晰的步骤",
        ],
        self_check=[
            f"能否不看书说出「{name}」的定义？",
            "能否独立完成一道同类题？",
            "能否指出最容易出错的一步？",
        ],
    )


async def generate_lesson_plan(db: AsyncSession, slug: str) -> Optional[LessonPlanOut]:
    result = await db.execute(select(Planet).where(Planet.slug == slug))
    planet = result.scalar_one_or_none()
    if planet is None:
        return None

    if not llm_available():
        return _fallback_plan(planet)

    user_msg = (
        f"知识点：{planet.name}\n"
        f"描述：{planet.description or '无'}\n"
        f"难度：{planet.difficulty or 'MEDIUM'}\n"
        f"请生成自学教案。"
    )
    raw = await llm_chat(
        [
            {"role": "system", "content": LESSON_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.4,
        response_json=True,
        timeout=90,
    )
    data = extract_json(raw or "")
    if not data:
        return _fallback_plan(planet)

    fallback = _fallback_plan(planet)
    return LessonPlanOut(
        planet_slug=planet.slug,
        planet_name=planet.name,
        learning_goals=_as_str_list(data.get("learning_goals"), fallback.learning_goals),
        teaching_approach=str(data.get("teaching_approach") or fallback.teaching_approach).strip(),
        example_problems=_as_str_list(data.get("example_problems"), fallback.example_problems),
        common_mistakes=_as_str_list(data.get("common_mistakes"), fallback.common_mistakes),
        practice_plan=_as_str_list(data.get("practice_plan"), fallback.practice_plan),
        self_check=_as_str_list(data.get("self_check"), fallback.self_check),
    )
