"""星云求救信号 S.O.S：连败 3 次发射，高分学生跃迁应答。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.mastery import PlanetMastery
from app.models.social import WormholeMessage
from app.models.user import User

# 进程内 SOS 存储
_SOS_BEACONS: list[dict] = []


async def _consecutive_fails(session: AsyncSession, user_id: str, planet_id: str) -> int:
    from app.models.mastery import ChallengeQuestion

    rows = (
        await session.execute(
            select(ChallengeQuestion)
            .where(
                ChallengeQuestion.user_id == user_id,
                ChallengeQuestion.planet_id == planet_id,
                ChallengeQuestion.answered.is_(True),
            )
            .order_by(ChallengeQuestion.created_at.desc())
            .limit(5)
        )
    ).scalars().all()
    streak = 0
    for r in rows:
        if r.correct:
            break
        streak += 1
    return streak


async def emit_sos(
    session: AsyncSession, user: User, planet_slug: str
) -> dict | None:
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        return None

    fails = await _consecutive_fails(session, user.id, planet.id)
    if fails < 3:
        return {"ok": False, "message": f"需连续失败 3 次才可发射 SOS（当前 {fails}/3）", "fails": fails}

    beacon = {
        "id": str(uuid4()),
        "sender_id": user.id,
        "sender_name": user.display_name,
        "planet_slug": planet_slug,
        "planet_name": planet.name,
        "created_at": datetime.utcnow().isoformat(),
        "status": "open",
        "responses": [],
    }
    _SOS_BEACONS.insert(0, beacon)
    _SOS_BEACONS[:] = _SOS_BEACONS[:50]
    return {"ok": True, "beacon": beacon, "message": f"已向全宇宙发射求救信号：{planet.name}"}


async def list_sos(session: AsyncSession, user_id: str) -> list[dict]:
    """列出开放 SOS + 当前用户可应答的（已点亮该行星）。"""
    lit_planet_slugs: set[str] = set()
    rows = (
        await session.execute(
            select(PlanetMastery, Planet)
            .join(Planet, Planet.id == PlanetMastery.planet_id)
            .where(PlanetMastery.user_id == user_id, PlanetMastery.status == "lit")
        )
    ).all()
    for _, p in rows:
        lit_planet_slugs.add(p.slug)

    out = []
    for b in _SOS_BEACONS:
        if b["status"] != "open":
            continue
        can_respond = (
            b["sender_id"] != user_id and b["planet_slug"] in lit_planet_slugs
        )
        out.append({**b, "can_respond": can_respond, "is_mine": b["sender_id"] == user_id})
    return out


async def respond_sos(
    session: AsyncSession, responder: User, beacon_id: str, content: str
) -> dict | None:
    beacon = next((b for b in _SOS_BEACONS if b["id"] == beacon_id and b["status"] == "open"), None)
    if beacon is None:
        return None

    # 验证应答者已点亮该行星
    planet = (
        await session.execute(select(Planet).where(Planet.slug == beacon["planet_slug"]))
    ).scalar_one_or_none()
    if planet is None:
        return None

    mastery = (
        await session.execute(
            select(PlanetMastery).where(
                PlanetMastery.user_id == responder.id,
                PlanetMastery.planet_id == planet.id,
                PlanetMastery.status == "lit",
            )
        )
    ).scalar_one_or_none()
    if mastery is None:
        return {"ok": False, "message": "你尚未点亮该行星，无法跃迁应答"}

    msg = WormholeMessage(
        sender_id=responder.id,
        receiver_id=beacon["sender_id"],
        content=f"【SOS 跃迁】{beacon['planet_name']}：{content}",
    )
    session.add(msg)
    await session.commit()

    beacon["responses"].append(
        {
            "responder_id": responder.id,
            "responder_name": responder.display_name,
            "content": content,
            "at": datetime.utcnow().isoformat(),
        }
    )
    responder.points += 3
    session.add(responder)
    await session.commit()

    return {"ok": True, "message": "跃迁应答已送达求救者虫洞收件箱"}
