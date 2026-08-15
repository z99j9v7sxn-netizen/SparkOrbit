"""伴学 Supervisor：意图识别 → 显式工具调度 → AgentStep 落库。"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.intent import classify_companion_intent
from app.agents.tools.runtime import (
    tool_generate_learning_path,
    tool_open_feynman,
    tool_start_resource_run,
)
from app.models.user import User
from app.schemas.galaxy import CompanionChatRequest, CompanionChatResponse
from app.services import agent_trace
from app.services.companion import companion_chat
from app.services.llm import llm_available

logger = logging.getLogger(__name__)


async def run_companion_supervisor(
    req: CompanionChatRequest,
    *,
    session: AsyncSession,
    user: User,
) -> CompanionChatResponse:
    intent = classify_companion_intent(req.message, mode_hint=req.mode)
    run_id = f"sup-{uuid.uuid4().hex[:12]}"
    degraded = not llm_available()

    tasks = [
        {"type": "intent", "priority": 1, "reason": f"识别意图={intent}", "agent_role": "IntentClassifier"},
    ]
    if intent == "path":
        tasks.append({"type": "path", "priority": 2, "reason": "生成/刷新学习路径", "agent_role": "PathPlanner"})
    elif intent == "sprint":
        tasks.append({"type": "sprint", "priority": 2, "reason": "生成考前冲刺计划", "agent_role": "SprintPlanner"})
    elif intent == "closed_loop":
        tasks.append({"type": "closed_loop", "priority": 2, "reason": "评估→路径→资源闭环", "agent_role": "ClosedLoop"})
    elif intent == "deck":
        tasks.append({"type": "deck", "priority": 2, "reason": "启动课件/闪卡资源生成", "agent_role": "DeckAgent"})
    elif intent == "quiz":
        tasks.append({"type": "quiz", "priority": 2, "reason": "启动题库资源生成", "agent_role": "QuizAgent"})
    elif intent == "resource":
        tasks.append({"type": "resource", "priority": 2, "reason": "启动多类型资源包", "agent_role": "ResourceCoordinator"})
    else:
        tasks.append({"type": "chat", "priority": 2, "reason": "对话辅导/陪伴", "agent_role": "TutorAgent"})

    tasks.append({"type": "next_actions", "priority": 3, "reason": "汇总下一步动作", "agent_role": "ActionComposer"})
    plan = agent_trace.build_supervisor_plan(tasks)

    try:
        await agent_trace.start_agent_run(
            session,
            run_id=run_id,
            user=user,
            scene="companion",
            mode="supervisor",
            topic=req.planet_slug or intent,
            graph_plan=plan,
        )
        await agent_trace.ensure_steps(session, run_id, plan["steps"])
        await agent_trace.mark_step_running(
            session, run_id, step_index=0, agent_role="Supervisor", summary=f"intent={intent}"
        )
        await agent_trace.mark_step_done(
            session,
            run_id,
            step_index=0,
            summary=f"intent={intent}",
            payload={"degraded": degraded},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("supervisor trace start failed: %s", exc)

    worker_index = 2
    try:
        await agent_trace.mark_step_running(
            session,
            run_id,
            step_index=1,
            agent_role="IntentClassifier",
            summary=intent,
        )
        await agent_trace.mark_step_done(session, run_id, step_index=1, summary=intent)
        await agent_trace.mark_step_running(
            session,
            run_id,
            step_index=worker_index,
            agent_role=str(tasks[1].get("agent_role") or "TutorAgent"),
            summary=str(tasks[1].get("reason") or ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("supervisor intent/worker mark failed: %s", exc)

    chat_req = CompanionChatRequest(
        message=req.message,
        mode=_chat_mode_for_intent(intent, req.mode),
        planet_slug=req.planet_slug,
        socratic=req.socratic,
        supervise=False,
    )
    base = await companion_chat(chat_req, session=session, user_id=user.id)

    path_id: Optional[str] = None
    resource_run_id: Optional[str] = None
    next_actions: list[dict[str, Any]] = []
    tool_payload: dict[str, Any] = {"intent": intent, "degraded": degraded}

    if intent == "path":
        tool_res = await tool_generate_learning_path(session, user, goal=req.message[:80] or "伴学推荐")
        next_actions.append(tool_res)
        tool_payload["tool"] = tool_res
        if tool_res.get("status") == "ok":
            path_id = str(tool_res.get("path_id") or "")
            base.reply = (base.reply or "") + f"\n\n已为你生成学习路径「{tool_res.get('title')}」，可在学习面板打开。"
        else:
            base.reply = (base.reply or "") + "\n\n学习路径生成失败，请稍后重试。"
    elif intent == "sprint":
        from app.services.learning_path import generate_sprint_path

        exam_name, exam_date = _extract_sprint_target(req.message)
        try:
            sprint = await generate_sprint_path(session, user, exam_name=exam_name, exam_date=exam_date)
            path_id = sprint.id
            tool_payload["tool"] = {
                "tool_name": "generate_sprint_path",
                "status": "ok",
                "path_id": sprint.id,
                "exam_date": exam_date,
            }
            next_actions.append(
                {
                    "type": "open_panel",
                    "panel": "path",
                    "label": f"查看冲刺计划（{exam_date} 考试）",
                    "path_id": sprint.id,
                    "status": "ok",
                    "tool_name": "generate_sprint_path",
                }
            )
            base.reply = (
                (base.reply or "")
                + f"\n\n已生成「{sprint.title}」：{len(sprint.steps)} 天倒排任务，考试日 {exam_date}。在学习路径面板的「冲刺」标签查看每日清单。"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("supervisor sprint failed: %s", exc)
            tool_payload["tool"] = {"tool_name": "generate_sprint_path", "status": "error", "error": str(exc)[:200]}
            base.reply = (base.reply or "") + f"\n\n冲刺计划生成失败：{exc}"
    elif intent == "closed_loop":
        from app.services.learning_loop import run_eval_path_resource_loop

        try:
            loop_res = await run_eval_path_resource_loop(session, user, auto_generate=True, top_k=2)
            tool_payload["tool"] = {"tool_name": "closed_loop", "status": "ok", **{k: loop_res.get(k) for k in ("run_id", "message", "targets")}}
            next_actions.append(
                {
                    "type": "open_panel",
                    "panel": "path",
                    "label": "查看重排后的学习路径",
                    "run_id": loop_res.get("run_id"),
                }
            )
            next_actions.append(
                {
                    "type": "open_panel",
                    "panel": "resources",
                    "label": "查看自动生成的资源",
                }
            )
            base.reply = (base.reply or "") + f"\n\n{loop_res.get('message') or '闭环已执行'}（run={loop_res.get('run_id')}）"
            path_obj = loop_res.get("path") or {}
            if isinstance(path_obj, dict):
                path_id = str(path_obj.get("id") or "")
        except Exception as exc:  # noqa: BLE001
            logger.exception("supervisor closed_loop failed: %s", exc)
            tool_payload["tool"] = {"tool_name": "closed_loop", "status": "error", "error": str(exc)}
            base.reply = (base.reply or "") + f"\n\n闭环执行失败：{exc}"
    elif intent in ("deck", "quiz", "resource"):
        kinds = _kinds_for_intent(intent)
        tool_res = tool_start_resource_run(
            user_id=user.id,
            planet_slug=req.planet_slug or "",
            kinds=kinds,
            extra=req.message[:200],
        )
        next_actions.append(tool_res)
        tool_payload["tool"] = tool_res
        if tool_res.get("status") == "ok":
            resource_run_id = str(tool_res.get("run_id") or "")
            base.reply = (
                (base.reply or "")
                + f"\n\n已启动资源生成任务（{', '.join(kinds)}），点击下方按钮进入资源工坊查看流式进度。"
            )
        elif tool_res.get("type") == "need_planet":
            base.reply = (base.reply or "") + "\n\n要生成资料的话，请先指定知识点（行星）。"
        else:
            base.reply = (base.reply or "") + "\n\n资源任务登记失败，请稍后重试。"
    elif intent == "feynman":
        next_actions.append(tool_open_feynman(planet_slug=req.planet_slug or ""))
        next_actions.extend(_default_next_actions(intent, req.planet_slug or ""))
    else:
        next_actions.extend(_default_next_actions(intent, req.planet_slug or ""))

    if degraded:
        base.reply = (base.reply or "") + "\n\n（当前为演示降级模式：未检测到可用 LLM Key，回复可能为模板。）"

    tool_payload["path_id"] = path_id
    tool_payload["resource_run_id"] = resource_run_id

    try:
        await agent_trace.mark_step_done(
            session,
            run_id,
            step_index=worker_index,
            summary=_worker_summary(tool_payload),
            payload=tool_payload,
            ok=not (tool_payload.get("tool") or {}).get("status") == "error",
        )
        await agent_trace.mark_step_running(
            session, run_id, step_index=3, agent_role="ActionComposer", summary="汇总 next_actions"
        )
        await agent_trace.mark_step_done(
            session,
            run_id,
            step_index=3,
            summary=f"{len(next_actions)} actions",
            payload={"next_actions": next_actions, "degraded": degraded},
        )
        await agent_trace.finish_agent_run(session, run_id, status="completed")
    except Exception as exc:  # noqa: BLE001
        logger.exception("supervisor finish failed: %s", exc)

    return CompanionChatResponse(
        reply=base.reply,
        mode=base.mode,
        fragment_progress=base.fragment_progress,
        socratic=base.socratic,
        sources=base.sources,
        explain_score=base.explain_score,
        explain_rubric=base.explain_rubric,
        run_id=run_id,
        intent=intent,
        next_actions=next_actions,
        path_id=path_id,
        resource_run_id=resource_run_id,
    )


def _extract_sprint_target(message: str) -> tuple[str, str]:
    """从消息中提取考试名与日期；无法确定时默认 14 天后。"""
    import re
    from datetime import date, timedelta

    text = (message or "").strip()
    today = date.today()

    exam_name = ""
    for kw in ("四级", "六级", "雅思", "托福", "期末", "期中", "考研", "高考", "中考", "粤语"):
        if kw in text:
            exam_name = kw
            break

    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if m:
        try:
            target = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if target > today:
                return exam_name, target.isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", text)
    if m:
        try:
            target = date(today.year, int(m.group(1)), int(m.group(2)))
            if target <= today:
                target = date(today.year + 1, int(m.group(1)), int(m.group(2)))
            return exam_name, target.isoformat()
        except ValueError:
            pass
    m = re.search(r"还有\s*(\d{1,3})\s*天|(\d{1,3})\s*天后", text)
    if m:
        days = int(m.group(1) or m.group(2))
        if days >= 1:
            return exam_name, (today + timedelta(days=days)).isoformat()
    return exam_name, (today + timedelta(days=14)).isoformat()


def _worker_summary(payload: dict[str, Any]) -> str:
    tool = payload.get("tool") or {}
    if tool.get("tool_name"):
        return f"tool={tool.get('tool_name')} status={tool.get('status')}"
    return "子能力完成"


def _chat_mode_for_intent(intent: str, fallback: str) -> str:
    if intent == "feynman":
        return "feynman"
    if intent == "companion":
        return "companion"
    if fallback in ("companion", "tutor", "feynman"):
        return fallback
    return "tutor"


def _kinds_for_intent(intent: str) -> list[str]:
    if intent == "deck":
        return ["deck", "quiz"]
    if intent == "quiz":
        return ["quiz"]
    # 路演默认避开不稳定 media
    return ["doc", "mindmap", "quiz"]


def _default_next_actions(intent: str, planet_slug: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "type": "generate_path",
            "label": "生成个性化学习路径",
            "status": "pending",
            "tool_name": "generate_learning_path",
        },
    ]
    if planet_slug:
        actions.append(
            {
                "type": "generate_deck",
                "label": "生成课件/闪卡",
                "planet_slug": planet_slug,
                "kinds": ["deck"],
                "status": "pending",
                "tool_name": "start_resource_run",
            }
        )
        actions.append(
            {
                "type": "generate_quiz",
                "label": "生成练习题",
                "planet_slug": planet_slug,
                "kinds": ["quiz"],
                "status": "pending",
                "tool_name": "start_resource_run",
            }
        )
        actions.append(tool_open_feynman(planet_slug=planet_slug))
    if intent == "companion":
        actions.insert(0, {"type": "rest", "label": "先休息 5 分钟再学", "status": "ok"})
    return actions
