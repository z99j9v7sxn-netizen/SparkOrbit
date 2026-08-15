"""星座成就系统：关联知识点全点亮后构成星座并发放徽章。"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.mastery import PlanetMastery

# 预定义星座（行星 slug 来自 seed_content）
CONSTELLATION_DEFS = [
    {
        "slug": "transport-trio",
        "name": "传输三杰座",
        "description": "TCP + UDP + IP 传输层核心星座",
        "planet_slugs": ["tcp-protocol", "udp-protocol", "ip-basics"],
        "badge_icon": "🛰️",
    },
    {
        "slug": "tree-constellation",
        "name": "二叉树星座",
        "description": "树结构与搜索的经典组合",
        "planet_slugs": ["binary-tree", "bst", "heap"],
        "badge_icon": "🌳",
    },
    {
        "slug": "os-core",
        "name": "内核守护座",
        "description": "进程、调度与同步的核心三角",
        "planet_slugs": ["process-thread", "cpu-scheduling", "sync-mutex"],
        "badge_icon": "⚙️",
    },
    {
        "slug": "sql-trail",
        "name": "SQL 星链座",
        "description": "关系模型到事务的 SQL 进阶链",
        "planet_slugs": ["relational-model", "sql-basics", "join", "transaction"],
        "badge_icon": "💾",
    },
]


async def _lit_slugs(session: AsyncSession, user_id: str) -> set[str]:
    rows = (
        await session.execute(
            select(PlanetMastery, Planet)
            .join(Planet, Planet.id == PlanetMastery.planet_id)
            .where(PlanetMastery.user_id == user_id, PlanetMastery.status == "lit")
        )
    ).all()
    return {p.slug for _, p in rows}


async def list_constellations(session: AsyncSession, user_id: str) -> List[dict]:
    lit = await _lit_slugs(session, user_id)
    out: List[dict] = []
    for c in CONSTELLATION_DEFS:
        slugs = c["planet_slugs"]
        lit_count = sum(1 for s in slugs if s in lit)
        completed = lit_count == len(slugs)
        out.append(
            {
                "slug": c["slug"],
                "name": c["name"],
                "description": c["description"],
                "badge_icon": c["badge_icon"],
                "planet_slugs": slugs,
                "lit_count": lit_count,
                "total": len(slugs),
                "completed": completed,
            }
        )
    return out


async def check_newly_completed(
    session: AsyncSession, user_id: str, just_lit_slug: str
) -> Optional[dict]:
    """点亮某行星后检查是否新完成某个星座。"""
    lit = await _lit_slugs(session, user_id)
    if just_lit_slug not in lit:
        lit.add(just_lit_slug)

    for c in CONSTELLATION_DEFS:
        if just_lit_slug not in c["planet_slugs"]:
            continue
        if all(s in lit for s in c["planet_slugs"]):
            return {
                "slug": c["slug"],
                "name": c["name"],
                "badge_icon": c["badge_icon"],
                "planet_slugs": c["planet_slugs"],
                "message": f"恭喜！你已点亮「{c['name']}」星座，获得专属 3D 徽章！",
            }
    return None
