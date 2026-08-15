import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study_room import StudyRoom
from app.models.user import User

logger = logging.getLogger(__name__)

ZODIAC = [
    {"slug": "aries", "name": "白羊座", "symbol": "♈"},
    {"slug": "taurus", "name": "金牛座", "symbol": "♉"},
    {"slug": "gemini", "name": "双子座", "symbol": "♊"},
    {"slug": "cancer", "name": "巨蟹座", "symbol": "♋"},
    {"slug": "leo", "name": "狮子座", "symbol": "♌"},
    {"slug": "virgo", "name": "处女座", "symbol": "♍"},
    {"slug": "libra", "name": "天秤座", "symbol": "♎"},
    {"slug": "scorpio", "name": "天蝎座", "symbol": "♏"},
    {"slug": "sagittarius", "name": "射手座", "symbol": "♐"},
    {"slug": "capricorn", "name": "摩羯座", "symbol": "♑"},
    {"slug": "aquarius", "name": "水瓶座", "symbol": "♒"},
    {"slug": "pisces", "name": "双鱼座", "symbol": "♓"},
]

ROOM_TEMPLATES = [
    ("主星·大自习室", "large", 20),
    ("辅星·大自习室", "large", 20),
    ("亮星·小自习室", "small", 6),
    ("暗星·小自习室", "small", 6),
    ("伴星·小自习室", "small", 6),
]

# room_id -> user_id -> occupant dict
_presence: dict[str, dict[str, dict[str, Any]]] = {}
_study_ws: dict[str, set] = {}
_user_room: dict[str, str] = {}
_heartbeat_tasks: dict[str, asyncio.Task] = {}


def register_study_ws(room_id: str, websocket) -> None:
    _study_ws.setdefault(room_id, set()).add(websocket)


def unregister_study_ws(room_id: str, websocket) -> None:
    conns = _study_ws.get(room_id)
    if not conns:
        return
    conns.discard(websocket)
    if not conns:
        _study_ws.pop(room_id, None)


async def broadcast_study_room(room_id: str, payload: dict) -> None:
    dead = []
    for ws in list(_study_ws.get(room_id, set())):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister_study_ws(room_id, ws)


def _occupancy(room_id: str) -> int:
    return len(_presence.get(room_id, {}))


def _room_out(room: StudyRoom) -> dict:
    occ = _occupancy(room.id)
    return {
        "id": room.id,
        "constellation": room.constellation,
        "name": room.name,
        "size": room.size,
        "capacity": room.capacity,
        "occupancy": occ,
        "is_full": occ >= room.capacity,
    }


def _occupants(room_id: str) -> list[dict]:
    return list(_presence.get(room_id, {}).values())


async def seed_study_rooms(session: AsyncSession) -> None:
    existing = (await session.execute(select(StudyRoom))).scalars().first()
    if existing is not None:
        return

    for zodiac in ZODIAC:
        for name, size, capacity in ROOM_TEMPLATES:
            session.add(
                StudyRoom(
                    constellation=zodiac["slug"],
                    name=f"{zodiac['name']}{name}",
                    size=size,
                    capacity=capacity,
                )
            )
    await session.commit()


async def list_constellations(session: AsyncSession) -> list[dict]:
    rows = (
        await session.execute(
            select(StudyRoom.constellation, func.count(StudyRoom.id)).group_by(StudyRoom.constellation)
        )
    ).all()
    counts = {slug: count for slug, count in rows}
    out = []
    for z in ZODIAC:
        rooms = (
            await session.execute(select(StudyRoom).where(StudyRoom.constellation == z["slug"]))
        ).scalars().all()
        total_occ = sum(_occupancy(r.id) for r in rooms)
        out.append(
            {
                "slug": z["slug"],
                "name": z["name"],
                "symbol": z["symbol"],
                "room_count": counts.get(z["slug"], len(rooms)),
                "total_occupancy": total_occ,
            }
        )
    return out


async def list_rooms(session: AsyncSession, constellation: str) -> list[dict]:
    rooms = (
        await session.execute(
            select(StudyRoom).where(StudyRoom.constellation == constellation).order_by(StudyRoom.size.desc(), StudyRoom.name)
        )
    ).scalars().all()
    return [_room_out(r) for r in rooms]


async def get_room(session: AsyncSession, room_id: str) -> StudyRoom | None:
    return (await session.execute(select(StudyRoom).where(StudyRoom.id == room_id))).scalar_one_or_none()


