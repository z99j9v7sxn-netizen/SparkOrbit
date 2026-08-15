import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_room import ChatMessageReaction, ChatRoom, ChatRoomMember, ChatRoomMessage
from app.models.user import User

logger = logging.getLogger(__name__)

_ws_connections: dict[str, set] = {}


def user_avatar_url(user: User | None) -> str:
    if user is None:
        return ""
    return (user.avatar_cartoon_url or user.avatar or "").strip()


def register_ws(room_id: str, websocket) -> None:
    _ws_connections.setdefault(room_id, set()).add(websocket)


def unregister_ws(room_id: str, websocket) -> None:
    conns = _ws_connections.get(room_id)
    if not conns:
        return
    conns.discard(websocket)
    if not conns:
        _ws_connections.pop(room_id, None)


async def broadcast_room(room_id: str, payload: dict) -> None:
    dead = []
    for ws in list(_ws_connections.get(room_id, set())):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_ws(room_id, ws)


TOPIC_TEMPLATES = [
    ("#数学求助", "math"),
    ("#物理讨论", "physics"),
    ("#编程交流", "code"),
]


async def _add_classmates_to_room(session: AsyncSession, room_id: str, class_id: str, exclude_user_id: str = "") -> None:
    if not class_id:
        return
    classmates = (
        await session.execute(
            select(User).where(User.class_id == class_id, User.role == "student")
        )
    ).scalars().all()
    for mate in classmates:
        if mate.id == exclude_user_id:
            continue
        member = (
            await session.execute(
                select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == mate.id)
            )
        ).scalar_one_or_none()
        if member is None:
            session.add(ChatRoomMember(room_id=room_id, user_id=mate.id))


async def ensure_topic_rooms(session: AsyncSession, user: User) -> None:
    if not user.class_id:
        return
    for title, _tag in TOPIC_TEMPLATES:
        room = (
            await session.execute(
                select(ChatRoom).where(
                    ChatRoom.room_type == "topic",
                    ChatRoom.class_id == user.class_id,
                    ChatRoom.title == title,
                )
            )
        ).scalar_one_or_none()
        if room is None:
            room = ChatRoom(room_type="topic", title=title, class_id=user.class_id, created_by=user.id)
            session.add(room)
            await session.flush()
        await _add_classmates_to_room(session, room.id, user.class_id)
    await session.commit()


async def ensure_class_room_for_student(session: AsyncSession, user: User) -> ChatRoom | None:
    if not user.class_id:
        return None
    from app.models.school_class import SchoolClass

    cls = (await session.execute(select(SchoolClass).where(SchoolClass.id == user.class_id))).scalar_one_or_none()
    if cls is None:
        return None

    room = (
        await session.execute(
            select(ChatRoom).where(ChatRoom.room_type == "class", ChatRoom.class_id == user.class_id)
        )
    ).scalar_one_or_none()
    if room is None:
        room = ChatRoom(room_type="class", title=f"{cls.name} 群聊", class_id=user.class_id, created_by=cls.teacher_id)
        session.add(room)
        await session.flush()

    member = (
        await session.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room.id, ChatRoomMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if member is None:
        session.add(ChatRoomMember(room_id=room.id, user_id=user.id))
        await session.commit()
    await ensure_topic_rooms(session, user)
    return room


async def create_topic_room(session: AsyncSession, user: User, title: str) -> ChatRoom | None:
    if not user.class_id:
        return None
    title = title.strip()
    if not title.startswith("#"):
        title = f"#{title}"
    room = ChatRoom(room_type="topic", title=title, class_id=user.class_id, created_by=user.id)
    session.add(room)
    await session.flush()
    session.add(ChatRoomMember(room_id=room.id, user_id=user.id))
    await _add_classmates_to_room(session, room.id, user.class_id, exclude_user_id=user.id)
    await session.commit()
    await session.refresh(room)

    from app.services.notification_service import create_notification

    classmates = (
        await session.execute(
            select(User).where(User.class_id == user.class_id, User.id != user.id, User.role == "student")
        )
    ).scalars().all()
    for mate in classmates:
        await create_notification(
            session,
            mate.id,
            "新话题频道",
            f"{user.display_name} 创建了话题 {title}",
            kind="chat",
            link=f"chat:{room.id}",
        )
    return room


async def create_group_room(session: AsyncSession, user: User, title: str, member_ids: list[str]) -> ChatRoom | None:
    title = title.strip() or "星际小组"
    room = ChatRoom(room_type="group", title=title, class_id=user.class_id or "", created_by=user.id)
    session.add(room)
    await session.flush()
    all_members = {user.id, *member_ids}
    for uid in all_members:
        session.add(ChatRoomMember(room_id=room.id, user_id=uid))
    await session.commit()
    await session.refresh(room)

    from app.services.notification_service import create_notification

    for uid in member_ids:
        if uid == user.id:
            continue
        await create_notification(
            session,
            uid,
            "群聊邀请",
            f"{user.display_name} 邀请你加入「{title}」",
            kind="chat",
            link=f"chat:{room.id}",
        )
    return room


async def invite_to_group(session: AsyncSession, user: User, room_id: str, target_user_id: str) -> bool:
    room = (await session.execute(select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.room_type == "group"))).scalar_one_or_none()
    if room is None or room.created_by != user.id:
        return False
    target = (await session.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if target is None:
        return False
    member = (
        await session.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == target_user_id)
        )
    ).scalar_one_or_none()
    if member is None:
        session.add(ChatRoomMember(room_id=room_id, user_id=target_user_id))
        await session.commit()
        from app.services.notification_service import create_notification

        await create_notification(
            session,
            target_user_id,
            "群聊邀请",
            f"{user.display_name} 邀请你加入「{room.title}」",
            kind="chat",
            link=f"chat:{room_id}",
        )
    return True


