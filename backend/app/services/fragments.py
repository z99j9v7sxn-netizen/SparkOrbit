"""行星碎片收集：Companion Agent 闯关授予知识碎片。"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.mastery import PlanetMastery

DEFAULT_FRAGMENTS = [
    {"id": "core", "name": "核心概念", "icon": "💎"},
    {"id": "example", "name": "典型案例", "icon": "🔮"},
    {"id": "trap", "name": "易错陷阱", "icon": "⚠️"},
    {"id": "practice", "name": "实战演练", "icon": "🎯"},
]


def _ensure_fragments(mastery: PlanetMastery) -> List[dict]:
    frags = mastery.fragments or []
    if not frags:
        frags = [{**f, "collected": False} for f in DEFAULT_FRAGMENTS]
        mastery.fragments = frags
    return frags


def get_fragment_progress(mastery: Optional[PlanetMastery]) -> Dict[str, Any]:
    if mastery is None:
        frags = [{**f, "collected": False} for f in DEFAULT_FRAGMENTS]
    else:
        frags = _ensure_fragments(mastery)
    collected = sum(1 for f in frags if f.get("collected"))
    total = len(frags)
    return {
        "fragments": frags,
        "collected_count": collected,
        "total": total,
        "complete": collected >= total,
        "halo": collected >= total and mastery and mastery.status == "lit",
    }


async def grant_fragment_on_chat(
    session: AsyncSession, user_id: str, planet_slug: str, message: str
) -> Optional[Dict[str, Any]]:
    """伴学聊天闯关：根据对话深度授予碎片。"""
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        return None

    mastery = (
        await session.execute(
            select(PlanetMastery).where(
                PlanetMastery.user_id == user_id, PlanetMastery.planet_id == planet.id
            )
        )
    ).scalar_one_or_none()
    if mastery is None:
        mastery = PlanetMastery(user_id=user_id, planet_id=planet.id, status="dim")
        session.add(mastery)
        await session.flush()

    frags = _ensure_fragments(mastery)
    msg_len = len(message.strip())
    # 根据消息长度与轮次授予下一块未收集碎片
    uncollected = [f for f in frags if not f.get("collected")]
    if not uncollected:
        return get_fragment_progress(mastery)

    if msg_len >= 8:
        target = uncollected[0]
        target["collected"] = True
        mastery.fragments = frags
        session.add(mastery)
        await session.commit()

        progress = get_fragment_progress(mastery)
        if progress["complete"]:
            progress["burst"] = True
            progress["message"] = f"碎片集齐！{planet.name} 爆发出绚丽光晕！"
        else:
            progress["message"] = f"获得碎片「{target['name']}」"
        return progress

    return get_fragment_progress(mastery)
