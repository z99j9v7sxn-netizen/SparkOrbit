"""模拟面试运行态：准备阶段 SSE 队列 + 面试中 WebSocket 会话（单进程内存）。

断线后以 DB 的 InterviewTurn / current_turn 为准恢复，不依赖本表。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.services.interview_transcript import TranscriptAssembler

INTERVIEW_EOS_MS = 9000
FRAME_BUDGET_PER_TURN = 4

_PREP: dict[str, dict[str, Any]] = {}
_LIVE: dict[str, "InterviewLive"] = {}


def register_prep(session_id: str, user_id: str) -> None:
    _PREP[session_id] = {
        "user_id": user_id,
        "status": "running",
        "queue": asyncio.Queue(),
    }


async def emit_prep(session_id: str, event: dict[str, Any]) -> None:
    rec = _PREP.get(session_id)
    if rec is None:
        return
    await rec["queue"].put(event)


def finish_prep(session_id: str, status: str) -> None:
    rec = _PREP.get(session_id)
    if rec is not None:
        rec["status"] = status


def get_prep(session_id: str) -> dict[str, Any] | None:
    return _PREP.get(session_id)


async def iter_prep_events(session_id: str):
    rec = _PREP.get(session_id)
    if rec is None:
        yield {"role": "System", "type": "error", "content": "准备任务不存在或已过期", "payload": {}}
        return
    queue: asyncio.Queue = rec["queue"]
    while True:
        event = await queue.get()
        yield event
        if event.get("type") in {"done", "error"}:
            break


@dataclass
class InterviewLive:
    session_id: str
    user_id: str
    websocket: WebSocket
    assembler: TranscriptAssembler = field(default_factory=TranscriptAssembler)
    pcm_chunks: list[bytes] = field(default_factory=list)
    frames: list[str] = field(default_factory=list)
    answering: bool = False
    mic_open: bool = False
    xf: Any = None
    xf_task: asyncio.Task | None = None
    seq: int = 1
    turn_index: int = 0

    def reset_answer(self) -> None:
        self.assembler.reset()
        self.pcm_chunks = []
        self.frames = []
        self.answering = False
        self.mic_open = False
        self.seq = 1
        self.xf = None
        self.xf_task = None

    def pcm_bytes(self) -> bytes:
        return b"".join(self.pcm_chunks)


def register_live(live: InterviewLive) -> None:
    old = _LIVE.get(live.session_id)
    if old and old is not live:
        try:
            if old.xf_task:
                old.xf_task.cancel()
        except Exception:
            pass
    _LIVE[live.session_id] = live


def get_live(session_id: str) -> InterviewLive | None:
    return _LIVE.get(session_id)


def unregister_live(session_id: str) -> None:
    _LIVE.pop(session_id, None)