async def list_user_rooms(session: AsyncSession, user_id: str) -> list[dict]:
    memberships = (
        await session.execute(select(ChatRoomMember).where(ChatRoomMember.user_id == user_id))
    ).scalars().all()
    room_ids = [m.room_id for m in memberships]
    if not room_ids:
        return []

    rooms = (await session.execute(select(ChatRoom).where(ChatRoom.id.in_(room_ids)))).scalars().all()
    out = []
    for room in rooms:
        last_msg = (
            await session.execute(
                select(ChatRoomMessage)
                .where(ChatRoomMessage.room_id == room.id)
                .order_by(ChatRoomMessage.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        out.append(
            {
                "id": room.id,
                "room_type": room.room_type,
                "title": room.title,
                "class_id": room.class_id,
                "created_by": room.created_by,
                "last_message": last_msg.content if last_msg else "",
            }
        )
    return out


async def delete_topic_room(session: AsyncSession, user: User, room_id: str) -> str:
    """Delete a topic room. Returns 'ok' | 'not_found' | 'forbidden'."""
    room = (
        await session.execute(select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.room_type == "topic"))
    ).scalar_one_or_none()
    if room is None:
        return "not_found"
    if room.created_by != user.id:
        return "forbidden"

    message_ids = (
        await session.execute(select(ChatRoomMessage.id).where(ChatRoomMessage.room_id == room_id))
    ).scalars().all()
    if message_ids:
        await session.execute(delete(ChatMessageReaction).where(ChatMessageReaction.message_id.in_(message_ids)))
    await session.execute(delete(ChatRoomMessage).where(ChatRoomMessage.room_id == room_id))
    await session.execute(delete(ChatRoomMember).where(ChatRoomMember.room_id == room_id))
    await session.execute(delete(ChatRoom).where(ChatRoom.id == room_id))
    await session.commit()
    return "ok"


async def _message_reactions(session: AsyncSession, message_id: str, user_id: str) -> list[dict]:
    rows = (
        await session.execute(select(ChatMessageReaction).where(ChatMessageReaction.message_id == message_id))
    ).scalars().all()
    grouped: dict[str, dict] = {}
    for row in rows:
        if row.emoji not in grouped:
            grouped[row.emoji] = {"emoji": row.emoji, "count": 0, "reacted_by_me": False}
        grouped[row.emoji]["count"] += 1
        if row.user_id == user_id:
            grouped[row.emoji]["reacted_by_me"] = True
    return list(grouped.values())


async def list_room_messages(session: AsyncSession, room_id: str, user_id: str, limit: int = 80) -> list[dict]:
    member = (
        await session.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id)
        )
    ).scalar_one_or_none()
    if member is None:
        return []

    rows = (
        await session.execute(
            select(ChatRoomMessage)
            .where(ChatRoomMessage.room_id == room_id)
            .order_by(ChatRoomMessage.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    rows = list(reversed(rows))

    user_cache: dict[str, User] = {}
    out = []
    for row in rows:
        if row.sender_id not in user_cache:
            user_cache[row.sender_id] = (
                await session.execute(select(User).where(User.id == row.sender_id))
            ).scalar_one_or_none()
        sender = user_cache[row.sender_id]
        created = row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat()
        out.append(
            {
                "id": row.id,
                "room_id": row.room_id,
                "sender_id": row.sender_id,
                "sender_name": sender.display_name if sender else "未知",
                "sender_avatar": user_avatar_url(sender),
                "content": row.content,
                "created_at": created,
                "reactions": await _message_reactions(session, row.id, user_id),
            }
        )
    return out


async def send_room_message(session: AsyncSession, room_id: str, sender_id: str, content: str) -> dict | None:
    member = (
        await session.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == sender_id)
        )
    ).scalar_one_or_none()
    if member is None:
        return None

    sender = (await session.execute(select(User).where(User.id == sender_id))).scalar_one_or_none()
    msg = ChatRoomMessage(id=str(__import__("uuid").uuid4()), room_id=room_id, sender_id=sender_id, content=content.strip())
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    payload = {
        "type": "message",
        "message": {
            "id": msg.id,
            "room_id": msg.room_id,
            "sender_id": msg.sender_id,
            "sender_name": sender.display_name if sender else "未知",
            "sender_avatar": user_avatar_url(sender),
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else datetime.now(timezone.utc).isoformat(),
            "reactions": [],
        },
    }
    await broadcast_room(room_id, payload)

    from app.services.notification_service import create_notification

    members = (
        await session.execute(select(ChatRoomMember).where(ChatRoomMember.room_id == room_id))
    ).scalars().all()
    room = (await session.execute(select(ChatRoom).where(ChatRoom.id == room_id))).scalar_one_or_none()
    for member in members:
        if member.user_id == sender_id:
            continue
        await create_notification(
            session,
            member.user_id,
            room.title if room else "新消息",
            f"{sender.display_name if sender else '同学'}：{content[:60]}",
            kind="chat",
            link=f"chat:{room_id}",
        )
    return payload["message"]


async def toggle_message_reaction(session: AsyncSession, user_id: str, message_id: str, emoji: str) -> list[dict]:
    existing = (
        await session.execute(
            select(ChatMessageReaction).where(
                ChatMessageReaction.message_id == message_id,
                ChatMessageReaction.user_id == user_id,
                ChatMessageReaction.emoji == emoji,
            )
        )
    ).scalar_one_or_none()
    if existing:
        await session.delete(existing)
    else:
        session.add(ChatMessageReaction(message_id=message_id, user_id=user_id, emoji=emoji))
    await session.commit()
    return await _message_reactions(session, message_id, user_id)


async def summarize_room_today(session: AsyncSession, room_id: str, user_id: str) -> dict:
    member = (
        await session.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user_id)
        )
    ).scalar_one_or_none()
    if member is None:
        return {"summary": "无权访问该房间", "message_count": 0}

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await session.execute(
            select(ChatRoomMessage)
            .where(ChatRoomMessage.room_id == room_id, ChatRoomMessage.created_at >= today_start)
            .order_by(ChatRoomMessage.created_at.asc())
            .limit(60)
        )
    ).scalars().all()
    if not rows:
        return {"summary": "今日暂无消息，星轨信号静默中。", "message_count": 0}

    lines = [f"{r.content[:80]}" for r in rows[-20:]]
    text_block = "\n".join(lines)
    summary = f"今日共 {len(rows)} 条消息。热点：{lines[-1][:40]}…" if len(lines) == 1 else f"今日共 {len(rows)} 条消息，讨论围绕学习打卡与互助展开。"

    from app.services.llm import llm_available, llm_chat

    if llm_available():
        try:
            ai = await llm_chat(
                [
                    {"role": "system", "content": "你是班级群聊速览助手，用一句中文（不超过60字）概括今日聊天要点。"},
                    {"role": "user", "content": text_block},
                ],
                temperature=0.4,
            )
            if ai and ai.strip():
                summary = ai.strip()
        except Exception:
            logger.exception("chat summary llm failed")

    return {"summary": summary, "message_count": len(rows)}


