"""星际社交：排行榜、好友、虫洞通讯。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import PlanetMastery
from app.models.social import Friendship, WormholeMessage
from app.models.user import User
from app.schemas.galaxy import FriendItem, LeaderboardItem, WormholeMessageOut


async def _lit_counts(session: AsyncSession) -> dict[str, int]:
    rows = (
        await session.execute(
            select(PlanetMastery.user_id, func.count())
            .where(PlanetMastery.status == "lit")
            .group_by(PlanetMastery.user_id)
        )
    ).all()
    return {user_id: count for user_id, count in rows}


async def leaderboard(session: AsyncSession, current_user_id: str, limit: int = 20) -> list[LeaderboardItem]:
    students = (
        await session.execute(select(User).where(User.role == "student"))
    ).scalars().all()
    counts = await _lit_counts(session)

    ranked = sorted(
        students,
        key=lambda u: (counts.get(u.id, 0), u.points),
        reverse=True,
    )
    out: list[LeaderboardItem] = []
    for i, u in enumerate(ranked[:limit]):
        out.append(
            LeaderboardItem(
                rank=i + 1,
                user_id=u.id,
                display_name=u.display_name,
                lit_count=counts.get(u.id, 0),
                points=u.points,
                is_me=(u.id == current_user_id),
            )
        )
    return out


async def list_friends(session: AsyncSession, user_id: str) -> list[FriendItem]:
    friend_ids = (
        await session.execute(select(Friendship.friend_id).where(Friendship.user_id == user_id))
    ).scalars().all()
    if not friend_ids:
        return []
    counts = await _lit_counts(session)
    friends = (
        await session.execute(select(User).where(User.id.in_(friend_ids)))
    ).scalars().all()
    return [
        FriendItem(
            user_id=f.id,
            display_name=f.display_name,
            username=f.username,
            lit_count=counts.get(f.id, 0),
            points=f.points,
        )
        for f in friends
    ]


async def add_friend(session: AsyncSession, user_id: str, friend_username: str) -> FriendItem | None:
    friend = (
        await session.execute(select(User).where(User.username == friend_username))
    ).scalar_one_or_none()
    if friend is None or friend.id == user_id:
        return None

    for a, b in ((user_id, friend.id), (friend.id, user_id)):
        exists = (
            await session.execute(
                select(Friendship).where(Friendship.user_id == a, Friendship.friend_id == b)
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(Friendship(user_id=a, friend_id=b))
    await session.commit()

    counts = await _lit_counts(session)
    return FriendItem(
        user_id=friend.id,
        display_name=friend.display_name,
        username=friend.username,
        lit_count=counts.get(friend.id, 0),
        points=friend.points,
    )


async def send_wormhole(session: AsyncSession, sender_id: str, receiver_id: str, content: str) -> WormholeMessage:
    msg = WormholeMessage(sender_id=sender_id, receiver_id=receiver_id, content=content)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def list_wormhole(session: AsyncSession, user_id: str) -> list[WormholeMessageOut]:
    msgs = (
        await session.execute(
            select(WormholeMessage)
            .where(WormholeMessage.receiver_id == user_id)
            .order_by(WormholeMessage.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    if not msgs:
        return []
    sender_ids = {m.sender_id for m in msgs}
    senders = (
        await session.execute(select(User).where(User.id.in_(sender_ids)))
    ).scalars().all()
    name_map = {s.id: s.display_name for s in senders}
    return [
        WormholeMessageOut(
            id=m.id,
            sender_id=m.sender_id,
            sender_name=name_map.get(m.sender_id, "神秘领航员"),
            receiver_id=m.receiver_id,
            content=m.content,
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in msgs
    ]
