import asyncio
import json

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.security import resolve_user_id_from_token
from app.services.asr_service import (
    build_iat_end_frame,
    build_iat_first_frame,
    build_iat_audio_frame,
    build_iat_ws_url,
    extract_iat_text,
    iat_header_code,
    iat_header_message,
    iat_is_final,
)
from app.services.chat_service import register_ws, send_room_message, unregister_ws
from app.services.study_service import (
    broadcast_study_room,
    join_room as study_join_room,
    leave_room as study_leave_room,
    list_occupants,
    register_study_ws,
    unregister_study_ws,
    update_occupant_status,
)
from app.services.interview_ws import interview_ws_handler

ws_router = APIRouter()


@ws_router.websocket("/ws/asr")
async def asr_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        requested_language = websocket.query_params.get("lang", "zh_cn")
        requested_accent = websocket.query_params.get("accent", "mandarin")
        language = requested_language if requested_language in {"zh_cn", "en_us"} else "zh_cn"
        accent = requested_accent if requested_accent in {"mandarin", "cantonese"} else "mandarin"
        url = build_iat_ws_url()
        async with websockets.connect(url, max_size=None) as xf:
            await xf.send(json.dumps(build_iat_first_frame(language, accent)))
            seq = 1

            async def forward_client() -> None:
                nonlocal seq
                while True:
                    raw = await websocket.receive_text()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    msg_type = data.get("type")
                    if msg_type == "audio":
                        status = int(data.get("status", 1))
                        audio = str(data.get("audio", ""))
                        await xf.send(json.dumps(build_iat_audio_frame(audio, status=status, seq=seq)))
                        seq += 1
                    elif msg_type == "end":
                        await xf.send(json.dumps(build_iat_end_frame(seq=seq)))
                        break

            async def forward_xf() -> None:
                transcript = ""
                while True:
                    raw = await xf.recv()
                    payload = json.loads(raw)
                    code = iat_header_code(payload)
                    if code != 0:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "detail": iat_header_message(payload) or f"讯飞识别失败({code})",
                            }
                        )
                        break
                    text = extract_iat_text(payload)
                    if text:
                        transcript += text
                        await websocket.send_json({"type": "partial", "text": text})
                    if iat_is_final(payload):
                        await websocket.send_json({"type": "final", "text": transcript})
                        break

            await asyncio.gather(forward_client(), forward_xf())
    except RuntimeError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "detail": f"语音识别不可用：{exc}"})
        except Exception:
            pass


@ws_router.websocket("/ws/chat/{room_id}")
async def chat_ws(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    register_ws(room_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "send":
                continue
            token = str(data.get("token", ""))
            content = str(data.get("content", "")).strip()
            user_id = resolve_user_id_from_token(token)
            if not user_id or not content:
                continue
            async with AsyncSessionLocal() as session:
                msg = await send_room_message(session, room_id, user_id, content)
                if msg is None:
                    await websocket.send_json({"type": "error", "detail": "无权发送消息"})
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws(room_id, websocket)


@ws_router.websocket("/ws/study/{room_id}")
async def study_ws(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    register_study_ws(room_id, websocket)
    user_id: str | None = None
    try:
        await websocket.send_json({"type": "presence", "occupants": list_occupants(room_id), "room_id": room_id})
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            token = str(data.get("token", ""))
            if msg_type == "heartbeat":
                await websocket.send_json({"type": "pong"})
                continue

            user_id = resolve_user_id_from_token(token)
            if not user_id:
                continue

            async with AsyncSessionLocal() as session:
                user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                if user is None:
                    await websocket.send_json({"type": "error", "detail": "用户不存在"})
                    continue

                if msg_type == "join":
                    try:
                        room, occupants = await study_join_room(session, user, room_id)
                        await websocket.send_json({"type": "joined", "room": room, "occupants": occupants})
                    except ValueError as exc:
                        await websocket.send_json({"type": "error", "detail": str(exc)})
                elif msg_type == "leave":
                    await study_leave_room(user_id)
                    await broadcast_study_room(
                        room_id,
                        {"type": "presence", "occupants": list_occupants(room_id), "room_id": room_id},
                    )
                elif msg_type == "status":
                    status = str(data.get("status", "focus"))
                    await update_occupant_status(user_id, status)
    except WebSocketDisconnect:
        pass
    finally:
        unregister_study_ws(room_id, websocket)
        if user_id:
            await study_leave_room(user_id)


@ws_router.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str) -> None:
    await interview_ws_handler(websocket, session_id)