async def create_private_room(session: AsyncSession, user_id: str, target_user_id: str) -> ChatRoom | None:
    if user_id == target_user_id:
        return None
    target = (await session.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if target is None:
        return None

    my_memberships = (
        await session.execute(select(ChatRoomMember).where(ChatRoomMember.user_id == user_id))
    ).scalars().all()
    for m in my_memberships:
        room = (await session.execute(select(ChatRoom).where(ChatRoom.id == m.room_id, ChatRoom.room_type == "private"))).scalar_one_or_none()
        if room is None:
            continue
        members = (
            await session.execute(select(ChatRoomMember).where(ChatRoomMember.room_id == room.id))
        ).scalars().all()
        member_ids = {x.user_id for x in members}
        if member_ids == {user_id, target_user_id}:
            return room

    me = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    title = f"{me.display_name if me else '我'} ↔ {target.display_name}"
    room = ChatRoom(room_type="private", title=title, created_by=user_id)
    session.add(room)
    await session.flush()
    session.add(ChatRoomMember(room_id=room.id, user_id=user_id))
    session.add(ChatRoomMember(room_id=room.id, user_id=target_user_id))
    await session.commit()
    await session.refresh(room)
    return room


async def list_classmates(session: AsyncSession, user: User) -> list[User]:
    if not user.class_id:
        return []
    result = await session.execute(
        select(User).where(User.class_id == user.class_id, User.id != user.id, User.role == "student")
    )
    return list(result.scalars().all())
