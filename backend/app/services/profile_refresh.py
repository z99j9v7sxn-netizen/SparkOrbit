"""画像随学随新：学习行为事件累积与增量画像更新。"""
from __future__ import annotations

import logging
import uuid
from typing import Any, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_resource import ProfileLearningEvent
from app.models.student_profile import PROFILE_DIMENSIONS, StudentProfile
from app.schemas.resource_gen import ProfileTimelineItem
from app.schemas.student_profile import DimensionProfile, StudentProfileExtract
from app.services.llm import extract_json, llm_available, llm_chat
from app.services.profiles import get_latest_profile, save_student_profile

logger = logging.getLogger(__name__)

REFRESH_THRESHOLD = 5

DIM_LAYER = {
    "major_background": "trajectory",
    "cognitive_style": "trajectory",
    "modality_preference": "trajectory",
    "prior_knowledge": "mastery",
    "mistake_tendency": "mastery",
    "learning_goal": "will",
    "time_flexibility": "will",
    "motivation_level": "will",
}


async def record_learning_event(
    session: AsyncSession,
    user_id: str,
    event_type: str,
    summary: str,
    payload: Optional[dict] = None,
    *,
    auto_refresh: bool = True,
) -> dict:
    row = ProfileLearningEvent(
        id=str(uuid.uuid4()),
        user_id=user_id,
        event_type=event_type,
        summary=summary[:500],
        payload_json=payload or {},
        processed=False,
    )
    session.add(row)
    await session.commit()

    pending = await _count_pending(session, user_id)
    refreshed = False
    if auto_refresh and pending >= REFRESH_THRESHOLD:
        result = await refresh_profile_from_events(session, user_id)
        refreshed = result is not None
        pending = await _count_pending(session, user_id)

    return {"ok": True, "pending_events": pending, "profile_refreshed": refreshed}


async def _count_pending(session: AsyncSession, user_id: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(ProfileLearningEvent).where(
                    ProfileLearningEvent.user_id == user_id,
                    ProfileLearningEvent.processed.is_(False),
                )
            )
        ).scalar()
        or 0
    )


def _profile_to_extract(row: StudentProfile) -> StudentProfileExtract:
    payload = {
        "student_name": row.student_name,
        "summary": row.summary,
        "missing_dimensions": row.missing_dimensions or [],
        "follow_up_questions": row.follow_up_questions or [],
    }
    for dim in PROFILE_DIMENSIONS:
        payload[dim] = getattr(row, dim) or {}
    return StudentProfileExtract.model_validate(payload)


def _clamp(score: int) -> int:
    return max(0, min(100, int(score)))


def _push_evidence(dim: DimensionProfile, text: str, limit: int = 8) -> None:
    ev = list(dim.evidence or [])
    if text and text not in ev:
        ev.insert(0, text[:200])
    dim.evidence = ev[:limit]


