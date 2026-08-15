"""模拟面试多智能体编排：准备 workflow / 单轮 handoff / council 总评。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.mock_interview import InterviewReport, InterviewSession, InterviewTurn
from app.models.user import User
from app.services import agent_trace
from app.services.interview_catalog import (
    fallback_questions,
    kind_labels,
    kinds_for,
    role_label,
)
from app.services.interview_resume import resume_brief
from app.services.interview_runtime import emit_prep, finish_prep
from app.services.interview_scoring import (
    analyze_frames,
    analyze_prosody,
    dimensions_for,
    fuse_scores,
    pcm_duration_sec,
    estimate_silence_sec,
    rubric_prompt_block,
)
from app.services.llm import extract_json, llm_available, llm_chat, llm_chat_raw

logger = logging.getLogger(__name__)

INTERVIEW_SCENE = "interview"


def build_interview_prep_plan(scenario: str) -> dict[str, Any]:
    kinds = kinds_for(scenario)
    group1 = ["JobAnalyst", "ProfileParser"]
    group2 = ["QuestionPlanner"]
    group3 = [f"Q-{k}" for k in kinds]
    steps: list[dict[str, Any]] = []
    idx = 0
    for gi, group in enumerate([group1, group2, group3], 1):
        for role in group:
            steps.append(
                {
                    "step_index": idx,
                    "agent_role": role,
                    "parallel_group": f"g{gi}",
                    "summary": f"待执行：{role}",
                    "payload": {"kind": role},
                }
            )
            idx += 1
    return {
        "order": group1 + group2 + group3,
        "parallel_groups": [group1, group2, group3],
        "steps": steps,
        "mode": "workflow",
        "scenario": scenario,
        "question_kinds": kinds,
    }


def council_roles_for(scenario: str) -> list[str]:
    if scenario == "academic":
        return ["学科导师", "综合素质官", "科研潜力官"]
    return ["技术官", "HR官", "业务官"]


def _sse(role: str, event_type: str, content: str, payload: dict | None = None) -> dict[str, Any]:
    return {"role": role, "type": event_type, "content": content, "payload": payload or {}}


async def _chat_json(
    system: str,
    user: str,
    *,
    user_id: str,
    endpoint: str,
    temperature: float = 0.3,
    timeout: float = 25.0,
    shield: bool = False,
) -> dict[str, Any]:
    if not llm_available():
        return {}
    fn = llm_chat if shield else llm_chat_raw
    raw = await fn(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        response_json=True,
        timeout=timeout,
        user_id=user_id,
        endpoint=endpoint,
    )
    return extract_json(raw or "") or {}


async def _mark(session: AsyncSession, run_id: str, step_index: int, role: str, *, running: bool, summary: str, ok: bool = True) -> None:
    if not run_id:
        return
    try:
        if running:
            await agent_trace.mark_step_running(session, run_id, step_index=step_index, agent_role=role, summary=summary)
        else:
            await agent_trace.mark_step_done(session, run_id, step_index=step_index, summary=summary, ok=ok)
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_trace step failed run=%s role=%s: %s", run_id, role, exc)


# ---------------------------------------------------------------------------
# 准备阶段 workflow
# ---------------------------------------------------------------------------


async def run_interview_prep(session_id: str) -> None:
    async with AsyncSessionLocal() as db:
        row = await db.get(InterviewSession, session_id)
        if row is None:
            await emit_prep(session_id, _sse("System", "error", "面试会话不存在"))
            finish_prep(session_id, "failed")
            return
        user = await db.get(User, row.user_id)
        if user is None:
            await emit_prep(session_id, _sse("System", "error", "用户不存在"))
            finish_prep(session_id, "failed")
            return

        plan = build_interview_prep_plan(row.scenario)
        run_id = row.prep_run_id or f"iv-prep-{uuid4().hex[:10]}"
        row.prep_run_id = run_id
        await db.commit()

        try:
            await agent_trace.start_agent_run(
                db,
                run_id=run_id,
                user=user,
                scene=INTERVIEW_SCENE,
                mode="workflow",
                topic=f"{role_label(row.job_role)} · {row.scenario}",
                graph_plan=plan,
            )
            await agent_trace.ensure_steps(db, run_id, plan["steps"])
        except Exception as exc:  # noqa: BLE001
            logger.exception("prep trace start failed: %s", exc)

        await emit_prep(
            session_id,
            _sse(
                "Coordinator",
                "start",
                f"正在为「{role_label(row.job_role)}」编排面试题",
                {"graph_plan": plan, "run_id": run_id, "mode": "workflow"},
            ),
        )

        await _mark(db, run_id, 0, "JobAnalyst", running=True, summary="岗位分析中")
        await _mark(db, run_id, 1, "ProfileParser", running=True, summary="画像解析中")

        async def _job_job() -> dict[str, Any]:
            return await _analyze_job(row, user.id)

        async def _job_profile() -> dict[str, Any]:
            return await _parse_profile(row, user.id)

        role_ctx, profile_ctx = await asyncio.gather(_job_job(), _job_profile())
        await emit_prep(session_id, _sse("JobAnalyst", "note", role_ctx.get("summary") or "已完成岗位画像"))
        await emit_prep(session_id, _sse("ProfileParser", "note", profile_ctx.get("summary") or "已完成候选人画像"))
        await _mark(db, run_id, 0, "JobAnalyst", running=False, summary="岗位分析完成")
        await _mark(db, run_id, 1, "ProfileParser", running=False, summary="画像解析完成")

        # 组1 虽上面顺序写了摘要，真正并行的是组3 出题；组1 的两步 LLM 再并行一次补强
        # 组2 题目规划
        await _mark(db, run_id, 2, "QuestionPlanner", running=True, summary="题目规划中")
        topics = await _plan_topics(row, role_ctx, profile_ctx, user.id)
        row.prep_intel = {
            "job": {
                "summary": str(role_ctx.get("summary") or ""),
                "skills": [str(x) for x in (role_ctx.get("skills") or [])][:8],
                "risks": [str(x) for x in (role_ctx.get("risks") or [])][:6],
            },
            "profile": {
                "summary": str(profile_ctx.get("summary") or ""),
                "hooks": [str(x) for x in (profile_ctx.get("hooks") or [])][:6],
            },
            "topics": [str(x) for x in (topics.get("topics") or [])][:8],
        }
        await emit_prep(
            session_id,
            _sse("QuestionPlanner", "note", "已规划考察主题：" + "、".join(topics.get("topics") or [])),
        )
        await _mark(db, run_id, 2, "QuestionPlanner", running=False, summary="题目规划完成")

        kinds = kinds_for(row.scenario)
        labels = kind_labels(row.scenario)
        kind_to_step = {s["agent_role"]: int(s["step_index"]) for s in plan["steps"]}

        async def _one_kind(kind: str) -> tuple[str, dict[str, Any], bool]:
            async with AsyncSessionLocal() as own:
                _ = own  # 独立 session，避免共享写锁；本题生成不落库中间态
            try:
                q = await _generate_question(row, kind, role_ctx, profile_ctx, topics, user.id)
                return kind, q, True
            except Exception as exc:  # noqa: BLE001
                logger.exception("question gen failed kind=%s: %s", kind, exc)
                return kind, {}, False

        for kind in kinds:
            role = f"Q-{kind}"
            await _mark(db, run_id, kind_to_step.get(role, 0), role, running=True, summary=f"{labels.get(kind, kind)} 出题中")

        results = await asyncio.gather(*[_one_kind(k) for k in kinds], return_exceptions=True)
        generated: list[dict[str, Any]] = []
        for item in results:
            if isinstance(item, Exception):
                await emit_prep(session_id, _sse("System", "error", f"出题失败：{item}"))
                continue
            kind, payload, ok = item
            role = f"Q-{kind}"
            question = str(payload.get("question") or "")
            if question:
                generated.append({"kind": kind, "question": question})
                await emit_prep(
                    session_id,
                    _sse(role, "question", question, {"kind": kind, "kind_label": labels.get(kind, kind)}),
                )
            await _mark(db, run_id, kind_to_step.get(role, 0), role, running=False, summary=f"{labels.get(kind, kind)} 完成", ok=ok)

        questions = generated or fallback_questions(row.job_role, row.question_count)
        # 按 question_count 截断/循环补齐
        packed = []
        i = 0
        while len(packed) < row.question_count:
            src = questions[i % len(questions)]
            packed.append({"index": len(packed), "kind": src.get("kind") or kinds[0], "question": src["question"]})
            i += 1
        row.questions = packed
        row.status = "ready"
        await db.commit()
        try:
            await agent_trace.finish_agent_run(db, run_id, status="completed")
        except Exception as exc:  # noqa: BLE001
            logger.exception("prep finish trace: %s", exc)

        await emit_prep(
            session_id,
            _sse("Coordinator", "done", f"已准备 {len(packed)} 道面试题", {"questions": packed, "status": "ready"}),
        )
        finish_prep(session_id, "completed")


async def _analyze_job(row: InterviewSession, user_id: str) -> dict[str, Any]:
    data = await _chat_json(
        "你是面试岗位分析官。返回 JSON：{\"summary\":\"岗位考察重点\",\"skills\":[\"\"],\"risks\":[\"\"]}",
        f"岗位：{role_label(row.job_role)}（{row.job_role}）\n场景：{row.scenario}\n难度：{row.difficulty}",
        user_id=user_id,
        endpoint="interview_job_analyst",
    )
    if data:
        return data
    return {"summary": f"{role_label(row.job_role)} 常规考察：基础、项目、协作与应变", "skills": [], "risks": []}


async def _parse_profile(row: InterviewSession, user_id: str) -> dict[str, Any]:
    brief = resume_brief(row.resume_profile)
    mastery_note = ""
    if row.scenario == "academic":
        mastery_note = await _mastery_brief(user_id)
        if mastery_note:
            brief = f"{brief}\n学科掌握：{mastery_note}"
    data = await _chat_json(
        "你是候选人画像官。返回 JSON：{\"summary\":\"可追问点\",\"hooks\":[\"\"]}",
        f"岗位：{role_label(row.job_role)}\n简历摘要：{brief}",
        user_id=user_id,
        endpoint="interview_profile_parser",
    )
    if data:
        if mastery_note:
            data["summary"] = f"{data.get('summary') or ''}；掌握度：{mastery_note}"
        return data
    return {"summary": brief, "hooks": []}


async def _mastery_brief(user_id: str) -> str:
    try:
        from app.models.galaxy import Planet
        from app.models.mastery import PlanetMastery

        async with AsyncSessionLocal() as db:
            rows = (
                await db.execute(
                    select(PlanetMastery, Planet)
                    .join(Planet, Planet.id == PlanetMastery.planet_id)
                    .where(PlanetMastery.user_id == user_id)
                    .order_by(PlanetMastery.score.asc())
                    .limit(6)
                )
            ).all()
        if not rows:
            return ""
        parts = [f"{planet.name}({mastery.score}分/{mastery.status})" for mastery, planet in rows]
        return "弱项优先：" + "、".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mastery brief failed: %s", exc)
        return ""


async def _plan_topics(row: InterviewSession, role_ctx: dict, profile_ctx: dict, user_id: str) -> dict[str, Any]:
    kinds = kinds_for(row.scenario)
    labels = kind_labels(row.scenario)
    data = await _chat_json(
        "你是面试题目规划官。返回 JSON：{\"topics\":[\"每个考察维度一个主题\"]}",
        (
            f"岗位：{role_label(row.job_role)}\n维度：{list(labels.values())}\n"
            f"岗位分析：{role_ctx.get('summary')}\n画像：{profile_ctx.get('summary')}\n"
            f"需要 {len(kinds)} 个主题，顺序对应 {kinds}"
        ),
        user_id=user_id,
        endpoint="interview_question_planner",
    )
    topics = list(data.get("topics") or [])
    while len(topics) < len(kinds):
        topics.append(labels.get(kinds[len(topics)], "综合"))
    return {"topics": topics[: len(kinds)]}


async def _generate_question(
    row: InterviewSession,
    kind: str,
    role_ctx: dict,
    profile_ctx: dict,
    topics: dict,
    user_id: str,
) -> dict[str, Any]:
    labels = kind_labels(row.scenario)
    kinds = kinds_for(row.scenario)
    idx = kinds.index(kind) if kind in kinds else 0
    topic = (topics.get("topics") or [""])[idx] if topics.get("topics") else labels.get(kind, kind)
    data = await _chat_json(
        (
            "你是模拟面试出题官。只出一题，口语化、可在 90 秒内回答。"
            "返回 JSON：{\"question\":\"题目\",\"kind\":\"\"}"
        ),
        (
            f"岗位：{role_label(row.job_role)}\n难度：{row.difficulty}\n维度：{labels.get(kind, kind)}\n"
            f"主题：{topic}\n岗位重点：{role_ctx.get('summary')}\n可追问点：{profile_ctx.get('summary')}\n"
            "不要一次问多个互不相关的问题。"
        ),
        user_id=user_id,
        endpoint="interview_question_gen",
        temperature=0.55,
    )
    question = str(data.get("question") or "").strip()
    if not question:
        bank = fallback_questions(row.job_role, 4)
        hit = next((q for q in bank if q.get("kind") == kind), bank[0])
        question = hit["question"]
    return {"kind": kind, "question": question}


# ---------------------------------------------------------------------------
# 单轮 handoff
# ---------------------------------------------------------------------------


class TurnState(TypedDict, total=False):
    question: str
    transcript: str
    duration_sec: float
    silence_sec: float
    scenario: str
    job_role: str
    resume_brief: str
    frames: list[str]
    semantic: dict[str, Any]
    prosody: dict[str, Any]
    visual: dict[str, Any]
    fused: float
    degraded: list[str]
    feedback: str
    followup_strategy: str
    followup_question: str
    reasons: list[str]
    user_id: str


async def score_interview_turn(
    db: AsyncSession,
    session: InterviewSession,
    *,
    question: str,
    transcript: str,
    pcm_bytes: bytes = b"",
    duration_sec: float = 0.0,
    frames: list[str] | None = None,
    user: User | None = None,
    followup_enabled: bool = False,
) -> dict[str, Any]:
    duration = duration_sec or pcm_duration_sec(pcm_bytes)
    silence = estimate_silence_sec(pcm_bytes) if pcm_bytes else 0.0
    run_id = f"iv-turn-{uuid4().hex[:10]}"
    plan = agent_trace.build_handoff_plan(["AnswerAggregator", "MultimodalScorer", "FollowUpStrategist"])
    try:
        await agent_trace.start_agent_run(
            db,
            run_id=run_id,
            user=user,
            user_id=session.user_id,
            scene=INTERVIEW_SCENE,
            mode="handoff",
            topic=question[:80],
            graph_plan=plan,
        )
        await agent_trace.ensure_steps(db, run_id, plan["steps"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("turn trace start: %s", exc)

    initial: TurnState = {
        "question": question,
        "transcript": transcript,
        "duration_sec": duration,
        "silence_sec": silence,
        "scenario": session.scenario,
        "job_role": session.job_role,
        "resume_brief": resume_brief(session.resume_profile),
        "frames": list(frames or []),
        "user_id": session.user_id,
        "followup_strategy": "next",
        "followup_question": "",
    }

    try:
        from langgraph.graph import END, StateGraph

        result = await _score_via_langgraph(db, run_id, initial, followup_enabled=followup_enabled)
    except Exception as exc:  # noqa: BLE001
        logger.warning("langgraph turn fallback: %s", exc)
        result = await _score_legacy(db, run_id, initial, followup_enabled=followup_enabled)

    try:
        await agent_trace.finish_agent_run(db, run_id, status="completed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("turn trace finish: %s", exc)
    result["run_id"] = run_id
    return result


async def _aggregator_node(state: TurnState) -> TurnState:
    prosody = analyze_prosody(
        transcript=state.get("transcript") or "",
        duration_sec=float(state.get("duration_sec") or 0),
        silence_sec=float(state.get("silence_sec") or 0),
    )
    return {**state, "prosody": prosody}


async def _score_semantic(state: TurnState) -> dict[str, Any]:
    scenario = state.get("scenario") or "job"
    dims = dimensions_for(scenario)
    transcript = (state.get("transcript") or "").strip()
    if not transcript:
        return {
            "overall": 20,
            "dimensions": {k: 20 for k, _ in dims},
            "reasons": ["未识别到有效回答"],
            "feedback": "这一题没有捕捉到完整作答，下一题请对着麦克风、回答结束后再点击「回答完毕」。",
            "followup": "",
        }
    return await _chat_json(
        (
            "你是面试评分官。结合题目与回答，按维度打分。"
            + rubric_prompt_block(scenario)
            + "若回答明显偏弱（overall<55）给出一句针对性追问；若很好（overall>=85）给出一句加压追问；否则 followup 留空。"
            "严格返回 JSON："
            '{"overall":80,"dimensions":{"k":80},"reasons":["扣分理由"],"feedback":"对考生说的点评","followup":""}'
        ),
        (
            f"岗位：{role_label(state.get('job_role') or '')}\n题目：{state.get('question')}\n"
            f"回答转写：{transcript}\n简历：{state.get('resume_brief')}\n"
            f"语音侧写：{state.get('prosody')}"
        ),
        user_id=str(state.get("user_id") or ""),
        endpoint="interview_semantic_score",
        temperature=0.25,
        timeout=25.0,
    )


async def _scorer_node(state: TurnState) -> TurnState:
    user_id = str(state.get("user_id") or "")
    semantic_task = _score_semantic(state)
    visual_task = analyze_frames(list(state.get("frames") or []), user_id=user_id)
    semantic, visual_raw = await asyncio.gather(semantic_task, visual_task)
    if not isinstance(semantic, dict):
        semantic = {}
    visual = visual_raw if isinstance(visual_raw, dict) else {}
    overall = semantic.get("overall")
    try:
        semantic_score = float(overall) if overall is not None else None
    except (TypeError, ValueError):
        semantic_score = None
    if semantic_score is None:
        dim_vals = [float(v) for v in (semantic.get("dimensions") or {}).values() if isinstance(v, (int, float))]
        semantic_score = sum(dim_vals) / len(dim_vals) if dim_vals else 50.0
    prosody_score = None
    if isinstance(state.get("prosody"), dict) and state["prosody"].get("score") is not None:
        prosody_score = float(state["prosody"]["score"])
    visual_score = None
    if visual.get("score") is not None:
        try:
            visual_score = float(visual["score"])
        except (TypeError, ValueError):
            visual_score = None
    fused, degraded = fuse_scores(semantic_score, prosody_score, visual_score)
    return {
        **state,
        "semantic": {**semantic, "score": round(semantic_score, 1)},
        "visual": visual,
        "fused": fused,
        "degraded": degraded,
        "feedback": str(semantic.get("feedback") or ""),
        "reasons": list(semantic.get("reasons") or []) + list(visual.get("reasons") or []),
        "followup_question": str(semantic.get("followup") or "").strip(),
    }


async def _followup_node(state: TurnState, *, enabled: bool) -> TurnState:
    if not enabled:
        return {**state, "followup_strategy": "next", "followup_question": ""}
    fused = float(state.get("fused") or 0)
    question = str(state.get("followup_question") or "").strip()
    if fused < 55:
        strategy = "probe"
    elif fused >= 85:
        strategy = "challenge"
    else:
        strategy = "next"
        question = ""
    if strategy != "next" and not question:
        strategy = "next"
    return {**state, "followup_strategy": strategy, "followup_question": question}


async def _score_via_langgraph(
    db: AsyncSession,
    run_id: str,
    initial: TurnState,
    *,
    followup_enabled: bool,
) -> dict[str, Any]:
    from langgraph.graph import END, StateGraph

    async def aggregator(state: TurnState) -> TurnState:
        return await _aggregator_node(state)

    async def scorer(state: TurnState) -> TurnState:
        return await _scorer_node(state)

    async def followup(state: TurnState) -> TurnState:
        return await _followup_node(state, enabled=followup_enabled)

    graph = StateGraph(TurnState)
    graph.add_node("aggregator", aggregator)
    graph.add_node("scorer", scorer)
    graph.add_node("followup", followup)
    graph.set_entry_point("aggregator")
    graph.add_edge("aggregator", "scorer")
    graph.add_edge("scorer", "followup")
    graph.add_edge("followup", END)
    app = graph.compile()

    await _mark(db, run_id, 0, "AnswerAggregator", running=True, summary="汇总转写与语音特征")
    merged: TurnState = dict(initial)
    async for update in app.astream(merged, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node_name, patch in update.items():
            if isinstance(patch, dict):
                merged = {**merged, **patch}
            if node_name == "aggregator":
                await _mark(db, run_id, 0, "AnswerAggregator", running=False, summary="语音特征已汇总")
                await _mark(db, run_id, 1, "MultimodalScorer", running=True, summary="语义评分中")
            elif node_name == "scorer":
                await _mark(db, run_id, 1, "MultimodalScorer", running=False, summary="语义评分完成")
                await _mark(db, run_id, 2, "FollowUpStrategist", running=True, summary="追问决策中")
            elif node_name == "followup":
                await _mark(
                    db,
                    run_id,
                    2,
                    "FollowUpStrategist",
                    running=False,
                    summary=f"策略：{merged.get('followup_strategy')}",
                )
    return dict(merged)


async def _score_legacy(
    db: AsyncSession,
    run_id: str,
    initial: TurnState,
    *,
    followup_enabled: bool,
) -> dict[str, Any]:
    await _mark(db, run_id, 0, "AnswerAggregator", running=True, summary="汇总转写与语音特征")
    state = await _aggregator_node(initial)
    await _mark(db, run_id, 0, "AnswerAggregator", running=False, summary="语音特征已汇总")
    await _mark(db, run_id, 1, "MultimodalScorer", running=True, summary="语义评分中")
    state = await _scorer_node(state)
    await _mark(db, run_id, 1, "MultimodalScorer", running=False, summary="语义评分完成")
    await _mark(db, run_id, 2, "FollowUpStrategist", running=True, summary="追问决策中")
    state = await _followup_node(state, enabled=followup_enabled)
    await _mark(db, run_id, 2, "FollowUpStrategist", running=False, summary=f"策略：{state.get('followup_strategy')}")
    return dict(state)


# ---------------------------------------------------------------------------
# council 报告 + 闭环回流
# ---------------------------------------------------------------------------


async def _council_one(role: str, session: InterviewSession, turns: list[InterviewTurn], user_id: str) -> dict[str, Any]:
    data = await _chat_json(
        (
            f"你是{role}。只从自己的视角评议本场面试，不要重复其他角色。"
            "返回 JSON：{\"role\":\"\",\"view\":\"200字内评议\",\"score\":80,\"issues\":[\"\"]}"
        ),
        (
            f"岗位：{role_label(session.job_role)}\n场景：{session.scenario}\n"
            f"各轮：{[{'q': t.question, 'score': t.fused_score, 'fb': t.feedback[:80]} for t in turns]}"
        ),
        user_id=user_id,
        endpoint="interview_council",
        temperature=0.35,
        timeout=25.0,
    )
    return {
        "role": role,
        "view": str(data.get("view") or f"{role}认为整体中等，需补具体例证。"),
        "score": data.get("score"),
        "issues": list(data.get("issues") or []),
    }


async def build_interview_report(db: AsyncSession, session: InterviewSession, user: User | None = None) -> InterviewReport:
    turns = list(
        (await db.execute(select(InterviewTurn).where(InterviewTurn.session_id == session.id).order_by(InterviewTurn.turn_index.asc())))
        .scalars()
        .all()
    )
    dims = dimensions_for(session.scenario)
    dim_scores: dict[str, float] = {}
    issues: list[str] = []
    degraded: set[str] = set()
    if not any(t.visual_score is not None for t in turns):
        degraded.add("visual")
    for turn in turns:
        if turn.feedback:
            issues.append(turn.feedback[:80])
    if turns:
        avg = sum(float(t.fused_score or 0) for t in turns) / max(len(turns), 1)
        for key, _ in dims:
            dim_scores[key] = round(avg, 1)
        lang_key = "language_expression" if session.scenario == "job" else "expression_clarity"
        prosodies = [float(t.prosody_score) for t in turns if t.prosody_score is not None]
        if prosodies and lang_key in dim_scores:
            dim_scores[lang_key] = round(sum(prosodies) / len(prosodies), 1)

    roles = council_roles_for(session.scenario)
    run_id = f"iv-rep-{uuid4().hex[:10]}"
    plan = agent_trace.build_council_plan(roles)
    try:
        await agent_trace.start_agent_run(
            db,
            run_id=run_id,
            user=user,
            user_id=session.user_id,
            scene=INTERVIEW_SCENE,
            mode="council",
            topic=f"{role_label(session.job_role)} 总评",
            graph_plan=plan,
        )
        await agent_trace.ensure_steps(db, run_id, plan["steps"])
        for s in plan["steps"][:-1]:
            await agent_trace.mark_step_running(db, run_id, step_index=s["step_index"], agent_role=s["agent_role"], summary=f"{s['agent_role']} 评议中")
    except Exception as exc:  # noqa: BLE001
        logger.exception("report trace start: %s", exc)

    views = await asyncio.gather(*[_council_one(role, session, turns, session.user_id) for role in roles])
    council_views = {str(v.get("role")): v for v in views}

    try:
        for s in plan["steps"][:-1]:
            await agent_trace.mark_step_done(db, run_id, step_index=s["step_index"], summary="评议完成")
        last = plan["steps"][-1]
        await agent_trace.mark_step_running(db, run_id, step_index=last["step_index"], agent_role="CouncilSummarizer", summary="汇总中")
    except Exception:
        pass

    data = await _chat_json(
        (
            "你是面试评议汇总官，综合三方视角给出总评。"
            + rubric_prompt_block(session.scenario)
            + "返回 JSON：{\"summary\":\"\",\"dimensions\":{\"k\":80},\"key_issues\":[\"\"],\"suggestions\":[\"\"]}"
        ),
        (
            f"岗位：{role_label(session.job_role)}\n场景：{session.scenario}\n"
            f"视角：{list(council_views.values())}\n"
            f"各轮：{[{'q': t.question, 'score': t.fused_score, 'fb': t.feedback} for t in turns]}"
        ),
        user_id=session.user_id,
        endpoint="interview_report",
        temperature=0.3,
        timeout=30.0,
        shield=True,
    )
    if isinstance(data.get("dimensions"), dict):
        for key, _ in dims:
            if key in data["dimensions"]:
                try:
                    dim_scores[key] = float(data["dimensions"][key])
                except (TypeError, ValueError):
                    pass
    key_issues = list(data.get("key_issues") or issues)[:6]
    suggestions = list(data.get("suggestions") or ["用 STAR 结构回答项目题", "减少填充词，先给结论再展开"])[:6]
    summary = str(data.get("summary") or "本场面试已完成，可回看逐题点评。")
    overall = round(sum(dim_scores.values()) / max(len(dim_scores), 1), 1) if dim_scores else 0.0

    try:
        last = plan["steps"][-1]
        await agent_trace.mark_step_done(db, run_id, step_index=last["step_index"], summary="汇总完成")
        await agent_trace.finish_agent_run(db, run_id, status="completed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("report trace finish: %s", exc)

    existing = (await db.execute(select(InterviewReport).where(InterviewReport.session_id == session.id))).scalar_one_or_none()
    payload = dict(
        dimension_scores=dim_scores,
        key_issues=key_issues,
        suggestions=suggestions,
        resource_refs=[],
        council_views=council_views,
        degraded_modalities=sorted(degraded),
        summary=summary,
    )
    if existing:
        for k, v in payload.items():
            setattr(existing, k, v)
        report = existing
    else:
        report = InterviewReport(id=str(uuid4()), session_id=session.id, **payload)
        db.add(report)
    session.overall_score = overall
    session.dimension_scores = dim_scores
    session.status = "completed"
    from datetime import datetime, timezone

    session.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)
    try:
        from app.services.interview_closed_loop import apply_interview_closed_loop

        refs = await apply_interview_closed_loop(db, session, report, turns)
        if refs:
            report.resource_refs = refs
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("closed loop: %s", exc)
    return report