async def join_room(session: AsyncSession, user: User, room_id: str) -> tuple[dict, list[dict]]:
    room = await get_room(session, room_id)
    if room is None:
        raise ValueError("自习室不存在")

    prev = _user_room.get(user.id)
    if prev and prev != room_id:
        await leave_room(user.id)

    occ = _occupancy(room_id)
    if user.id not in _presence.get(room_id, {}) and occ >= room.capacity:
        raise ValueError("自习室已满")

    _presence.setdefault(room_id, {})[user.id] = {
        "user_id": user.id,
        "display_name": user.display_name or user.username,
        "avatar": user.avatar_cartoon_url or user.avatar or "",
        "joined_at": datetime.now(timezone.utc).isoformat(),
        "focus_minutes": 0,
        "status": "focus",
    }
    _user_room[user.id] = room_id

    payload = {"type": "presence", "occupants": _occupants(room_id), "room_id": room_id}
    await broadcast_study_room(room_id, payload)
    return _room_out(room), _occupants(room_id)


async def leave_room(user_id: str) -> str | None:
    room_id = _user_room.pop(user_id, None)
    if not room_id:
        return None
    room_presence = _presence.get(room_id)
    if room_presence and user_id in room_presence:
        del room_presence[user_id]
        if not room_presence:
            _presence.pop(room_id, None)
        await broadcast_study_room(room_id, {"type": "presence", "occupants": _occupants(room_id), "room_id": room_id})
    return room_id


def list_occupants(room_id: str) -> list[dict]:
    return _occupants(room_id)


def get_user_study_room(user_id: str) -> str | None:
    return _user_room.get(user_id)


async def update_occupant_status(user_id: str, status: str) -> str | None:
    room_id = _user_room.get(user_id)
    if not room_id:
        return None
    occupant = _presence.get(room_id, {}).get(user_id)
    if occupant is None:
        return None
    if status not in {"focus", "break", "help"}:
        status = "focus"
    occupant["status"] = status
    await broadcast_study_room(
        room_id,
        {"type": "presence", "occupants": _occupants(room_id), "room_id": room_id},
    )
    return room_id


async def list_teacher_study_presence(session: AsyncSession, teacher_id: str) -> list[dict]:
    from app.models.school_class import SchoolClass

    classes = (await session.execute(select(SchoolClass).where(SchoolClass.teacher_id == teacher_id))).scalars().all()
    class_ids = [c.id for c in classes]
    if not class_ids:
        return []
    users = (await session.execute(select(User).where(User.class_id.in_(class_ids)))).scalars().all()
    out = []
    for user in users:
        room_id = _user_room.get(user.id)
        if not room_id:
            continue
        room = await get_room(session, room_id)
        if room is None:
            continue
        out.append(
            {
                "user_id": user.id,
                "display_name": user.display_name or user.username,
                "room_id": room_id,
                "room_name": room.name,
                "constellation": room.constellation,
                "status": (_presence.get(room_id, {}).get(user.id) or {}).get("status", "focus"),
            }
        )
    return out


# ---------------- 集体番茄钟（内存态，随房间广播同步） ----------------

_room_pomodoro: dict[str, dict[str, Any]] = {}


def get_room_pomodoro(room_id: str) -> dict[str, Any] | None:
    """获取房间进行中的番茄钟；已结束则清理并返回 None。"""
    state = _room_pomodoro.get(room_id)
    if not state:
        return None
    if datetime.now(timezone.utc).timestamp() >= float(state.get("ends_at_ts") or 0):
        _room_pomodoro.pop(room_id, None)
        return None
    return state


async def start_room_pomodoro(user: User, minutes: int = 25) -> dict[str, Any]:
    room_id = _user_room.get(user.id)
    if not room_id:
        raise ValueError("请先加入自习室")
    if get_room_pomodoro(room_id) is not None:
        raise ValueError("本轮集体番茄钟正在进行中")
    minutes = max(5, min(int(minutes or 25), 120))
    now = datetime.now(timezone.utc)
    state = {
        "room_id": room_id,
        "minutes": minutes,
        "started_by": user.id,
        "started_by_name": user.display_name or user.username,
        "started_at": now.isoformat(),
        "ends_at_ts": now.timestamp() + minutes * 60,
    }
    _room_pomodoro[room_id] = state
    await broadcast_study_room(room_id, {"type": "pomodoro", "action": "start", **state})
    return state


async def stop_room_pomodoro(user: User) -> dict[str, Any]:
    room_id = _user_room.get(user.id)
    if not room_id:
        raise ValueError("请先加入自习室")
    state = get_room_pomodoro(room_id)
    if state is None:
        raise ValueError("当前没有进行中的集体番茄钟")
    if state.get("started_by") != user.id:
        raise ValueError("只有发起人可以提前结束")
    _room_pomodoro.pop(room_id, None)
    await broadcast_study_room(room_id, {"type": "pomodoro", "action": "stop", "room_id": room_id})
    return {"ok": True}


_supervision_meta: dict[str, dict] = {}


