"""模拟面试 WebSocket：一题一条讯飞 IAT 连接 + wpgs 全量字幕 + 麦克风门控。"""
from __future__ import annotations

import asyncio
import base64
import json
import logging

import websockets
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.mock_interview import InterviewSession
from app.models.user import User
from app.core.security import resolve_user_id_from_token
from app.services.asr_service import (
    build_iat_audio_frame,
    build_iat_end_frame,
    build_iat_first_frame,
    build_iat_ws_url,
    extract_iat_segment,
    iat_header_code,
    iat_header_message,
    iat_is_final,
)
from app.services.interview_agents import build_interview_report, score_interview_turn
from app.services.interview_catalog import kind_labels
from app.services.interview_runtime import (
    FRAME_BUDGET_PER_TURN,
    INTERVIEW_EOS_MS,
    InterviewLive,
    get_live,
    register_live,
    unregister_live,
)
from app.services.interview_service import apply_followup_to_session, persist_turn, serialize_turn
from app.services.interview_transcript import TranscriptAssembler

logger = logging.getLogger(__name__)


async def _send(ws: WebSocket, payload: dict) -> None:
    await ws.send_json(payload)


def _question_at(session: InterviewSession, index: int) -> dict | None:
    questions = list(session.questions or [])
    if 0 <= index < len(questions):
        item = dict(questions[index])
        labels = kind_labels(session.scenario)
        item["kind_label"] = labels.get(str(item.get("kind") or ""), "")
        return item
    return None


async def _push_question(ws: WebSocket, session: InterviewSession, index: int) -> None:
    item = _question_at(session, index)
    if item is None:
        await _send(ws, {"type": "error", "detail": "题目已用尽"})
        return
    await _send(
        ws,
        {
            "type": "question",
            "index": index,
            "total": len(session.questions or []),
            "kind": item.get("kind"),
            "kind_label": item.get("kind_label"),
            "text": item.get("question"),
        },
    )
    await _send(ws, {"type": "mic_gate", "state": "closed"})


async def _open_iat(live: InterviewLive) -> None:
    url = build_iat_ws_url()
    xf = await websockets.connect(url, max_size=None)
    await xf.send(json.dumps(build_iat_first_frame("zh_cn", eos=INTERVIEW_EOS_MS)))
    live.xf = xf
    live.seq = 1
    live.assembler = TranscriptAssembler()

    async def _forward_xf() -> None:
        try:
            while True:
                raw = await xf.recv()
                payload = json.loads(raw)
                code = iat_header_code(payload)
                if code != 0:
                    await _send(
                        live.websocket,
                        {"type": "error", "detail": iat_header_message(payload) or f"讯飞识别失败({code})"},
                    )
                    break
                sn, words, pgs, rg = extract_iat_segment(payload)
                if words or pgs == "rpl" or sn:
                    text = live.assembler.push(sn, words, pgs, rg)
                    await _send(live.websocket, {"type": "caption", "text": text})
                if iat_is_final(payload):
                    await _send(live.websocket, {"type": "caption", "text": live.assembler.text, "final": True})
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("interview iat recv: %s", exc)
        finally:
            try:
                await xf.close()
            except Exception:
                pass
            if live.xf is xf:
                live.xf = None

    live.xf_task = asyncio.create_task(_forward_xf())


async def _close_iat(live: InterviewLive) -> None:
    xf = live.xf
    if xf is None:
        return
    try:
        await xf.send(json.dumps(build_iat_end_frame(seq=live.seq)))
    except Exception:
        pass
    task = live.xf_task
    if task:
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=8)
        except Exception:
            task.cancel()
    live.xf = None
    live.xf_task = None


