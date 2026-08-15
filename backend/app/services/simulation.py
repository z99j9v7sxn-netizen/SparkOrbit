"""多智能体「影子镜像」推演工作流。

以 LangGraph 的编排思路组织 Teacher -> Mirror -> Evaluator -> PathPlanner 四个
智能体的协同预演：Teacher 出诊断题、Mirror 以学生数字孪生体身份试错作答、
Evaluator 评估并做错因分析、PathPlanner 生成个性化补救路径。

关键设计：
- 全程围绕真实传入的 `topic`（知识点）组织，杜绝"点操作系统却问计网"的张冠李戴。
- 优先调用 DeepSeek 大模型生成内容；无 Key 或失败时回退到与画像强相关的本地推理，
  保证演示闭环永不"开天窗"。
- 通过异步生成器逐条 yield 事件，前端以打字机流式呈现"智能体互相讨论"的过程。
"""
import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Literal, Optional, TypedDict

from app.schemas.student_profile import StudentProfileExtract
from app.services.rag import build_rag_context
from app.services.spark import extract_json, spark_available, spark_chat

AgentRole = Literal["Teacher", "Mirror", "Evaluator", "PathPlanner", "System"]


class SimulationEvent(TypedDict):
    role: AgentRole
    type: str
    content: str
    payload: Dict[str, Any]


# ---------------------------------------------------------------------------
# 运行注册表：POST /simulations/mirror 时登记本次推演参数（topic / 画像覆盖等），
# 供随后的 SSE 流 GET /simulations/{run_id}/stream 精准取用，
# 修复"前端选的主题传不到后端"的数据流断裂问题。
# ---------------------------------------------------------------------------
_RUNS: Dict[str, Dict[str, Any]] = {}


def register_run(run_id: str, params: Dict[str, Any]) -> None:
    _RUNS[run_id] = params


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    return _RUNS.get(run_id)


async def _emit(
    role: AgentRole,
    event_type: str,
    content: str,
    payload: Optional[Dict[str, Any]] = None,
    delay: float = 0.12,
) -> SimulationEvent:
    await asyncio.sleep(delay)
    return {"role": role, "type": event_type, "content": content, "payload": payload or {}}


def _profile_brief(p: StudentProfileExtract) -> str:
    return (
        f"- 专业背景：{p.major_background.value or '未知'}（成熟度 {p.major_background.score}）\n"
        f"- 前置知识：{p.prior_knowledge.value or '未知'}（成熟度 {p.prior_knowledge.score}）\n"
        f"- 认知风格：{p.cognitive_style.value or '未知'}（成熟度 {p.cognitive_style.score}）\n"
        f"- 易错倾向：{p.mistake_tendency.value or '未知'}（稳健度 {p.mistake_tendency.score}）\n"
        f"- 学习目标：{p.learning_goal.value or '未知'}（清晰度 {p.learning_goal.score}）\n"
        f"- 时间弹性：{p.time_flexibility.value or '未知'}（充裕度 {p.time_flexibility.score}）\n"
        f"- 资源模态偏好：{p.modality_preference.value or '未知'}（匹配度 {p.modality_preference.score}）\n"
        f"- 学习动机强度：{p.motivation_level.value or '未知'}（强度 {p.motivation_level.score}）"
    )


def build_mirror_system_prompt(profile: StudentProfileExtract, topic: str) -> str:
    return f"""你是 SparkOrbit 星轨学图中的 Mirror Agent（学生数字孪生体）。
你要严格按照下面的学生画像，模拟"这名真实学生"在学习「{topic}」时的作答与思维，
包括他可能的知识盲点与惯性错误。切勿表现得比画像更强。

学生画像：
{_profile_brief(profile)}

要求：
- 若前置知识/易错倾向分数偏低，请在作答中自然暴露对应的误解或疏漏。
- 用第一人称、口语化地写出你的解题思路（可以是错的），控制在 120 字内。""".strip()