async def save_supervision_frame(user: User, data: bytes) -> dict:
    from app.core.paths import SUPERVISION_DIR, ensure_storage_dirs

    ensure_storage_dirs()
    path = SUPERVISION_DIR / f"{user.id}.jpg"
    path.write_bytes(data)
    room_id = _user_room.get(user.id) or ""
    status = "offline"
    if room_id and user.id in _presence.get(room_id, {}):
        status = (_presence[room_id][user.id] or {}).get("status", "focus")
    meta = {
        "user_id": user.id,
        "display_name": user.display_name or user.username,
        "frame_url": f"/static/uploads/supervision/{user.id}.jpg",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "room_id": room_id,
        "status": status,
        "online": bool(room_id),
    }
    _supervision_meta[user.id] = meta
    return meta


def clear_supervision_frame(user_id: str) -> None:
    meta = _supervision_meta.get(user_id)
    if meta:
        meta["online"] = False
        meta["status"] = "offline"


async def list_supervision_patrol(
    session: AsyncSession, teacher: User, class_id: str = ""
) -> list[dict]:
    """教师巡查：班级学生在自习室态势 + 最近监督截图。"""
    from app.core.paths import SUPERVISION_DIR
    from app.models.school_class import SchoolClass

    if teacher.role == "admin":
        class_rows = list((await session.execute(select(SchoolClass))).scalars().all())
    else:
        class_rows = list(
            (
                await session.execute(select(SchoolClass).where(SchoolClass.teacher_id == teacher.id))
            ).scalars().all()
        )
    if class_id:
        class_rows = [c for c in class_rows if c.id == class_id]
    class_ids = [c.id for c in class_rows]
    class_name_map = {c.id: c.name for c in class_rows}
    if not class_ids:
        return []
    students = (
        await session.execute(select(User).where(User.role == "student", User.class_id.in_(class_ids)))
    ).scalars().all()
    out = []
    for s in students:
        room_id = _user_room.get(s.id)
        room_name = ""
        constellation = ""
        status = "offline"
        if room_id:
            room = await get_room(session, room_id)
            if room:
                room_name = room.name
                constellation = room.constellation
            status = (_presence.get(room_id, {}).get(s.id) or {}).get("status", "focus")
        meta = _supervision_meta.get(s.id) or {}
        frame_url = meta.get("frame_url") or ""
        updated_at = meta.get("updated_at") or ""
        # 进程重启后内存元数据会丢，若磁盘仍有截图则回填 URL
        if not frame_url:
            disk_path = SUPERVISION_DIR / f"{s.id}.jpg"
            if disk_path.is_file():
                frame_url = f"/static/uploads/supervision/{s.id}.jpg"
                updated_at = datetime.fromtimestamp(disk_path.stat().st_mtime, tz=timezone.utc).isoformat()
        out.append(
            {
                "user_id": s.id,
                "display_name": s.display_name or s.username,
                "class_id": s.class_id or "",
                "class_name": class_name_map.get(s.class_id or "", ""),
                "room_id": room_id or "",
                "room_name": room_name,
                "constellation": constellation,
                "status": status if room_id else "offline",
                "frame_url": frame_url,
                "updated_at": updated_at,
                "online": bool(room_id),
            }
        )
    out.sort(key=lambda x: (not x["online"], x["display_name"]))
    return out


async def create_supervision_alert(
    session: AsyncSession,
    student: User,
    kind: str,
    message: str,
    room_id: str = "",
) -> dict:
    """学生端 AI 监督事件上报：写入教师 Alert。"""
    from app.models.alert import Alert
    from app.models.school_class import SchoolClass

    if kind not in {"phone", "away"}:
        raise ValueError("kind 须为 phone 或 away")
    text = (message or "").strip() or (
        "检测到学生使用手机" if kind == "phone" else "检测到学生离开摄像头视野"
    )
    teacher_id = (student.teacher_id or "").strip()
    if not teacher_id and student.class_id:
        cls = (
            await session.execute(select(SchoolClass).where(SchoolClass.id == student.class_id))
        ).scalar_one_or_none()
        if cls and cls.teacher_id:
            teacher_id = cls.teacher_id
    if not teacher_id:
        # 仍写入一条挂在学生自己名下的记录，便于排查；教师列表可按 student_id 查
        teacher_id = student.id

    room_hint = f"（自习室 {room_id}）" if room_id else ""
    alert = Alert(
        user_id=teacher_id,
        student_id=student.id,
        alert_type=f"supervision_{kind}",
        alert_level="high" if kind == "phone" else "warning",
        message=f"{student.display_name or student.username}：{text}{room_hint}",
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return {"ok": True, "alert_id": alert.id, "alert_type": alert.alert_type}