async def _finish_answer(live: InterviewLive) -> None:
    await _close_iat(live)
    transcript = live.assembler.text.strip()
    pcm = live.pcm_bytes()
    frames = list(live.frames)
    answered_index = live.turn_index
    async with AsyncSessionLocal() as db:
        session = await db.get(InterviewSession, live.session_id)
        user = await db.get(User, live.user_id)
        if session is None:
            await _send(live.websocket, {"type": "error", "detail": "会话不存在"})
            return
        q = _question_at(session, answered_index) or {"question": "", "kind": ""}
        await _send(live.websocket, {"type": "turn_progress", "stage": "scoring", "content": "正在并行评分（语义 + 仪态）…"})
        await _send(live.websocket, {"type": "agent_step", "role": "MultimodalScorer", "content": "正在评分…"})
        result = await score_interview_turn(
            db,
            session,
            question=str(q.get("question") or ""),
            transcript=transcript,
            pcm_bytes=pcm,
            frames=frames,
            user=user,
            followup_enabled=True,
        )
        result["frames"] = frames
        await _send(live.websocket, {"type": "turn_progress", "stage": "saving", "content": "正在保存本轮评分…"})
        turn = await persist_turn(
            db,
            session,
            question=str(q.get("question") or ""),
            question_kind=str(q.get("kind") or ""),
            transcript=transcript,
            result=result,
            followup_of=str(q.get("followup_of") or ""),
        )
        await _send(
            live.websocket,
            {
                "type": "turn_score",
                "turn": serialize_turn(turn),
                "degraded": result.get("degraded") or [],
                "prosody": result.get("prosody") or {},
            },
        )
        inserted = await apply_followup_to_session(
            db,
            session,
            answered_index=answered_index,
            strategy=str(result.get("followup_strategy") or "next"),
            followup_question=str(result.get("followup_question") or ""),
            followup_of=turn.id,
        )
        if inserted:
            await _send(
                live.websocket,
                {
                    "type": "followup",
                    "strategy": result.get("followup_strategy"),
                    "question": result.get("followup_question"),
                },
            )
        next_index = session.current_turn
        if next_index >= len(session.questions or []):
            total = len(session.questions or [])
            await _send(live.websocket, {"type": "session_end", "total": total})
            await _send(live.websocket, {"type": "agent_step", "role": "CouncilSummarizer", "content": "正在生成三视角报告…"})
            report = await build_interview_report(db, session, user)
            await db.refresh(session)
            await _send(
                live.websocket,
                {
                    "type": "report_ready",
                    "report_id": report.id,
                    "session_id": session.id,
                    "overall_score": session.overall_score,
                },
            )
            live.reset_answer()
            return
        live.turn_index = next_index
        live.reset_answer()
        await db.refresh(session)
        await _push_question(live.websocket, session, next_index)


async def interview_ws_handler(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    live: InterviewLive | None = None
    user_id = ""
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = data.get("type")
            if msg_type == "heartbeat":
                await _send(websocket, {"type": "pong"})
                continue

            token = str(data.get("token") or "")
            uid = resolve_user_id_from_token(token)
            if not uid:
                await _send(websocket, {"type": "error", "detail": "未登录"})
                continue
            user_id = uid

            if msg_type == "start":
                async with AsyncSessionLocal() as db:
                    session = await db.get(InterviewSession, session_id)
                    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                    if session is None or user is None or session.user_id != user_id:
                        await _send(websocket, {"type": "error", "detail": "无权进入该面试"})
                        continue
                    if session.status not in {"ready", "running"}:
                        await _send(websocket, {"type": "error", "detail": f"面试尚未就绪（{session.status}）"})
                        continue
                    session.status = "running"
                    await db.commit()
                    live = InterviewLive(
                        session_id=session_id,
                        user_id=user_id,
                        websocket=websocket,
                        turn_index=int(session.current_turn or 0),
                    )
                    register_live(live)
                    await _push_question(websocket, session, live.turn_index)
                continue

            if live is None:
                live = get_live(session_id)
            if live is None or live.user_id != user_id:
                await _send(websocket, {"type": "error", "detail": "请先发送 start"})
                continue

            if msg_type == "speak_done":
                try:
                    await _open_iat(live)
                    live.mic_open = True
                    live.answering = True
                    await _send(websocket, {"type": "mic_gate", "state": "open"})
                except Exception as exc:  # noqa: BLE001
                    logger.warning("open iat: %s", exc)
                    await _send(websocket, {"type": "error", "detail": f"语音识别不可用：{exc}"})
                    # 仍允许纯文本兜底
                    live.mic_open = True
                    live.answering = True
                    await _send(websocket, {"type": "mic_gate", "state": "open"})

            elif msg_type == "audio" and live.mic_open:
                audio_b64 = str(data.get("audio") or "")
                if audio_b64:
                    try:
                        live.pcm_chunks.append(base64.b64decode(audio_b64))
                    except Exception:
                        pass
                if live.xf is not None:
                    try:
                        await live.xf.send(json.dumps(build_iat_audio_frame(audio_b64, status=1, seq=live.seq)))
                        live.seq += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("forward iat audio: %s", exc)

            elif msg_type == "frame" and live.mic_open:
                image = str(data.get("data") or data.get("image") or "")
                if image.startswith("data:image") and len(live.frames) < FRAME_BUDGET_PER_TURN:
                    live.frames.append(image)

            elif msg_type == "caption_override":
                text = str(data.get("text") or "").strip()
                if text:
                    live.assembler.reset()
                    live.assembler.push_text(text)

            elif msg_type == "answer_end":
                live.mic_open = False
                await _send(websocket, {"type": "mic_gate", "state": "closed"})
                await _finish_answer(live)

            elif msg_type == "next":
                async with AsyncSessionLocal() as db:
                    session = await db.get(InterviewSession, session_id)
                    if session:
                        live.turn_index = int(session.current_turn or 0)
                        live.reset_answer()
                        await _push_question(websocket, session, live.turn_index)

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("interview ws: %s", exc)
        try:
            await _send(websocket, {"type": "error", "detail": str(exc)})
        except Exception:
            pass
    finally:
        if live:
            await _close_iat(live)
        unregister_live(session_id)
