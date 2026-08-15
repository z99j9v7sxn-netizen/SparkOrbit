"""Teacher Agent 出题 + Evaluator 判题 + 行星点亮闭环。

单行星挑战（练闸）：教导摘要 → 5 题混合小测，答对 ≥4 通过练闸；
四闸齐备后才点亮（见 mastery_gates）。
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.hallucination import HallucinationTicket
from app.models.mastery import ChallengeQuestion, PlanetMastery
from app.models.user import User
from app.models.zone_extras import MistakeRecord
from app.schemas.galaxy import (
    ChallengeOption,
    ChallengeOut,
    SubmitChallengeRequest,
    SubmitChallengeResult,
)
from app.services.constellation import check_newly_completed
from app.services.llm import llm_available
from app.services import mastery_gates as gates
from app.services.gate_policy import get_thresholds_for_user
from app.services.rag import build_rag_context
from app.services.spark import extract_json, spark_chat

# 练闸：5 题答对 ≥4（不再因练习直接 lit）；运行时优先读 GatePolicy
CHALLENGE_QUESTIONS_PER_PLANET = gates.PRACTICE_QUESTIONS
MIN_CORRECT_TO_LIT = gates.PRACTICE_MIN_CORRECT

# session_id -> 小测会话
_SESSIONS: dict[str, dict[str, Any]] = {}

TEACHER_SYSTEM = """你是 SparkOrbit 星轨学图中的 Teacher Agent（严谨的出题考官）。
请针对给定知识点生成一道四选一单项选择题，用于检测学生的核心理解。
严格返回 JSON，不要输出 Markdown 或多余文字，格式：
{
  "question": "题干",
  "options": [{"key": "A", "text": "..."}, {"key": "B", "text": "..."}, {"key": "C", "text": "..."}, {"key": "D", "text": "..."}],
  "answer_key": "A",
  "explanation": "为什么正确以及其他选项为何错误",
  "knowledge_point_id": "必须等于给定的知识点 slug",
  "expected_key_points": ["本题必须覆盖的核心要点1", "要点2"],
  "traps": ["干扰项设计意图1", "干扰项设计意图2"],
  "source_refs": ["planet:<slug>"],
  "source_pages": [{"book":"教材名或校本材料","page":1,"snippet":"依据摘录"}]
}
要求：四个选项互斥且只有一个正确；难度与要求一致；题干聚焦该知识点；knowledge_point_id 不得编造其他知识点；expected_key_points 至少 2 条；每题必须含 source_pages（至少 1 条有效页码，page>0）。"""

TEACHER_BATCH_SYSTEM = """你是 SparkOrbit 星轨学图中的 Teacher Agent（严谨的出题考官）。
请针对给定知识点生成 {n} 道互不重复的四选一单项选择题，由易到难覆盖不同角度。
严格返回 JSON，不要输出 Markdown 或多余文字，格式：
{{
  "questions": [
    {{
      "question": "题干",
      "options": [{{"key": "A", "text": "..."}}, {{"key": "B", "text": "..."}}, {{"key": "C", "text": "..."}}, {{"key": "D", "text": "..."}}],
      "answer_key": "A",
      "explanation": "简要解析",
      "knowledge_point_id": "知识点 slug",
      "expected_key_points": ["核心要点"],
      "traps": ["干扰项意图"],
      "source_refs": ["planet:<slug>"],
      "source_pages": [{{"book":"教材名","page":1,"snippet":"依据摘录"}}]
    }}
  ]
}}
要求：每题四个选项互斥且只有一个正确；题干聚焦该知识点且互不雷同；knowledge_point_id 必须与给定 slug 一致；每题含 expected_key_points；每题必须含 source_pages（page>0）。"""

CONFIDENCE_THRESHOLD = 0.55

TEACH_SYSTEM = """你是 SparkOrbit 的 Tutor Agent。请为该知识点写一段 80 字以内的教导摘要，
帮助学生在答题前快速回顾核心概念。只返回纯文本摘要，不要 Markdown、列表或 JSON。"""


def _fallback_question(planet: Planet, variant: int = 0) -> dict:
    """无大模型或调用失败时的本地兜底题（保证闭环可演示）。"""
    name = planet.name
    variants = [
        {
            "question": f"关于「{name}」，下列哪一项描述最准确地反映了它的核心要点？",
            "options": [
                {"key": "A", "text": f"{name} 的核心概念与典型应用"},
                {"key": "B", "text": f"与 {name} 完全无关的干扰项一"},
                {"key": "C", "text": f"与 {name} 完全无关的干扰项二"},
                {"key": "D", "text": f"对 {name} 的常见错误理解"},
            ],
            "answer_key": "A",
            "explanation": f"选项 A 概括了 {name} 的核心概念；其余选项为无关或错误理解。（离线兜底题）",
        },
        {
            "question": f"学习「{name}」时，最应优先把握的是哪一点？",
            "options": [
                {"key": "A", "text": "死记硬背全部术语而不理解"},
                {"key": "B", "text": f"{name} 的定义、适用场景与边界条件"},
                {"key": "C", "text": "跳过练习直接进入下一知识点"},
                {"key": "D", "text": "只关注与之无关的周边概念"},
            ],
            "answer_key": "B",
            "explanation": f"掌握 {name} 应抓住定义、场景与边界，而非死记或跳过练习。（离线兜底题）",
        },
        {
            "question": f"下列关于「{name}」的说法，哪一项更合理？",
            "options": [
                {"key": "A", "text": f"{name} 与任何实际问题都无关"},
                {"key": "B", "text": f"{name} 可以替代所有其他知识点"},
                {"key": "C", "text": f"结合例题与对比辨析能更好巩固 {name}"},
                {"key": "D", "text": "一旦听过讲解就不必再练习"},
            ],
            "answer_key": "C",
            "explanation": f"通过例题与对比辨析巩固 {name} 是更有效的学习方式。（离线兜底题）",
        },
    ]
    return variants[variant % len(variants)]


def _normalize_source_pages(data: dict | None, planet: Planet) -> list[dict]:
    pages: list[dict] = []
    raw = data.get("source_pages") if isinstance(data, dict) else None
    if isinstance(raw, list):
        for p in raw:
            if not isinstance(p, dict):
                continue
            book = str(p.get("book") or p.get("book_title") or "").strip()
            try:
                page_no = int(p.get("page") or p.get("page_no") or 0)
            except (TypeError, ValueError):
                page_no = 0
            snippet = str(p.get("snippet") or "")[:200]
            if book and page_no > 0:
                pages.append({"book": book, "page": page_no, "snippet": snippet})
    if not pages:
        pages = [{"book": f"planet:{planet.slug}", "page": 1, "snippet": (planet.description or planet.name)[:120]}]
    return pages[:4]


def _normalize_question_data(data: dict | None, planet: Planet, variant: int = 0) -> dict:
    if not data or "options" not in data or "answer_key" not in data:
        fb = _fallback_question(planet, variant)
        fb["knowledge_point_id"] = planet.slug
        fb["expected_key_points"] = [planet.name, "核心定义与适用场景"]
        fb["traps"] = ["常见错误理解", "无关干扰项"]
        fb["source_refs"] = [f"planet:{planet.slug}"]
        fb["source_pages"] = _normalize_source_pages(None, planet)
        return fb
    options = [{"key": str(o.get("key")), "text": str(o.get("text"))} for o in data.get("options", []) if o.get("key")]
    if len(options) < 2:
        fb = _fallback_question(planet, variant)
        fb["knowledge_point_id"] = planet.slug
        fb["expected_key_points"] = [planet.name, "核心定义与适用场景"]
        fb["traps"] = ["常见错误理解", "无关干扰项"]
        fb["source_refs"] = [f"planet:{planet.slug}"]
        fb["source_pages"] = _normalize_source_pages(None, planet)
        return fb
    traps = data.get("traps") if isinstance(data.get("traps"), list) else ["常见混淆点"]
    refs = data.get("source_refs") if isinstance(data.get("source_refs"), list) else [f"planet:{planet.slug}"]
    key_points = data.get("expected_key_points") if isinstance(data.get("expected_key_points"), list) else []
    if not key_points:
        key_points = [planet.name, "核心定义与适用边界"]
    return {
        "question": str(data.get("question", "")),
        "options": options,
        "answer_key": str(data.get("answer_key", "A")).strip().upper()[:1],
        "explanation": str(data.get("explanation", "")),
        "knowledge_point_id": str(data.get("knowledge_point_id") or planet.slug),
        "expected_key_points": [str(x) for x in key_points][:6],
        "traps": [str(t) for t in traps][:5],
        "source_refs": [str(r) for r in refs][:5],
        "source_pages": _normalize_source_pages(data, planet),
    }


async def _generate_teaching_summary(planet: Planet) -> str:
    fallback = f"「{planet.name}」：{planet.description or '把握核心定义与典型应用，再通过练习巩固。'}"
    if len(fallback) > 120:
        fallback = fallback[:117] + "…"
    tags = "、".join(planet.question_tags or []) or planet.name
    rag_ctx = build_rag_context(planet.name)
    content = await spark_chat(
        [
            {"role": "system", "content": TEACH_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"知识点：{planet.name}\n说明：{planet.description}\n标签：{tags}\n"
                    f"难度：{planet.difficulty}\n{rag_ctx}\n请写教导摘要。"
                ),
            },
        ],
        temperature=0.5,
    )
    summary = (content or "").strip().strip("`")
    if summary.lower().startswith("json"):
        summary = summary[4:].strip()
    return summary[:200] if summary else fallback


async def _generate_question_payloads(planet: Planet, count: int) -> list[dict]:
    tags = "、".join(planet.question_tags or []) or planet.name
    rag_ctx = build_rag_context(planet.name)
    user_prompt = (
        f"知识点名称：{planet.name}\n"
        f"知识点说明：{planet.description}\n"
        f"考察标签：{tags}\n"
        f"难度：{planet.difficulty}\n"
        f"{rag_ctx}\n"
        f"请据此出 {count} 道单项选择题。"
    )
    content = await spark_chat(
        [
            {"role": "system", "content": TEACHER_BATCH_SYSTEM.format(n=count)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    data = extract_json(content) if content else None
    raw_list = data.get("questions") if isinstance(data, dict) else None
    payloads: list[dict] = []
    if isinstance(raw_list, list):
        for i, item in enumerate(raw_list[:count]):
            if isinstance(item, dict):
                payloads.append(_normalize_question_data(item, planet, i))
    while len(payloads) < count:
        # 单题补全
        single_prompt = (
            f"知识点名称：{planet.name}\n知识点说明：{planet.description}\n"
            f"考察标签：{tags}\n难度：{planet.difficulty}\n{rag_ctx}\n"
            f"请出第 {len(payloads) + 1} 道互不重复的单项选择题。"
        )
        single = await spark_chat(
            [{"role": "system", "content": TEACHER_SYSTEM}, {"role": "user", "content": single_prompt}],
            temperature=0.75,
        )
        payloads.append(_normalize_question_data(extract_json(single) if single else None, planet, len(payloads)))
    return payloads[:count]


def _challenge_to_out(
    challenge: ChallengeQuestion,
    planet: Planet,
    *,
    teaching_summary: str,
    session_id: str,
    question_index: int,
    total_questions: int,
    mastery: PlanetMastery | None = None,
    min_correct_to_lit: int | None = None,
    policy: dict[str, Any] | None = None,
) -> ChallengeOut:
    options = [ChallengeOption(**o) for o in (challenge.options or [])]
    snap = gates.gate_snapshot(mastery, policy) if mastery else {}
    return ChallengeOut(
        challenge_id=challenge.id,
        planet_id=planet.id,
        planet_name=planet.name,
        question=challenge.question,
        options=options,
        difficulty=planet.difficulty,
        teaching_summary=teaching_summary,
        session_id=session_id,
        question_index=question_index,
        total_questions=total_questions,
        min_correct_to_lit=min_correct_to_lit if min_correct_to_lit is not None else MIN_CORRECT_TO_LIT,
        mastery_phase=str(snap.get("mastery_phase") or "dim"),
        gates=dict(snap.get("gates") or {}),
        can_challenge=bool(snap.get("can_challenge", True)),
        lit_ready=bool(snap.get("lit_ready", False)),
    )


async def generate_challenge(
    session: AsyncSession, user: User, planet_slug: str, *, review: bool = False
) -> ChallengeOut | None:
    planet = (
        await session.execute(select(Planet).where(Planet.slug == planet_slug))
    ).scalar_one_or_none()
    if planet is None:
        return None

    mastery = await gates.ensure_mastery(session, user.id, planet.id)
    # 班级门控策略（无记录则回退常量 / 行星标签启发式）
    galaxy_slug = ""
    try:
        from app.models.galaxy import Galaxy

        g = (await session.execute(select(Galaxy).where(Galaxy.id == planet.galaxy_id))).scalar_one_or_none()
        galaxy_slug = g.slug if g else ""
    except Exception:
        galaxy_slug = ""
    thresholds = await get_thresholds_for_user(session, user, galaxy_slug)
    n_questions = int(thresholds.get("practice_questions") or CHALLENGE_QUESTIONS_PER_PLANET)
    min_correct = int(thresholds.get("practice_min_correct") or MIN_CORRECT_TO_LIT)
    # 衰减复习：缩短练闸（2～3 题），降低摩擦但仍需答对多数
    if review:
        n_questions = min(3, max(2, n_questions // 2 or 2))
        min_correct = max(1, min(n_questions, (n_questions + 1) // 2))

    tags = [str(t).lower() for t in (planet.question_tags or [])]
    if getattr(user, "class_id", ""):
        apply_required = bool(thresholds.get("apply_required_default", True))
        if any(t in tags for t in ("code", "coding", "编程", "算法实现")) or planet.difficulty == "hard":
            apply_required = True
    else:
        apply_required = any(t in tags for t in ("code", "coding", "编程", "算法实现")) or planet.difficulty == "hard"
    gates.set_apply_required(mastery, apply_required)
    await session.commit()

    snap = gates.gate_snapshot(mastery, thresholds)
    if not snap.get("can_challenge"):
        # 返回空题提示学闸：用 teaching_summary 传达
        return ChallengeOut(
            challenge_id="",
            planet_id=planet.id,
            planet_name=planet.name,
            question="",
            options=[],
            difficulty=planet.difficulty,
            teaching_summary="请先完成「学」闸：打开星库教材、观看视频、演武舱步进或生成资源后再挑战。",
            session_id="",
            question_index=0,
            total_questions=n_questions,
            min_correct_to_lit=min_correct,
            mastery_phase=str(snap.get("mastery_phase") or "dim"),
            gates=dict(snap.get("gates") or {}),
            can_challenge=False,
            lit_ready=False,
        )

    teaching_summary = await _generate_teaching_summary(planet)
    payloads = await _generate_question_payloads(planet, n_questions)

    challenges: list[ChallengeQuestion] = []
    for data in payloads:
        meta = {
            "knowledge_point_id": str(data.get("knowledge_point_id") or planet.slug),
            "expected_key_points": data.get("expected_key_points") or [planet.name],
            "traps": data.get("traps") or [],
            "source_refs": data.get("source_refs") or [f"planet:{planet.slug}"],
            "source_pages": data.get("source_pages") or _normalize_source_pages(None, planet),
        }
        challenge = ChallengeQuestion(
            user_id=user.id,
            planet_id=planet.id,
            question=str(data.get("question", "")),
            options=data["options"],
            answer_key=str(data.get("answer_key", "A")).strip().upper()[:1],
            explanation=str(data.get("explanation", "")),
            difficulty=planet.difficulty,
            tags=list(planet.question_tags or []),
            meta_json=meta,
        )
        session.add(challenge)
        challenges.append(challenge)

    await session.commit()
    for c in challenges:
        await session.refresh(c)

    session_id = f"pc-{uuid.uuid4().hex[:12]}"
    _SESSIONS[session_id] = {
        "user_id": user.id,
        "planet_id": planet.id,
        "planet_slug": planet_slug,
        "challenge_ids": [c.id for c in challenges],
        "current_index": 0,
        "correct_count": 0,
        "answered": 0,
        "teaching_summary": teaching_summary,
        "practice_min_correct": min_correct,
        "practice_questions": n_questions,
        "thresholds": thresholds,
    }

    return _challenge_to_out(
        challenges[0],
        planet,
        teaching_summary=teaching_summary,
        session_id=session_id,
        question_index=1,
        total_questions=len(challenges),
        mastery=mastery,
        min_correct_to_lit=min_correct,
    )


def _find_session_for_challenge(user_id: str, challenge_id: str) -> tuple[str | None, dict[str, Any] | None]:
    for sid, data in _SESSIONS.items():
        if data.get("user_id") == user_id and challenge_id in data.get("challenge_ids", []):
            return sid, data
    return None, None


async def _ensure_mastery(session: AsyncSession, user_id: str, planet_id: str) -> PlanetMastery:
    return await gates.ensure_mastery(session, user_id, planet_id)


async def submit_challenge(session: AsyncSession, user: User, req: SubmitChallengeRequest) -> SubmitChallengeResult | None:
    challenge = (
        await session.execute(select(ChallengeQuestion).where(ChallengeQuestion.id == req.challenge_id))
    ).scalar_one_or_none()
    if challenge is None or challenge.user_id != user.id:
        return None
    if challenge.answered:
        return None

    selected = req.selected_key.strip().upper()[:1]
    correct = selected == challenge.answer_key
    challenge.answered = True
    challenge.correct = correct
    challenge.selected_key = selected
    session.add(challenge)

    planet = (await session.execute(select(Planet).where(Planet.id == challenge.planet_id))).scalar_one_or_none()
    mastery = await _ensure_mastery(session, user.id, challenge.planet_id)
    mastery.attempts += 1

    session_id, quiz = _find_session_for_challenge(user.id, challenge.id)
    total_questions = CHALLENGE_QUESTIONS_PER_PLANET
    thresholds: dict[str, Any] = {}
    min_needed = MIN_CORRECT_TO_LIT
    if quiz:
        total_questions = len(quiz["challenge_ids"])
        quiz["answered"] += 1
        if correct:
            quiz["correct_count"] += 1
        # 推进当前下标到下一题
        try:
            idx = quiz["challenge_ids"].index(challenge.id)
            quiz["current_index"] = max(quiz["current_index"], idx + 1)
        except ValueError:
            quiz["current_index"] = quiz["answered"]
        session_correct = quiz["correct_count"]
        session_answered = quiz["answered"]
        teaching_summary = str(quiz.get("teaching_summary") or "")
        min_needed = int(quiz.get("practice_min_correct") or MIN_CORRECT_TO_LIT)
        thresholds = dict(quiz.get("thresholds") or {})
    else:
        # 无会话：不计点亮，仅记录单题（废除「答对即 lit」）
        session_id = ""
        session_correct = 1 if correct else 0
        session_answered = 1
        total_questions = CHALLENGE_QUESTIONS_PER_PLANET
        teaching_summary = ""
        try:
            thresholds = await get_thresholds_for_user(session, user, "")
            min_needed = int(thresholds.get("practice_min_correct") or MIN_CORRECT_TO_LIT)
            total_questions = int(thresholds.get("practice_questions") or CHALLENGE_QUESTIONS_PER_PLANET)
        except Exception:
            thresholds = {}

    if correct:
        mastery.correct_count += 1
        mastery.score = min(100, 60 + mastery.correct_count * 12)
        user.mood = "celebrate"
    else:
        wrong = list(mastery.last_wrong_tags or [])
        for tag in challenge.tags or []:
            if tag not in wrong:
                wrong.append(tag)
        mastery.last_wrong_tags = wrong[-10:]
        mastery.score = max(0, mastery.score - 5)
        user.mood = "confused"
        # 错题本
        opt_map = {str(o.get("key")): str(o.get("text")) for o in (challenge.options or []) if o.get("key")}
        session.add(
            MistakeRecord(
                user_id=user.id,
                question=challenge.question,
                student_answer=f"{selected}. {opt_map.get(selected, selected)}",
                correct_answer=f"{challenge.answer_key}. {opt_map.get(challenge.answer_key, challenge.answer_key)}",
                subject=(planet.name if planet else ""),
                note=(challenge.explanation or "")[:500],
            )
        )

    session_done = bool(quiz) and session_answered >= total_questions
    just_lit = False
    gate_snap: dict[str, Any] = gates.gate_snapshot(mastery, thresholds or None)

    if session_done:
        snap = gates.pass_practice_gate(
            mastery,
            correct=session_correct,
            total=total_questions,
            min_correct=min_needed,
            questions=total_questions,
            policy=thresholds or None,
        )
        gate_snap = snap
        # 练闸通过 ≠ 点亮；需四闸齐备
        just_lit = gates.try_light_planet(mastery)
        if just_lit:
            user.points += 10
        if session_id and session_id in _SESSIONS:
            del _SESSIONS[session_id]

    session.add(mastery)
    session.add(user)

    # 学习事件 → 画像可感知更新
    try:
        from app.services.profile_refresh import record_learning_event, refresh_profile_from_events

        await record_learning_event(
            session,
            user_id=user.id,
            event_type="challenge_submit",
            summary=(
                f"{'点亮' if just_lit else ('练闸通过' if session_done and session_correct >= min_needed else ('答对' if correct else '答错'))} "
                f"{planet.name if planet else '知识点'} "
                f"（{session_correct}/{session_answered}）"
            ),
            payload={
                "planet_slug": planet.slug if planet else "",
                "correct": correct,
                "lit": just_lit,
                "session_done": session_done,
                "gates": gate_snap.get("gates"),
                "mastery_phase": gate_snap.get("mastery_phase"),
                "self_confidence": (getattr(req, "self_confidence", "") or "").strip(),
            },
        )
        if session_done:
            await refresh_profile_from_events(session, user.id)
            try:
                from app.services.learning_path import sync_path_after_mastery_change

                await sync_path_after_mastery_change(session, user)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass

    await session.commit()

    constellation = None
    if just_lit and planet:
        constellation = await check_newly_completed(session, user.id, planet.slug)

    next_out: ChallengeOut | None = None
    question_index = session_answered
    if not session_done and quiz and session_id:
        next_idx = quiz["current_index"]
        ids = quiz["challenge_ids"]
        if next_idx < len(ids) and planet:
            next_row = (
                await session.execute(select(ChallengeQuestion).where(ChallengeQuestion.id == ids[next_idx]))
            ).scalar_one_or_none()
            if next_row:
                next_out = _challenge_to_out(
                    next_row,
                    planet,
                    teaching_summary=teaching_summary,
                    session_id=session_id,
                    question_index=next_idx + 1,
                    total_questions=total_questions,
                    mastery=mastery,
                    min_correct_to_lit=min_needed,
                    policy=thresholds or None,
                )
                question_index = next_idx  # 刚答完的题号；前端用 next 的 index

    fails = 0 if correct else await _consecutive_fails(session, user.id, challenge.planet_id)

    meta = challenge.meta_json if isinstance(challenge.meta_json, dict) else {}
    knowledge_point_id = str(meta.get("knowledge_point_id") or (planet.slug if planet else ""))
    source_refs = [str(x) for x in (meta.get("source_refs") or []) if x]
    if not source_refs and planet:
        source_refs = [f"planet:{planet.slug}"]
    expected_key_points = [str(x) for x in (meta.get("expected_key_points") or []) if x]

    # Evaluator 独立引用（禁止抄 knowledge_point_id 自证）
    from app.services.hallucination_guard import evaluate_submission_consistency

    eval_out = await evaluate_submission_consistency(
        planet_slug=planet.slug if planet else knowledge_point_id,
        planet_name=planet.name if planet else "",
        question=challenge.question or "",
        answer_key=challenge.answer_key or "",
        selected_key=selected,
        explanation=challenge.explanation or "",
        expected_key_points=expected_key_points,
        rule_correct=correct,
    )
    cited_knowledge_point_id = str(eval_out.get("cited_knowledge_point_id") or "")
    confidence = float(eval_out.get("confidence") or 0.5)
    reason = str(eval_out.get("reason") or "")
    contradiction = bool(eval_out.get("contradiction"))

    if req.force_human_review:
        confidence = 0.35
        reason = "演示强制低置信，转教师人审"
    elif ("离线兜底" in (challenge.explanation or "") or not llm_available()) and not correct:
        confidence = min(confidence, 0.42)
        reason = reason or "判题依据不足（离线/降级），需教师复核"

    if cited_knowledge_point_id and knowledge_point_id and cited_knowledge_point_id != knowledge_point_id:
        confidence = min(confidence, 0.4)
        reason = reason or "引用知识点与当前行星不一致"
        contradiction = True

    human_review = (
        confidence < CONFIDENCE_THRESHOLD
        or contradiction
        or (
            bool(cited_knowledge_point_id)
            and bool(knowledge_point_id)
            and cited_knowledge_point_id != knowledge_point_id
        )
    )
    # 矛盾时不以规则对错作为权威终裁展示：前端依赖 human_review_required
    if contradiction and not req.force_human_review:
        reason = reason or "Teacher/Evaluator 逻辑矛盾，已转教师人审"
    ticket_id: str | None = None
    if human_review and planet:
        ticket = HallucinationTicket(
            student_id=user.id,
            teacher_id=getattr(user, "teacher_id", "") or "",
            class_id=getattr(user, "class_id", "") or "",
            challenge_id=challenge.id,
            planet_slug=planet.slug,
            planet_name=planet.name,
            knowledge_point_id=knowledge_point_id,
            cited_knowledge_point_id=cited_knowledge_point_id,
            confidence=float(confidence),
            reason=reason or "置信度低于阈值",
            question_preview=(challenge.question or "")[:240],
            status="pending",
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        ticket_id = ticket.id

    gate_snap = gates.gate_snapshot(mastery)
    try:
        from app.services.calibration import record_or_update_outcome

        if planet:
            await record_or_update_outcome(
                session,
                user_id=user.id,
                planet_slug=planet.slug,
                challenge_id=challenge.id,
                real_correct=bool(correct),
            )
    except Exception:  # noqa: BLE001
        pass

    return SubmitChallengeResult(
        correct=correct,
        answer_key=challenge.answer_key,
        explanation=challenge.explanation,
        planet_status=mastery.status,
        lit=just_lit,
        points=user.points,
        mood=user.mood,
        constellation=constellation,
        consecutive_fails=fails,
        can_emit_sos=(not correct) and fails >= 3,
        session_id=session_id or "",
        session_correct=session_correct,
        session_answered=session_answered,
        total_questions=total_questions,
        min_correct_to_lit=min_needed,
        session_done=session_done,
        question_index=session_answered,
        next_challenge=next_out,
        knowledge_point_id=knowledge_point_id,
        cited_knowledge_point_id=cited_knowledge_point_id,
        confidence=float(round(confidence, 3)),
        human_review_required=human_review,
        review_ticket_id=ticket_id,
        source_refs=source_refs,
        mastery_phase=str(gate_snap.get("mastery_phase") or mastery.status),
        gates=dict(gate_snap.get("gates") or {}),
        practice_passed=bool((gate_snap.get("gates") or {}).get("practice")),
        lit_ready=bool(gate_snap.get("lit_ready")),
    )


async def _consecutive_fails(session: AsyncSession, user_id: str, planet_id: str) -> int:
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
