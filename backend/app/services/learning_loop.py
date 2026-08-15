"""评估 → 路径重排 → TopK 弱项资源生成 的可观测闭环。"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import agent_trace
from app.services.evaluation import build_evaluation_report, evaluation_suggestions_for_path
from app.services.learning_path import generate_learning_path
from app.services.resource_agents import run_resource_generation

logger = logging.getLogger(__name__)

DEFAULT_KINDS = ["doc", "quiz"]


def build_closed_loop_plan(*, top_k: int, kinds: list[str]) -> dict[str, Any]:
    steps = [
        {
            "step_index": 0,
            "agent_role": "Evaluator",
            "status": "pending",
            "parallel_group": 0,
            "summary": "生成成长评估",
            "payload": {"phase": "evaluate"},
        },
        {
            "step_index": 1,
            "agent_role": "PathPlanner",
            "status": "pending",
            "parallel_group": 1,
            "summary": "按评估建议重排路径",
            "payload": {"phase": "rerank_path"},
        },
        {
            "step_index": 2,
            "agent_role": "ResourceCoordinator",
            "status": "pending",
            "parallel_group": 2,
            "summary": f"为 Top{top_k} 弱项生成资源 ({','.join(kinds)})",
            "payload": {"phase": "spawn_resources", "top_k": top_k, "kinds": kinds},
        },
        {
            "step_index": 3,
            "agent_role": "Notifier",
            "status": "pending",
            "parallel_group": 3,
            "summary": "汇总闭环结果",
            "payload": {"phase": "notify"},
        },
    ]
    return {
        "mode": "loop",
        "order": [s["agent_role"] for s in steps],
        "parallel_groups": [[s["agent_role"]] for s in steps],
        "steps": steps,
    }


async def run_eval_path_resource_loop(
    session: AsyncSession,
    user: User,
    *,
    auto_generate: bool = True,
    kinds: Optional[list[str]] = None,
    top_k: int = 2,
) -> dict[str, Any]:
    """一键闭环：评估 → 路径 →（可选）资源生成，全程写 AgentStep。"""
    kind_list = [k for k in (kinds or list(DEFAULT_KINDS)) if k]
    if not kind_list:
        kind_list = list(DEFAULT_KINDS)
    top_k = max(1, min(int(top_k or 2), 5))

    run_id = f"loop-{uuid.uuid4().hex[:12]}"
    plan = build_closed_loop_plan(top_k=top_k, kinds=kind_list)

    await agent_trace.start_agent_run(
        session,
        run_id=run_id,
        user=user,
        scene="closed_loop",
        mode="loop",
        topic="评估→路径→资源",
        graph_plan=plan,
    )
    await agent_trace.ensure_steps(session, run_id, plan["steps"])

    # 1) evaluate
    await agent_trace.mark_step_running(session, run_id, step_index=0, agent_role="Evaluator")
    report = await build_evaluation_report(session, user)
    hints = evaluation_suggestions_for_path(report)
    await agent_trace.mark_step_done(
        session,
        run_id,
        step_index=0,
        summary=f"掌握率 {report.mastery_rate}%",
        payload={
            "mastery_rate": report.mastery_rate,
            "suggestions": hints[:8],
            "weaknesses": list(report.weaknesses or [])[:6],
        },
    )

    # 2) path
    await agent_trace.mark_step_running(session, run_id, step_index=1, agent_role="PathPlanner")
    path = await generate_learning_path(
        session,
        user,
        goal="根据成长评估动态调整学习计划（闭环）",
        evaluation_hints=hints,
    )
    steps = list(getattr(path, "steps", None) or [])
    targets: list[dict[str, Any]] = []
    for step in steps:
        slug = str(getattr(step, "planet_slug", None) or (step.get("planet_slug") if isinstance(step, dict) else "") or "")
        name = str(getattr(step, "planet_name", None) or (step.get("planet_name") if isinstance(step, dict) else "") or slug)
        if not slug:
            continue
        if any(t["planet_slug"] == slug for t in targets):
            continue
        rk = getattr(step, "resource_kinds", None) if not isinstance(step, dict) else step.get("resource_kinds")
        step_kinds = [str(x) for x in (rk or kind_list) if x][:3] or list(kind_list)
        targets.append({"planet_slug": slug, "planet_name": name, "kinds": step_kinds})
        if len(targets) >= top_k:
            break

    await agent_trace.mark_step_done(
        session,
        run_id,
        step_index=1,
        summary=f"路径「{path.title}」共 {len(steps)} 步",
        payload={"path_id": path.id, "title": path.title, "targets": targets},
    )

    # 3) resources
    generated: list[dict[str, Any]] = []
    await agent_trace.mark_step_running(session, run_id, step_index=2, agent_role="ResourceCoordinator")
    if auto_generate and targets:
        for target in targets:
            slug = target["planet_slug"]
            use_kinds = target.get("kinds") or kind_list
            event_count = 0
            last_summary = ""
            try:
                async for ev in run_resource_generation(
                    session,
                    user,
                    slug,
                    use_kinds,  # type: ignore[arg-type]
                    extra_requirements="闭环自动补强：针对评估弱项生成巩固资源",
                    run_id="",
                ):
                    event_count += 1
                    last_summary = str(ev.get("content") or last_summary)
                    payload = ev.get("payload") or {}
                    if isinstance(payload, dict) and payload.get("resource_id"):
                        generated.append(
                            {
                                "planet_slug": slug,
                                "planet_name": target.get("planet_name"),
                                "kind": payload.get("kind"),
                                "resource_id": payload.get("resource_id"),
                                "title": payload.get("title"),
                            }
                        )
            except Exception as exc:  # noqa: BLE001
                logger.exception("closed-loop resource gen failed for %s: %s", slug, exc)
                generated.append({"planet_slug": slug, "error": str(exc)})
            if not any(g.get("planet_slug") == slug and g.get("resource_id") for g in generated):
                generated.append(
                    {
                        "planet_slug": slug,
                        "planet_name": target.get("planet_name"),
                        "events": event_count,
                        "note": last_summary or "已尝试生成",
                    }
                )

    await agent_trace.mark_step_done(
        session,
        run_id,
        step_index=2,
        summary=f"资源产物 {len([g for g in generated if g.get('resource_id')])} 份",
        payload={"generated": generated, "auto_generate": auto_generate},
    )

    # 4) notify
    await agent_trace.mark_step_running(session, run_id, step_index=3, agent_role="Notifier")
    msg = (
        f"闭环完成：掌握率 {report.mastery_rate}% → 路径已重排"
        + (f" → 已为 {len(targets)} 个弱项触发生成" if auto_generate else "（未自动生成资源）")
    )
    try:
        from app.services.notification_service import create_notification

        await create_notification(
            session,
            user_id=user.id,
            title="学习闭环已完成",
            body=msg,
            kind="closed_loop",
            link="/student?dock=path",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("closed-loop notify failed: %s", exc)

    await agent_trace.mark_step_done(
        session,
        run_id,
        step_index=3,
        summary=msg,
        payload={"message": msg},
    )
    await agent_trace.finish_agent_run(session, run_id, status="completed")

    return {
        "ok": True,
        "run_id": run_id,
        "mode": "loop",
        "mastery_rate": report.mastery_rate,
        "path": path.model_dump() if hasattr(path, "model_dump") else path,
        "targets": targets,
        "generated": generated,
        "message": msg,
        "suggestions": hints[:8],
    }