# ---------------------------------------------------------------------------
# 三个 Agent 的 LLM 调用（各自带本地兜底），全部围绕 topic 展开。
# ---------------------------------------------------------------------------
async def _teacher_question(topic: str, profile: StudentProfileExtract) -> Dict[str, Any]:
    system = (
        "你是 SparkOrbit 的 Teacher Agent（诊断出题官）。"
        "请针对给定知识点设计一道能暴露学生核心理解误区的情境诊断题。"
        "严格返回 JSON：{\"question\":\"题干（含具体情境）\",\"key_point\":\"该题真正考察的核心\","
        "\"common_trap\":\"学生最常见的错误陷阱\"}，不要输出多余文字。"
    )
    user = f"知识点：{topic}\n学生学习目标：{profile.learning_goal.value or '掌握该知识点'}\n请出题。"
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.6,
    )
    data = extract_json(raw) if raw else None
    if not data or "question" not in data:
        data = {
            "question": f"围绕「{topic}」，请判断在给定情境下应采用的核心方法，并说明理由。",
            "key_point": f"{topic} 的核心概念与典型适用场景",
            "common_trap": "混淆相邻概念、忽略边界条件或复杂度权衡",
        }
    return data


async def _mirror_answer(profile: StudentProfileExtract, topic: str, question: str) -> Dict[str, Any]:
    weak = profile.prior_knowledge.score < 60 or profile.mistake_tendency.score < 55
    system = build_mirror_system_prompt(profile, topic)
    user = f"题目：{question}\n请以这名学生的真实水平作答，并写出思路。"
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.85,
    )
    if raw:
        return {"answer": raw.strip(), "likely_wrong": weak}
    # 兜底：依据画像给出"可能出错"或"基本正确"的模拟作答
    if weak:
        answer = (
            f"关于「{topic}」，我大概记得个概念……我可能会直接套用最先想到的方法，"
            "但对边界条件和为什么这么做其实说不太清楚。"
        )
    else:
        answer = (
            f"针对「{topic}」，我会先厘清核心定义，再结合情境选择合适方法，"
            "并注意验证边界条件与复杂度。"
        )
    return {"answer": answer, "likely_wrong": weak}


async def _evaluator_judge(
    profile: StudentProfileExtract, topic: str, question: str, mirror_answer: str
) -> Dict[str, Any]:
    rag_ctx = build_rag_context(topic)
    system = (
        "你是 SparkOrbit 的 Evaluator Agent（严谨的评估与错因分析官）。"
        "请评估学生数字孪生体的作答是否掌握了知识点，并做错因归因。"
        f"{rag_ctx}"
        "严格返回 JSON：{\"passed\":true/false,\"score\":0-100,"
        "\"diagnosis\":\"一句话结论\",\"root_cause\":\"若未通过，指出根本原因；通过则填 掌握良好\"}。"
    )
    user = (
        f"知识点：{topic}\n题目：{question}\n"
        f"学生画像易错倾向：{profile.mistake_tendency.value or '未知'}\n"
        f"学生数字孪生体作答：{mirror_answer}\n请评估。"
    )
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
    )
    data = extract_json(raw) if raw else None
    if not data or "passed" not in data:
        weak = profile.prior_knowledge.score < 60 or profile.mistake_tendency.score < 55
        trap = profile.mistake_tendency.value or "边界条件与概念辨析"
        data = {
            "passed": not weak,
            "score": max(35, min(95, profile.prior_knowledge.score)),
            "diagnosis": "掌握良好，可进阶" if not weak else f"未稳定掌握，受「{trap}」影响",
            "root_cause": "掌握良好" if not weak else f"前置知识不牢 + {trap}，导致方法选择与边界处理失误",
        }
    return data