def _apply_structured_payload(updated: StudentProfileExtract, events: list) -> str:
    """优先消费结构化 payload，返回推断的 update_source。"""
    source = "auto_refresh"
    for e in reversed(events):
        payload = e.payload_json if isinstance(e.payload_json, dict) else {}
        et = e.event_type or ""

        if et == "vault_analyze":
            source = "vault_analyze"
            ai = payload.get("ai") if isinstance(payload.get("ai"), dict) else payload
            weak = list(ai.get("weak_topics") or [])[:6]
            strengths = list(ai.get("strengths") or [])[:4]
            habits = list(ai.get("habits") or [])[:4]
            focus = ai.get("focus_score")
            if weak:
                updated.mistake_tendency.score = _clamp(updated.mistake_tendency.score - min(12, 3 * len(weak)))
                updated.mistake_tendency.value = f"知识库提示薄弱：{'、'.join(weak[:3])}"
                _push_evidence(updated.mistake_tendency, f"知识库AI薄弱点：{'、'.join(weak[:4])}")
                updated.prior_knowledge.score = _clamp(updated.prior_knowledge.score - 4)
                _push_evidence(updated.prior_knowledge, f"待补强主题：{'、'.join(weak[:3])}")
            if strengths:
                updated.prior_knowledge.score = _clamp(updated.prior_knowledge.score + 3)
                _push_evidence(updated.prior_knowledge, f"优势：{'、'.join(strengths[:3])}")
            if habits:
                updated.cognitive_style.value = f"学习习惯：{'、'.join(habits[:2])}"
                _push_evidence(updated.cognitive_style, f"习惯观察：{'、'.join(habits[:3])}")
            if isinstance(focus, (int, float)):
                updated.time_flexibility.score = _clamp(40 + int(focus) * 10)
                _push_evidence(updated.time_flexibility, f"专注度评分 {focus}/5")
            if e.summary:
                updated.summary = e.summary[:400]

        elif et == "challenge_submit":
            source = "challenge"
            correct = bool(payload.get("correct") or payload.get("lit"))
            conf = str(payload.get("self_confidence") or "").strip().lower()
            planet = str(payload.get("planet_slug") or "")
            hint = f"挑战{'正确' if correct else '错误'}" + (f" · {planet}" if planet else "")
            if conf == "hesitant" and not correct:
                updated.mistake_tendency.score = _clamp(updated.mistake_tendency.score - 8)
                _push_evidence(updated.mistake_tendency, f"犹豫且做错：{hint}")
            elif conf == "sure" and correct:
                updated.prior_knowledge.score = _clamp(updated.prior_knowledge.score + 4)
                _push_evidence(updated.prior_knowledge, f"确定且做对：{hint}")
            elif conf == "unknown":
                updated.mistake_tendency.score = _clamp(updated.mistake_tendency.score - 3)
                _push_evidence(updated.mistake_tendency, f"自评不会：{hint}")
            elif correct:
                updated.prior_knowledge.score = _clamp(updated.prior_knowledge.score + 2)
                _push_evidence(updated.prior_knowledge, hint)
            else:
                updated.mistake_tendency.score = _clamp(updated.mistake_tendency.score - 4)
                _push_evidence(updated.mistake_tendency, hint)

        elif et == "path_step_complete":
            source = "path"
            planet = str(payload.get("planet_name") or payload.get("planet_slug") or "")
            action = str(payload.get("action") or e.summary or "完成路径步骤")
            updated.motivation_level.score = _clamp(int(getattr(updated.motivation_level, "score", 50) or 50) + 3)
            updated.motivation_level.value = updated.motivation_level.value or "路径打卡持续投入"
            _push_evidence(updated.motivation_level, f"路径打卡：{planet} · {action}" if planet else action)
            updated.learning_goal.score = _clamp(int(getattr(updated.learning_goal, "score", 50) or 50) + 1)
            _push_evidence(updated.learning_goal, f"推进计划：{action}")

        elif et == "ai_quiz_submit":
            source = "ai_quiz"
            correct = bool(payload.get("correct"))
            q = str(payload.get("question") or "")[:80]
            if correct:
                updated.prior_knowledge.score = _clamp(int(getattr(updated.prior_knowledge, "score", 50) or 50) + 2)
                _push_evidence(updated.prior_knowledge, f"智能测验通过：{q}")
                updated.motivation_level.score = _clamp(int(getattr(updated.motivation_level, "score", 50) or 50) + 2)
            else:
                updated.mistake_tendency.score = _clamp(int(getattr(updated.mistake_tendency, "score", 50) or 50) - 3)
                _push_evidence(updated.mistake_tendency, f"智能测验待补：{q}")

        elif et == "feynman_explain":
            source = "feynman"
            planet = str(payload.get("planet_slug") or "")
            score = payload.get("explain_score")
            passed = bool(payload.get("pass"))
            hint = f"费曼讲解 {planet or '知识点'}"
            if isinstance(score, (int, float)):
                hint += f"（{float(score):.2f}）"
            if passed or (isinstance(score, (int, float)) and float(score) >= 0.75):
                updated.prior_knowledge.score = _clamp(int(getattr(updated.prior_knowledge, "score", 50) or 50) + 4)
                updated.cognitive_style.score = _clamp(int(getattr(updated.cognitive_style, "score", 50) or 50) + 2)
                _push_evidence(updated.prior_knowledge, f"讲闸通过：{hint}")
                _push_evidence(updated.cognitive_style, f"费曼表达：{hint}")
            else:
                updated.mistake_tendency.score = _clamp(int(getattr(updated.mistake_tendency, "score", 50) or 50) - 2)
                _push_evidence(updated.mistake_tendency, f"讲闸待补：{hint}")
                updated.learning_goal.score = _clamp(int(getattr(updated.learning_goal, "score", 50) or 50) + 1)
                _push_evidence(updated.learning_goal, f"需复述巩固：{planet or '当前知识点'}")

        elif et == "workshop_ingest":
            source = "workshop"
            title = str(payload.get("title") or e.summary or "工坊产物")
            updated.cognitive_style.score = _clamp(updated.cognitive_style.score + 2)
            _push_evidence(updated.cognitive_style, f"工坊入库：{title}")
            _push_evidence(updated.major_background, f"航迹：保存 {title}")

        elif et == "interview_completed":
            source = "interview"
            overall = payload.get("overall_score")
            dims = payload.get("dimension_scores") if isinstance(payload.get("dimension_scores"), dict) else {}
            weak_turns = int(payload.get("weak_turns") or 0)
            if isinstance(overall, (int, float)):
                delta = 2 if float(overall) >= 70 else -2
                updated.prior_knowledge.score = _clamp(
                    int(getattr(updated.prior_knowledge, "score", 50) or 50) + delta
                )
                _push_evidence(updated.prior_knowledge, e.summary or f"模拟面试综合 {overall}")
            weak_labels = [
                str(k)
                for k, v in dims.items()
                if isinstance(v, (int, float)) and float(v) < 70
            ]
            if weak_turns or weak_labels:
                penalty = min(10, 2 * max(weak_turns, len(weak_labels)))
                updated.mistake_tendency.score = _clamp(
                    int(getattr(updated.mistake_tendency, "score", 50) or 50) - penalty
                )
                hint = "、".join(weak_labels[:3]) if weak_labels else f"{weak_turns} 道弱项"
                _push_evidence(updated.mistake_tendency, f"面试弱项：{hint}")
            updated.motivation_level.score = _clamp(
                int(getattr(updated.motivation_level, "score", 50) or 50) + 2
            )
            _push_evidence(updated.motivation_level, e.summary or "完成模拟面试")

        elif "clip" in et or et.endswith("_clip"):
            _push_evidence(updated.prior_knowledge, e.summary or "划词剪藏")

        elif "wrong" in et or "mistake" in et:
            updated.mistake_tendency.score = _clamp(updated.mistake_tendency.score - 5)
            _push_evidence(updated.mistake_tendency, e.summary or et)
        elif "correct" in et or "lit" in et:
            updated.prior_knowledge.score = _clamp(updated.prior_knowledge.score + 3)
            _push_evidence(updated.prior_knowledge, e.summary or et)

    return source


