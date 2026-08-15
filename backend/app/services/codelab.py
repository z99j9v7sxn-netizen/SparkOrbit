"""代码舱：AI 出题 / 提示 / 讲解；测例通过记用闸。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.user import User
from app.services import mastery_gates as gates
from app.services.rag import build_rag_context
from app.services.spark import extract_json, spark_chat


async def generate_exercise(session: AsyncSession, user: User, planet_slug: str) -> dict[str, Any]:
    _ = user
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        return {"ok": False, "detail": "planet not found"}
    rag = build_rag_context(planet.name)
    prompt = f"""为知识点「{planet.name}」出一道 Python 编程微习题。
说明：{planet.description}
{rag}
严格返回 JSON：
{{
  "title": "题目标题",
  "prompt": "题目描述",
  "starter_code": "def solve():\\n    pass\\n",
  "tests": [{{"stdin": "", "expected_stdout": "..."}}],
  "hint": "不直接给答案的提示",
  "solution_outline": "解题思路一句话"
}}"""
    raw = await spark_chat(
        [
            {"role": "system", "content": "你是 CodeLabCoachAgent，只返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )
    data = extract_json(raw) if raw else None
    if not data:
        data = {
            "title": f"{planet.name} 微习题",
            "prompt": f"编写函数演示「{planet.name}」的核心逻辑，打印一个可读结果。",
            "starter_code": "def solve():\n    print('todo')\n\nsolve()\n",
            "tests": [{"stdin": "", "expected_stdout": "todo"}],
            "hint": "先写出输入输出，再补核心分支。",
            "solution_outline": "用最小可运行示例覆盖定义与边界。",
        }
    data["planet_slug"] = planet_slug
    data["ok"] = True
    return data


async def coach_hint(planet_slug: str, code: str, question: str = "") -> dict[str, Any]:
    prompt = f"""学生在做「{planet_slug}」编程题。
题目补充：{question[:500]}
学生代码：\n{code[:3000]}\n
请给出苏格拉底式提示（不要直接给完整答案），返回 JSON：{{"hint":"...","next_question":"..."}}"""
    raw = await spark_chat(
        [
            {"role": "system", "content": "你是苏格拉底编程教练，只返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    data = extract_json(raw) if raw else None
    if not data:
        data = {"hint": "先写出一个最小例子的期望输出，再对照你的 print。", "next_question": "哪一行最先偏离了你的预期？"}
    return data


async def coach_explain(planet_slug: str, code: str, question: str = "") -> dict[str, Any]:
    """测例通过后或卡壳时：讲解思路（仍避免直接贴完整可抄答案）。"""
    prompt = f"""学生在做「{planet_slug}」编程题，需要讲解思路。
题目：{question[:800]}
学生当前代码：\n{code[:3000]}\n
返回 JSON：{{"explain":"分步骤讲解核心思路（不贴完整可运行答案）","pitfalls":"常见坑一点","next_step":"下一步可做什么"}}"""
    raw = await spark_chat(
        [
            {"role": "system", "content": "你是 CodeLab 讲解教练，只返回 JSON，禁止贴完整可抄答案。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
    )
    data = extract_json(raw) if raw else None
    if not data:
        data = {
            "explain": "先明确输入输出契约，再写最小可运行骨架，最后补边界。",
            "pitfalls": "别急着优化；先保证一个样例打印正确。",
            "next_step": "对照测例期望输出，逐步 print 中间变量。",
        }
    return data


async def mark_tests_passed(
    session: AsyncSession,
    user: User,
    *,
    planet_slug: str,
    passed: int,
    total: int,
) -> dict[str, Any]:
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        return {"ok": False}
    mastery = await gates.ensure_mastery(session, user.id, planet.id)
    snap = gates.gate_snapshot(mastery)
    lit = False
    if total > 0 and passed >= total:
        gates.pass_apply_gate(mastery)
        lit = gates.try_light_planet(mastery)
        if lit:
            user.points += 10
            session.add(user)
        snap = gates.gate_snapshot(mastery)
    await session.commit()
    return {"ok": True, "gates": snap, "lit": lit}