async def _path_planner(topic: str, root_cause: str, profile: StudentProfileExtract) -> List[str]:
    system = (
        "你是 SparkOrbit 的 PathPlanner Agent（个性化学习路径规划师）。"
        "请根据错因给出 3-4 步、可立即执行的补救学习路径。"
        "严格返回 JSON：{\"steps\":[\"第一步...\",\"第二步...\"]}。"
    )
    time_hint = profile.time_flexibility.value or "时间较紧"
    user = f"知识点：{topic}\n错因：{root_cause}\n学生时间弹性：{time_hint}\n请规划路径。"
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.6,
    )
    data = extract_json(raw) if raw else None
    steps = data.get("steps") if isinstance(data, dict) else None
    if not steps or not isinstance(steps, list):
        steps = [
            f"用一个生活化案例重新理解「{topic}」的核心定义",
            "对照该知识点最常见的错误陷阱做辨析笔记",
            "完成 3 道由易到难的针对性练习并即时复盘",
            "回到星图重新挑战该行星，验证是否已可稳定点亮",
        ]
    return [str(s) for s in steps][:5]


def _langgraph_available() -> bool:
    try:
        from langgraph.graph import END, StateGraph  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


async def run_mirror_simulation(
    profile: StudentProfileExtract,
    topic: str = "数据结构与算法基础",
    *,
    run_id: str = "",
    db: Any = None,
) -> AsyncGenerator[SimulationEvent, None]:
    """Teacher -> Mirror -> Evaluator -> PathPlanner 的 handoff 流式协同预演。

    优先用 LangGraph StateGraph 真正 astream；不可用时回退手写流水线。
    """
    if _langgraph_available():
        async for event in _run_mirror_via_langgraph(profile, topic, run_id=run_id, db=db):
            yield event
        return

    async for event in _run_mirror_legacy(profile, topic, run_id=run_id, db=db):
        yield event


async def _trace_handoff_start(db: Any, run_id: str, topic: str, user_id: str = "", user_name: str = "") -> None:
    if not db or not run_id:
        return
    try:
        from sqlalchemy import select

        from app.models.agent_trace import AgentRun, AgentStep
        from app.services import agent_trace

        plan = agent_trace.build_handoff_plan(["Teacher", "Mirror", "Evaluator", "PathPlanner"])
        existing = await db.get(AgentRun, run_id)
        if existing is None:
            await agent_trace.start_agent_run(
                db,
                run_id=run_id,
                user_id=user_id,
                user_name=user_name,
                scene="simulation",
                mode="handoff",
                topic=topic,
                graph_plan=plan,
            )
        else:
            existing.mode = "handoff"
            existing.scene = existing.scene or "simulation"
            existing.graph_plan = plan
            existing.topic = topic or existing.topic
            await db.commit()
        has_steps = (
            await db.execute(select(AgentStep.id).where(AgentStep.run_id == run_id).limit(1))
        ).scalar_one_or_none()
        if has_steps is None:
            await agent_trace.ensure_steps(db, run_id, plan["steps"])
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("simulation handoff trace ensure failed: %s", exc)


async def _trace_step(db: Any, run_id: str, step_index: int, agent_role: str, *, done: bool = False, summary: str = "", ok: bool = True) -> None:
    if not db or not run_id:
        return
    try:
        from app.services import agent_trace

        if done:
            await agent_trace.mark_step_done(db, run_id, step_index=step_index, summary=summary, ok=ok)
        else:
            await agent_trace.mark_step_running(db, run_id, step_index=step_index, agent_role=agent_role, summary=summary)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "simulation trace step failed run=%s step=%s: %s", run_id, step_index, exc
        )


async def _finish_trace(db: Any, run_id: str, *, status: str = "completed", error_message: str = "") -> None:
    if not db or not run_id:
        return
    try:
        from app.services import agent_trace

        await agent_trace.finish_agent_run(db, run_id, status=status, error_message=error_message)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "simulation finish_agent_run failed run=%s status=%s: %s", run_id, status, exc
        )
        # 二次尝试标 failed，避免管理端永久 running
        try:
            from app.services import agent_trace

            await agent_trace.finish_agent_run(
                db,
                run_id,
                status="failed",
                error_message=(error_message or str(exc))[:240],
            )
        except Exception as exc2:  # noqa: BLE001
            logging.getLogger(__name__).exception(
                "simulation finish_agent_run fallback failed run=%s: %s", run_id, exc2
            )