async def refresh_profile_from_events(session: AsyncSession, user_id: str) -> Optional[StudentProfile]:
    events = (
        await session.execute(
            select(ProfileLearningEvent)
            .where(ProfileLearningEvent.user_id == user_id, ProfileLearningEvent.processed.is_(False))
            .order_by(ProfileLearningEvent.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    if not events:
        return None

    latest = await get_latest_profile(session, user_id=user_id)
    event_lines = "\n".join(f"- [{e.event_type}] {e.summary}" for e in reversed(events))
    base = _profile_to_extract(latest) if latest else StudentProfileExtract(student_name="星轨学习者")
    floors = (latest.dimension_floors_json or {}) if latest else {}
    warnings = list(latest.warnings_json or []) if latest else []

    updated = StudentProfileExtract.model_validate(base.model_dump())
    update_source = _apply_structured_payload(updated, list(events))

    # 有 vault_analyze 时以结构化结果为主，跳过二次全量 LLM 以免漂移
    has_vault = any(e.event_type == "vault_analyze" for e in events)
    if llm_available() and not has_vault:
        prompt = f"""基于当前学生画像与近期学习行为，增量更新八维画像 JSON。
当前画像：{updated.model_dump_json()[:2400]}
近期行为：
{event_lines}

要求：重点更新 prior_knowledge、mistake_tendency、motivation_level、modality_preference；保留已有 evidence 并追加；返回完整 StudentProfileExtract JSON。"""
        raw = await llm_chat(
            [{"role": "system", "content": "你是 Profiler Agent，只做 JSON 输出。"}, {"role": "user", "content": prompt}],
            temperature=0.4,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw)
            if parsed:
                try:
                    llm_updated = StudentProfileExtract.model_validate(parsed)
                    # 合并结构化 evidence
                    for dim in PROFILE_DIMENSIONS:
                        cur = getattr(updated, dim)
                        nxt = getattr(llm_updated, dim)
                        merged_ev = list(dict.fromkeys([*(nxt.evidence or []), *(cur.evidence or [])]))[:8]
                        nxt.evidence = merged_ev
                    updated = llm_updated
                    update_source = "auto_refresh"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("profile refresh validate failed: %s", exc)

    if not (updated.summary or "").strip():
        updated.summary = f"已根据 {len(events)} 条学习行为更新画像"
    if "[随学随新" not in (updated.summary or "") and update_source == "auto_refresh":
        updated.summary = (updated.summary or "") + " [随学随新自动更新]"

    saved = await save_student_profile(
        session,
        updated,
        user_id=user_id,
        dimension_floors=floors if isinstance(floors, dict) else {},
        warnings=warnings,
        apply_floor_merge=True,
        update_source=update_source,
    )
    for e in events:
        e.processed = True
    await session.commit()
    return saved


async def list_profile_timeline(
    session: AsyncSession, limit: int = 30, *, user_id: str | None = None
) -> List[ProfileTimelineItem]:
    stmt = select(StudentProfile).order_by(desc(StudentProfile.created_at)).limit(limit)
    if user_id:
        stmt = stmt.where(StudentProfile.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    out: list[ProfileTimelineItem] = []
    for row in rows:
        scores = {}
        for dim in PROFILE_DIMENSIONS:
            data = getattr(row, dim) or {}
            if isinstance(data, dict):
                scores[dim] = int(data.get("score") or 0)
        source = getattr(row, "update_source", None) or ""
        if not source:
            source = "auto_refresh" if "[随学随新" in (row.summary or "") else "profiler"
        out.append(
            ProfileTimelineItem(
                id=row.id,
                student_name=row.student_name,
                summary=row.summary or "",
                scores=scores,
                created_at=row.created_at.isoformat() if row.created_at else None,
                source=source,
            )
        )
    return out


async def list_dimension_evidence(
    session: AsyncSession,
    user_id: str,
    *,
    dimension: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    latest = await get_latest_profile(session, user_id=user_id)
    dim_evidence: list[dict] = []
    if latest and dimension and dimension in PROFILE_DIMENSIONS:
        data = getattr(latest, dimension) or {}
        for text in list((data.get("evidence") if isinstance(data, dict) else []) or [])[:12]:
            dim_evidence.append(
                {
                    "at": latest.updated_at.isoformat() if latest.updated_at else "",
                    "event_type": "profile_evidence",
                    "summary": text,
                    "delta_hint": "",
                    "link": "",
                    "dimension": dimension,
                }
            )

    events = (
        await session.execute(
            select(ProfileLearningEvent)
            .where(ProfileLearningEvent.user_id == user_id)
            .order_by(ProfileLearningEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    event_items: list[dict] = []
    for e in events:
        payload = e.payload_json if isinstance(e.payload_json, dict) else {}
        layer = ""
        if e.event_type == "vault_analyze":
            layer = "trajectory"
        elif e.event_type == "challenge_submit":
            layer = "mastery"
        elif e.event_type in ("workshop_ingest",):
            layer = "trajectory"
        elif e.event_type == "interview_completed":
            layer = "mastery"
        if dimension:
            want = DIM_LAYER.get(dimension, "")
            # 过滤：维度有指定时，只保留相关层或含该维关键词的事件
            if want and layer and layer != want and e.event_type not in ("vault_analyze", "challenge_submit", "workshop_ingest"):
                continue
            if dimension == "mistake_tendency" and e.event_type == "challenge_submit" and payload.get("correct"):
                if str(payload.get("self_confidence") or "") not in ("hesitant", "unknown"):
                    continue
        event_items.append(
            {
                "at": e.created_at.isoformat() if e.created_at else "",
                "event_type": e.event_type,
                "summary": e.summary,
                "delta_hint": _delta_hint(e.event_type, payload),
                "link": str(payload.get("vault_path") or payload.get("resource_id") or ""),
                "dimension": dimension or "",
                "payload": {
                    "self_confidence": payload.get("self_confidence"),
                    "weak_topics": (payload.get("ai") or {}).get("weak_topics")
                    if isinstance(payload.get("ai"), dict)
                    else payload.get("weak_topics"),
                    "title": payload.get("title"),
                    "planet_slug": payload.get("planet_slug"),
                },
            }
        )

    return {
        "dimension": dimension,
        "profile_evidence": dim_evidence,
        "events": event_items,
        "items": dim_evidence + event_items,
    }


def _delta_hint(event_type: str, payload: dict) -> str:
    if event_type == "vault_analyze":
        ai = payload.get("ai") if isinstance(payload.get("ai"), dict) else {}
        weak = ai.get("weak_topics") or []
        return f"薄弱 {len(weak)} 项" if weak else "知识库分析"
    if event_type == "challenge_submit":
        conf = str(payload.get("self_confidence") or "")
        ok = bool(payload.get("correct"))
        parts = ["正确" if ok else "错误"]
        if conf:
            parts.append({"sure": "确定", "hesitant": "犹豫", "unknown": "不会"}.get(conf, conf))
        return " · ".join(parts)
    if event_type == "workshop_ingest":
        return "航迹+1"
    if event_type == "interview_completed":
        score = payload.get("overall_score")
        return f"综合 {score}" if score is not None else "完成面试"
    return ""


async def profile_source_meta(session: AsyncSession, user_id: str) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(StudentProfile)
            .where(StudentProfile.user_id == user_id)
            .order_by(desc(StudentProfile.created_at))
            .limit(40)
        )
    ).scalars().all()
    last_sources: dict[str, str] = {}
    for row in rows:
        src = getattr(row, "update_source", None) or ""
        if not src:
            src = "auto_refresh" if "[随学随新" in (row.summary or "") else "profiler"
        key = src
        if key not in last_sources and row.created_at:
            last_sources[key] = row.created_at.isoformat()

    pending = await _count_pending(session, user_id)
    latest = rows[0] if rows else None
    layers = {"trajectory": 0, "mastery": 0, "will": 0}
    if latest:
        for dim, layer in DIM_LAYER.items():
            data = getattr(latest, dim) or {}
            ev = (data.get("evidence") if isinstance(data, dict) else []) or []
            layers[layer] = layers.get(layer, 0) + len(ev)

    recent_events = (
        await session.execute(
            select(ProfileLearningEvent)
            .where(ProfileLearningEvent.user_id == user_id)
            .order_by(ProfileLearningEvent.created_at.desc())
            .limit(8)
        )
    ).scalars().all()
    layer_summaries = {
        "trajectory": "近期学习航迹尚少",
        "mastery": "掌握证据待积累",
        "will": "目标与节奏待明确",
    }
    for e in recent_events:
        if e.event_type == "vault_analyze" and e.summary:
            layer_summaries["trajectory"] = e.summary[:80]
        elif e.event_type == "challenge_submit":
            layer_summaries["mastery"] = e.summary[:80]
        elif e.event_type == "workshop_ingest":
            layer_summaries["trajectory"] = e.summary[:80]
        elif e.event_type == "interview_completed":
            layer_summaries["mastery"] = (e.summary or "完成模拟面试")[:80]

    if latest:
        lg = latest.learning_goal if isinstance(latest.learning_goal, dict) else {}
        if lg.get("value"):
            layer_summaries["will"] = str(lg.get("value"))[:80]

    return {
        "last_sources": last_sources,
        "pending_events": pending,
        "layers": layers,
        "layer_summaries": layer_summaries,
        "update_source": getattr(latest, "update_source", "") if latest else "",
        "updated_at": latest.updated_at.isoformat() if latest and latest.updated_at else "",
    }


def build_profile_reason(latest: StudentProfile | None) -> str:
    if latest is None:
        return ""
    weak_bits: list[str] = []
    mt = latest.mistake_tendency if isinstance(latest.mistake_tendency, dict) else {}
    pk = latest.prior_knowledge if isinstance(latest.prior_knowledge, dict) else {}
    for text in list(mt.get("evidence") or [])[:2]:
        weak_bits.append(str(text))
    for text in list(pk.get("evidence") or [])[:1]:
        if "待补强" in str(text) or "薄弱" in str(text):
            weak_bits.append(str(text))
    if int(mt.get("score") or 50) < 55:
        weak_bits.append(str(mt.get("value") or "易错倾向偏高"))
    if not weak_bits:
        return ""
    return f"因画像证据：{weak_bits[0][:60]}"
