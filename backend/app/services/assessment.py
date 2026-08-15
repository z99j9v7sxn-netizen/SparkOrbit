"""引力黑洞初测：新星系解锁时的 5 道连环摸底测试。"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Galaxy, Planet
from app.models.mastery import PlanetMastery
from app.models.user import User
from app.services.spark import extract_json, spark_chat

# 进程内会话存储（assessment_id -> session data）
_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _fallback_questions(galaxy: Galaxy, planets: List[Planet]) -> List[dict]:
    picks = planets[:5] if len(planets) >= 5 else planets
    while len(picks) < 5 and planets:
        picks.append(planets[len(picks) % len(planets)])
    questions = []
    for i, p in enumerate(picks[:5]):
        questions.append(
            {
                "index": i,
                "planet_slug": p.slug,
                "planet_name": p.name,
                "question": f"关于「{p.name}」，下列哪项最能体现其核心概念？",
                "options": [
                    {"key": "A", "text": f"{p.name} 的核心定义与应用"},
                    {"key": "B", "text": "完全无关的干扰项"},
                    {"key": "C", "text": "常见错误理解"},
                    {"key": "D", "text": "相邻但不同的概念"},
                ],
                "answer_key": "A",
            }
        )
    return questions


async def _generate_questions(galaxy: Galaxy, planets: List[Planet]) -> List[dict]:
    planet_names = "、".join(p.name for p in planets[:8])
    system = (
        "你是 Teacher Agent。请为星系摸底测试生成 5 道连环单选题。"
        "严格返回 JSON：{\"questions\":[{\"question\":\"题干\",\"options\":[{\"key\":\"A\",\"text\":\"...\"},...],"
        "\"answer_key\":\"A\",\"planet_slug\":\"对应行星slug\"}]}。"
        "题目由易到难，每题对应一个知识点。"
    )
    user = f"星系：{galaxy.name}\n描述：{galaxy.description}\n行星：{planet_names}\n请生成 5 题。"
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.6,
    )
    data = extract_json(raw) if raw else None
    if not data or not isinstance(data.get("questions"), list):
        return _fallback_questions(galaxy, planets)

    slug_set = {p.slug for p in planets}
    slug_map = {p.slug: p for p in planets}
    out: List[dict] = []
    for i, q in enumerate(data["questions"][:5]):
        slug = str(q.get("planet_slug", ""))
        if slug not in slug_set and planets:
            slug = planets[i % len(planets)].slug
        planet = slug_map.get(slug) or planets[0]
        options = q.get("options") or []
        if len(options) < 2:
            continue
        out.append(
            {
                "index": i,
                "planet_slug": planet.slug,
                "planet_name": planet.name,
                "question": str(q.get("question", f"关于 {planet.name} 的基础问题")),
                "options": [{"key": str(o.get("key")), "text": str(o.get("text"))} for o in options],
                "answer_key": str(q.get("answer_key", "A")).strip().upper()[:1],
            }
        )
    return out if len(out) >= 3 else _fallback_questions(galaxy, planets)


async def start_assessment(session: AsyncSession, user: User, galaxy_slug: str) -> Optional[Dict[str, Any]]:
    galaxy = (await session.execute(select(Galaxy).where(Galaxy.slug == galaxy_slug))).scalar_one_or_none()
    if galaxy is None:
        return None
    planets = (
        await session.execute(
            select(Planet).where(Planet.galaxy_id == galaxy.id).order_by(Planet.sort_order)
        )
    ).scalars().all()
    if not planets:
        return None

    questions = await _generate_questions(galaxy, planets)
    assessment_id = f"bh-{uuid.uuid4().hex[:10]}"
    _SESSIONS[assessment_id] = {
        "user_id": user.id,
        "galaxy_slug": galaxy_slug,
        "questions": questions,
        "answers": [],
        "current_index": 0,
    }
    first = questions[0]
    return {
        "assessment_id": assessment_id,
        "galaxy_slug": galaxy_slug,
        "galaxy_name": galaxy.name,
        "total": len(questions),
        "current_index": 0,
        "question": first["question"],
        "options": first["options"],
        "planet_name": first["planet_name"],
    }


async def submit_answer(
    session: AsyncSession, user: User, assessment_id: str, selected_key: str
) -> Optional[Dict[str, Any]]:
    data = _SESSIONS.get(assessment_id)
    if data is None or data["user_id"] != user.id:
        return None

    idx = data["current_index"]
    questions: List[dict] = data["questions"]
    if idx >= len(questions):
        return None

    q = questions[idx]
    correct = selected_key.strip().upper()[:1] == q["answer_key"]
    data["answers"].append({"index": idx, "correct": correct, "planet_slug": q["planet_slug"]})
    data["current_index"] += 1

    # 完成全部题目
    if data["current_index"] >= len(questions):
        lit_planets: List[str] = []
        unlocked: List[str] = []
        correct_count = sum(1 for a in data["answers"] if a["correct"])
        # 初测只解锁探索，不直接 lit
        from app.services import mastery_gates as gates

        for ans in data["answers"]:
            if ans["correct"]:
                planet = (
                    await session.execute(select(Planet).where(Planet.slug == ans["planet_slug"]))
                ).scalar_one_or_none()
                if planet is None:
                    continue
                mastery = await gates.ensure_mastery(session, user.id, planet.id)
                gates.bootstrap_from_assessment(mastery)
                unlocked.append(planet.slug)
                user.points += 5

        session.add(user)
        await session.commit()
        del _SESSIONS[assessment_id]
        return {
            "done": True,
            "correct_count": correct_count,
            "total": len(questions),
            "lit_planets": lit_planets,
            "unlocked_planets": unlocked,
            "message": (
                f"黑洞初测完成！答对 {correct_count}/{len(questions)} 题，"
                f"已解锁 {len(unlocked)} 颗行星的探索权（需完成学→练→讲→用四闸后点亮）。"
            ),
        }

    next_q = questions[data["current_index"]]
    return {
        "done": False,
        "correct": correct,
        "current_index": data["current_index"],
        "total": len(questions),
        "question": next_q["question"],
        "options": next_q["options"],
        "planet_name": next_q["planet_name"],
    }