async def _run_mirror_via_langgraph(
    profile: StudentProfileExtract,
    topic: str,
    *,
    run_id: str = "",
    db: Any = None,
) -> AsyncGenerator[SimulationEvent, None]:
    from typing import TypedDict

    from langgraph.graph import END, StateGraph

    class SimState(TypedDict, total=False):
        topic: str
        question: Dict[str, Any]
        mirror: Dict[str, Any]
        evaluation: Dict[str, Any]
        path_steps: List[str]

    engine = "LangGraph + DeepSeek" if spark_available() else "LangGraph + 本地兜底"
    yield await _emit(
        "System",
        "boot",
        f"影子镜像推演已启动 · 引擎：{engine} · 模式：handoff · 目标知识点：{topic}",
        {"topic": topic, "orchestrator": "langgraph", "mode": "handoff", "run_id": run_id},
    )
    await _trace_handoff_start(db, run_id, topic)

    async def teacher_node(state: SimState) -> SimState:
        q = await _teacher_question(state["topic"], profile)
        return {**state, "question": q}

    async def mirror_node(state: SimState) -> SimState:
        m = await _mirror_answer(profile, state["topic"], state["question"]["question"])
        return {**state, "mirror": m}

    async def evaluator_node(state: SimState) -> SimState:
        ev = await _evaluator_judge(
            profile, state["topic"], state["question"]["question"], state["mirror"]["answer"]
        )
        return {**state, "evaluation": ev}

    async def planner_node(state: SimState) -> SimState:
        if bool(state.get("evaluation", {}).get("passed")):
            return {**state, "path_steps": []}
        steps = await _path_planner(
            state["topic"], str(state.get("evaluation", {}).get("root_cause") or ""), profile
        )
        return {**state, "path_steps": steps}

    graph = StateGraph(SimState)
    graph.add_node("teacher", teacher_node)
    graph.add_node("mirror", mirror_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("planner", planner_node)
    graph.set_entry_point("teacher")
    graph.add_edge("teacher", "mirror")
    graph.add_edge("mirror", "evaluator")
    graph.add_edge("evaluator", "planner")
    graph.add_edge("planner", END)
    app = graph.compile()

    role_by_node = {
        "teacher": ("Teacher", 0),
        "mirror": ("Mirror", 1),
        "evaluator": ("Evaluator", 2),
        "planner": ("PathPlanner", 3),
    }

    yield await _emit("Teacher", "thinking", f"Teacher 正在围绕「{topic}」构造一道能暴露误区的诊断题…")
    await _trace_step(db, run_id, 0, "Teacher", summary="Teacher 出题中")

    merged: SimState = {"topic": topic}
    async for update in app.astream(merged, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node_name, patch in update.items():
            if isinstance(patch, dict):
                merged = {**merged, **patch}
            role, step_index = role_by_node.get(node_name, ("System", 0))
            if node_name == "teacher":
                q = merged.get("question") or {}
                yield await _emit(
                    "Teacher",
                    "question",
                    q.get("question", ""),
                    {"key_point": q.get("key_point"), "trap": q.get("common_trap"), "step_index": 0},
                )
                yield await _emit(
                    "Teacher",
                    "note",
                    f"考察核心：{q.get('key_point', '')} ｜ 预设陷阱：{q.get('common_trap', '')}",
                )
                await _trace_step(db, run_id, 0, "Teacher", done=True, summary="Teacher 已出题")
                yield await _emit("Mirror", "system_prompt", "Mirror 已加载学生六维画像，进入数字孪生体人格，开始试错…")
                await _trace_step(db, run_id, 1, "Mirror", summary="Mirror 试错中")
            elif node_name == "mirror":
                m = merged.get("mirror") or {}
                yield await _emit(
                    "Mirror",
                    "answer",
                    m.get("answer", ""),
                    {"likely_wrong": m.get("likely_wrong"), "step_index": 1},
                )
                await _trace_step(db, run_id, 1, "Mirror", done=True, summary="Mirror 已作答")
                yield await _emit("Evaluator", "thinking", "Evaluator 正在比对孪生体作答与知识点要点，进行错因归因…")
                await _trace_step(db, run_id, 2, "Evaluator", summary="Evaluator 评判中")
            elif node_name == "evaluator":
                ev = merged.get("evaluation") or {}
                passed = bool(ev.get("passed"))
                yield await _emit(
                    "Evaluator",
                    "evaluation",
                    f"{'✅ 判定通过' if passed else '⚠️ 判定未通过'}（得分 {ev.get('score', '-')}）：{ev.get('diagnosis', '')}",
                    {"passed": passed, "score": ev.get("score"), "step_index": 2},
                )
                await _trace_step(db, run_id, 2, "Evaluator", done=True, summary="Evaluator 已判定")
                await _trace_step(db, run_id, 3, "PathPlanner", summary="PathPlanner 规划中")
            elif node_name == "planner":
                ev = merged.get("evaluation") or {}
                passed = bool(ev.get("passed"))
                steps = merged.get("path_steps") or []
                if passed:
                    yield await _emit(
                        "PathPlanner",
                        "planning",
                        "孪生体已能稳定掌握该知识点，PathPlanner 建议直接进阶更高难度行星。",
                        {"advance": True, "step_index": 3},
                    )
                    await _trace_step(db, run_id, 3, "PathPlanner", done=True, summary="建议进阶")
                    if db and run_id:
                        await _finish_trace(db, run_id, status="completed")
                    yield await _emit(
                        "System",
                        "done",
                        "推演完成：预测该学生可安全点亮此行星。",
                        {"passed": True, "mode": "handoff"},
                    )
                    return

                yield await _emit(
                    "Evaluator",
                    "root_cause",
                    f"根本原因：{ev.get('root_cause', '')}",
                    {"root_cause": ev.get("root_cause")},
                )
                yield await _emit("PathPlanner", "planning", "PathPlanner 正在生成个性化补救路径…")
                for i, step in enumerate(steps, 1):
                    yield await _emit(
                        "PathPlanner",
                        "step",
                        f"步骤 {i}：{step}",
                        {"index": i, "total": len(steps)},
                    )
                await _trace_step(db, run_id, 3, "PathPlanner", done=True, summary=f"补救路径 {len(steps)} 步")
                if db and run_id:
                    await _finish_trace(db, run_id, status="completed")
                yield await _emit(
                    "System",
                    "done",
                    "推演完成：已输出补救路径，建议学生按步骤练习后再挑战点亮。",
                    {"passed": False, "steps": steps, "mode": "handoff"},
                )


async def _run_mirror_legacy(
    profile: StudentProfileExtract,
    topic: str = "数据结构与算法基础",
    *,
    run_id: str = "",
    db: Any = None,
) -> AsyncGenerator[SimulationEvent, None]:
    """手写 handoff 流水线回退（仍写 AgentStep）。"""

    engine = "DeepSeek 大模型" if spark_available() else "本地推理引擎（离线兜底）"
    yield await _emit(
        "System",
        "boot",
        f"影子镜像推演已启动 · 引擎：{engine} · 模式：handoff · 目标知识点：{topic}",
        {"topic": topic, "mode": "handoff", "run_id": run_id},
    )
    await _trace_handoff_start(db, run_id, topic)

    yield await _emit("Teacher", "thinking", f"Teacher 正在围绕「{topic}」构造一道能暴露误区的诊断题…")
    await _trace_step(db, run_id, 0, "Teacher", summary="Teacher 出题中")
    q = await _teacher_question(topic, profile)
    yield await _emit("Teacher", "question", q["question"], {"key_point": q.get("key_point"), "trap": q.get("common_trap")})
    yield await _emit("Teacher", "note", f"考察核心：{q.get('key_point','')} ｜ 预设陷阱：{q.get('common_trap','')}")
    await _trace_step(db, run_id, 0, "Teacher", done=True, summary="Teacher 已出题")

    yield await _emit("Mirror", "system_prompt", "Mirror 已加载学生六维画像，进入数字孪生体人格，开始试错…")
    await _trace_step(db, run_id, 1, "Mirror", summary="Mirror 试错中")
    m = await _mirror_answer(profile, topic, q["question"])
    yield await _emit("Mirror", "answer", m["answer"], {"likely_wrong": m["likely_wrong"]})
    await _trace_step(db, run_id, 1, "Mirror", done=True, summary="Mirror 已作答")

    yield await _emit("Evaluator", "thinking", "Evaluator 正在比对孪生体作答与知识点要点，进行错因归因…")
    await _trace_step(db, run_id, 2, "Evaluator", summary="Evaluator 评判中")
    ev = await _evaluator_judge(profile, topic, q["question"], m["answer"])
    passed = bool(ev.get("passed"))
    yield await _emit(
        "Evaluator",
        "evaluation",
        f"{'✅ 判定通过' if passed else '⚠️ 判定未通过'}（得分 {ev.get('score','-')}）：{ev.get('diagnosis','')}",
        {"passed": passed, "score": ev.get("score")},
    )
    await _trace_step(db, run_id, 2, "Evaluator", done=True, summary="Evaluator 已判定")

    await _trace_step(db, run_id, 3, "PathPlanner", summary="PathPlanner 规划中")
    if passed:
        yield await _emit(
            "PathPlanner",
            "planning",
            "孪生体已能稳定掌握该知识点，PathPlanner 建议直接进阶更高难度行星。",
            {"advance": True},
        )
        await _trace_step(db, run_id, 3, "PathPlanner", done=True, summary="建议进阶")
        if db and run_id:
            await _finish_trace(db, run_id, status="completed")
        yield await _emit("System", "done", "推演完成：预测该学生可安全点亮此行星。", {"passed": True, "mode": "handoff"})
        return

    root_cause = str(ev.get("root_cause", ""))
    yield await _emit("Evaluator", "root_cause", f"根本原因：{root_cause}", {"root_cause": root_cause})
    yield await _emit("PathPlanner", "planning", "PathPlanner 已被触发，正在生成个性化补救路径…")
    steps = await _path_planner(topic, root_cause, profile)
    path_text = "；".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    yield await _emit("PathPlanner", "learning_path", path_text, {"steps": steps, "reason": root_cause})
    await _trace_step(db, run_id, 3, "PathPlanner", done=True, summary=f"补救路径 {len(steps)} 步")
    if db and run_id:
        await _finish_trace(db, run_id, status="completed")
    yield await _emit("System", "done", "推演完成：已提前锁定风险并生成补救路径。", {"passed": False, "mode": "handoff"})


STRATEGY_PROFILES = {
    "aggressive": {"label": "激进型", "overrides": {"time_flexibility": 90, "mistake_tendency": 40}},
    "balanced": {"label": "均衡型", "overrides": {}},
    "conservative": {"label": "保守型", "overrides": {"time_flexibility": 30, "prior_knowledge": 85}},
}


def _apply_overrides(profile: StudentProfileExtract, overrides: Dict[str, int]) -> StudentProfileExtract:
    import copy

    p = copy.deepcopy(profile)
    for key, score in overrides.items():
        dim = getattr(p, key, None)
        if dim is not None:
            dim.score = max(0, min(100, int(score)))
    return p


async def run_multiverse_simulation(
    profile: StudentProfileExtract,
    topic: str = "数据结构与算法基础",
    *,
    run_id: str = "",
    db: Any = None,
) -> AsyncGenerator[SimulationEvent, None]:
    """多重平行宇宙：council 模式——三策略并行预演后汇总评议。"""
    roles = [cfg["label"] for cfg in STRATEGY_PROFILES.values()]
    if db and run_id:
        try:
            from sqlalchemy import select

            from app.models.agent_trace import AgentRun, AgentStep
            from app.services import agent_trace

            plan = agent_trace.build_council_plan(roles)
            existing = await db.get(AgentRun, run_id)
            if existing is None:
                await agent_trace.start_agent_run(
                    db,
                    run_id=run_id,
                    scene="multiverse",
                    mode="council",
                    topic=topic,
                    graph_plan=plan,
                )
            else:
                existing.mode = "council"
                existing.scene = "multiverse"
                existing.graph_plan = plan
                existing.topic = topic or existing.topic
                await db.commit()
            has_steps = (
                await db.execute(select(AgentStep.id).where(AgentStep.run_id == run_id).limit(1))
            ).scalar_one_or_none()
            if has_steps is None:
                await agent_trace.ensure_steps(db, run_id, plan["steps"])
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("council trace ensure failed: %s", exc)

    yield await _emit(
        "System",
        "boot",
        f"平行宇宙推演启动 · 模式：council · 目标：{topic} · 3 策略并行评议",
        {"topic": topic, "multiverse": True, "mode": "council", "run_id": run_id},
    )

    async def _one_strategy(strategy_key: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
        label = cfg["label"]
        sim_profile = _apply_overrides(profile, cfg["overrides"])
        q = await _teacher_question(topic, sim_profile)
        m = await _mirror_answer(sim_profile, topic, q["question"])
        ev = await _evaluator_judge(sim_profile, topic, q["question"], m["answer"])
        passed = bool(ev.get("passed"))
        steps: List[str] = []
        if not passed:
            steps = await _path_planner(topic, str(ev.get("root_cause", "")), sim_profile)
        return {
            "strategy": strategy_key,
            "label": label,
            "passed": passed,
            "score": ev.get("score", 0),
            "diagnosis": ev.get("diagnosis", ""),
            "steps": steps,
        }

    for i, (strategy_key, cfg) in enumerate(STRATEGY_PROFILES.items()):
        await _trace_step(db, run_id, i, cfg["label"], summary=f"{cfg['label']} 宇宙推演中")

    gathered = await asyncio.gather(
        *[_one_strategy(k, c) for k, c in STRATEGY_PROFILES.items()],
        return_exceptions=True,
    )
    results: List[Dict[str, Any]] = []
    for i, item in enumerate(gathered):
        label = list(STRATEGY_PROFILES.values())[i]["label"]
        if isinstance(item, Exception):
            await _trace_step(db, run_id, i, label, done=True, summary=str(item), ok=False)
            continue
        results.append(item)
        await _trace_step(db, run_id, i, label, done=True, summary=f"{label} 已完成")
        yield await _emit(
            "PathPlanner",
            "multiverse_result",
            f"【{item['label']}】{'通过' if item['passed'] else '未通过'}（{item.get('score', '-')}分）：{item.get('diagnosis', '')}",
            item,
        )

    await _trace_step(db, run_id, len(roles), "CouncilSummarizer", summary="汇总评议中")
    best = max(results, key=lambda r: (r["passed"], r.get("score", 0))) if results else {
        "strategy": "balanced",
        "label": "均衡型",
        "passed": False,
        "steps": [],
    }
    rec = (
        f"推荐采用「{best['label']}」策略："
        + ("可直接进阶。" if best.get("passed") else f"建议路径：{'；'.join((best.get('steps') or [])[:3])}")
    )
    yield await _emit(
        "System",
        "recommendation",
        rec,
        {"best_strategy": best.get("strategy"), "results": results, "mode": "council"},
    )
    await _trace_step(db, run_id, len(roles), "CouncilSummarizer", done=True, summary=rec[:200])
    if db and run_id:
        await _finish_trace(db, run_id, status="completed")
    yield await _emit(
        "System",
        "done",
        "平行宇宙推演完成。",
        {"multiverse": True, "best": best.get("strategy"), "mode": "council"},
    )


def format_sse(event: SimulationEvent) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
