"""AgentRun / AgentStep 写入与查询（管理端观测）。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_trace import AgentRun, AgentStep
from app.models.user import User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def start_agent_run(
    session: AsyncSession,
    *,
    run_id: str,
    user: User | None = None,
    user_id: str = "",
    user_name: str = "",
    scene: str,
    mode: str,
    topic: str = "",
    graph_plan: Optional[dict[str, Any]] = None,
) -> AgentRun:
    uid = user_id or (user.id if user else "")
    uname = user_name or (getattr(user, "display_name", None) or getattr(user, "username", "") or "")
    row = AgentRun(
        id=run_id,
        user_id=uid,
        user_name=uname,
        scene=scene,
        mode=mode,
        status="running",
        topic=topic,
        graph_plan=graph_plan or {},
        current_step=0,
        current_agent="",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def ensure_steps(
    session: AsyncSession,
    run_id: str,
    steps: list[dict[str, Any]],
) -> list[AgentStep]:
    """按计划预创建 pending 步骤（便于前端先画完整图）。"""
    created: list[AgentStep] = []
    for s in steps:
        row = AgentStep(
            id=str(uuid4()),
            run_id=run_id,
            step_index=int(s.get("step_index") or 0),
            agent_role=str(s.get("agent_role") or ""),
            status="pending",
            parallel_group=str(s.get("parallel_group") or ""),
            summary=str(s.get("summary") or ""),
            payload=dict(s.get("payload") or {}),
        )
        session.add(row)
        created.append(row)
    await session.commit()
    return created


async def mark_step_running(
    session: AsyncSession,
    run_id: str,
    *,
    step_index: int,
    agent_role: str,
    parallel_group: str = "",
    summary: str = "",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    row = (
        await session.execute(
            select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.step_index == step_index)
        )
    ).scalar_one_or_none()
    now = _utcnow()
    if row is None:
        row = AgentStep(
            id=str(uuid4()),
            run_id=run_id,
            step_index=step_index,
            agent_role=agent_role,
            status="running",
            parallel_group=parallel_group,
            summary=summary,
            payload=payload or {},
            started_at=now,
        )
        session.add(row)
    else:
        row.status = "running"
        row.agent_role = agent_role or row.agent_role
        if parallel_group:
            row.parallel_group = parallel_group
        if summary:
            row.summary = summary
        if payload:
            row.payload = {**(row.payload or {}), **payload}
        row.started_at = row.started_at or now

    run = await session.get(AgentRun, run_id)
    if run:
        run.current_step = step_index
        run.current_agent = agent_role
        run.status = "running"
    await session.commit()


async def mark_step_done(
    session: AsyncSession,
    run_id: str,
    *,
    step_index: int,
    summary: str = "",
    payload: Optional[dict[str, Any]] = None,
    ok: bool = True,
) -> None:
    row = (
        await session.execute(
            select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.step_index == step_index)
        )
    ).scalar_one_or_none()
    now = _utcnow()
    if row is None:
        return
    row.status = "completed" if ok else "failed"
    if summary:
        row.summary = summary
    if payload:
        row.payload = {**(row.payload or {}), **payload}
    row.finished_at = now
    await session.commit()


async def finish_agent_run(
    session: AsyncSession,
    run_id: str,
    *,
    status: str = "completed",
    error_message: str = "",
) -> None:
    run = await session.get(AgentRun, run_id)
    if run is None:
        return
    run.status = status
    run.error_message = error_message or run.error_message
    run.finished_at = _utcnow()
    if status != "running":
        run.current_agent = run.current_agent or ""
    await session.commit()


async def list_agent_runs(
    session: AsyncSession,
    *,
    limit: int = 50,
    scene: str = "",
    mode: str = "",
    status: str = "",
    user_id: str = "",
) -> list[AgentRun]:
    stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(min(max(limit, 1), 200))
    if scene:
        stmt = stmt.where(AgentRun.scene == scene)
    if mode:
        stmt = stmt.where(AgentRun.mode == mode)
    if status:
        stmt = stmt.where(AgentRun.status == status)
    if user_id:
        stmt = stmt.where(AgentRun.user_id == user_id)
    return list((await session.execute(stmt)).scalars().all())


async def get_agent_run_detail(session: AsyncSession, run_id: str) -> Optional[dict[str, Any]]:
    run = await session.get(AgentRun, run_id)
    if run is None:
        return None
    steps = list(
        (
            await session.execute(
                select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.step_index.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": run.id,
        "user_id": run.user_id,
        "user_name": run.user_name,
        "scene": run.scene,
        "mode": run.mode,
        "status": run.status,
        "topic": run.topic,
        "graph_plan": run.graph_plan or {},
        "current_step": run.current_step,
        "current_agent": run.current_agent,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else "",
        "finished_at": run.finished_at.isoformat() if run.finished_at else "",
        "steps": [
            {
                "id": s.id,
                "step_index": s.step_index,
                "agent_role": s.agent_role,
                "status": s.status,
                "parallel_group": s.parallel_group,
                "summary": s.summary,
                "payload": s.payload or {},
                "started_at": s.started_at.isoformat() if s.started_at else "",
                "finished_at": s.finished_at.isoformat() if s.finished_at else "",
            }
            for s in steps
        ],
    }


def build_resource_workflow_plan(kinds: list[str]) -> dict[str, Any]:
    """C2：组1 并行 doc/mindmap/media/deck/code；组2 quiz 等 doc；组3 reading 等 doc+mindmap。"""
    kind_set = set(kinds)
    g1_order = ["doc", "mindmap", "media", "deck", "code"]
    group1 = [k for k in g1_order if k in kind_set]
    group2 = ["quiz"] if "quiz" in kind_set else []
    group3 = ["reading"] if "reading" in kind_set else []
    # 不在三组模板里的 kind 并入组1
    known = set(g1_order) | {"quiz", "reading"}
    extras = [k for k in kinds if k not in known]
    group1 = group1 + extras

    order: list[str] = []
    parallel_groups: list[list[str]] = []
    if group1:
        parallel_groups.append(group1)
        order.extend(group1)
    if group2:
        parallel_groups.append(group2)
        order.extend(group2)
    if group3:
        parallel_groups.append(group3)
        order.extend(group3)

    steps = []
    idx = 0
    for gi, group in enumerate(parallel_groups, 1):
        for kind in group:
            steps.append(
                {
                    "step_index": idx,
                    "agent_role": kind,
                    "parallel_group": f"g{gi}",
                    "summary": f"待执行：{kind}",
                    "payload": {"kind": kind},
                }
            )
            idx += 1
    return {
        "order": order,
        "parallel_groups": parallel_groups,
        "steps": steps,
        "mode": "workflow",
    }


def build_handoff_plan(roles: list[str]) -> dict[str, Any]:
    steps = [
        {
            "step_index": i,
            "agent_role": role,
            "parallel_group": "",
            "summary": f"待接力：{role}",
            "payload": {},
        }
        for i, role in enumerate(roles)
    ]
    return {"order": roles, "parallel_groups": [[r] for r in roles], "steps": steps, "mode": "handoff"}


def build_supervisor_plan(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """
    supervisor：主控 + 按 priority 排列的子任务。
    tasks 项：{"type": str, "priority": int, "reason": str, "agent_role": str?}
    """
    ordered = sorted(
        list(tasks or []),
        key=lambda t: int(t.get("priority") or 100),
    )
    steps = []
    steps.append(
        {
            "step_index": 0,
            "agent_role": "Supervisor",
            "parallel_group": "control",
            "summary": "意图识别与优先级编排",
            "payload": {"type": "plan"},
        }
    )
    for i, t in enumerate(ordered, 1):
        steps.append(
            {
                "step_index": i,
                "agent_role": str(t.get("agent_role") or t.get("type") or f"task-{i}"),
                "parallel_group": "workers",
                "summary": str(t.get("reason") or t.get("type") or ""),
                "payload": {
                    "type": t.get("type"),
                    "priority": int(t.get("priority") or i),
                    "reason": t.get("reason"),
                },
            }
        )
    return {
        "plan": [
            {
                "type": s["payload"].get("type") or s["agent_role"],
                "priority": s["payload"].get("priority", s["step_index"]),
                "reason": s["summary"],
            }
            for s in steps[1:]
        ],
        "order": [s["agent_role"] for s in steps],
        "parallel_groups": [["Supervisor"], [s["agent_role"] for s in steps[1:]]],
        "steps": steps,
        "mode": "supervisor",
    }


def build_council_plan(roles: list[str]) -> dict[str, Any]:
    steps = [
        {
            "step_index": i,
            "agent_role": role,
            "parallel_group": "council",
            "summary": f"待评议：{role}",
            "payload": {},
        }
        for i, role in enumerate(roles)
    ]
    steps.append(
        {
            "step_index": len(roles),
            "agent_role": "CouncilSummarizer",
            "parallel_group": "summary",
            "summary": "待汇总评议",
            "payload": {},
        }
    )
    return {
        "order": roles + ["CouncilSummarizer"],
        "parallel_groups": [roles, ["CouncilSummarizer"]],
        "steps": steps,
        "mode": "council",
    }


async def seed_demo_mode_runs(session: AsyncSession) -> list[dict[str, Any]]:
    """写入四模式演示 run（不跑 LLM），供管理端图鉴对比。"""
    from datetime import datetime, timezone
    from uuid import uuid4

    now = datetime.now(timezone.utc)
    specs: list[tuple[str, str, str, dict[str, Any], list[tuple[str, str]]]] = []

    wf = build_resource_workflow_plan(["doc", "mindmap", "media", "deck", "code", "quiz", "reading"])
    # map kind -> display agent label
    kind_label = {
        "doc": "DocAgent",
        "mindmap": "MindAgent",
        "media": "MediaAgent",
        "deck": "DeckAgent",
        "code": "CodeAgent",
        "quiz": "QuizAgent",
        "reading": "ReadAgent",
    }
    for s in wf["steps"]:
        k = str((s.get("payload") or {}).get("kind") or s.get("agent_role"))
        s["agent_role"] = kind_label.get(k, k)
        s["summary"] = f"演示完成：{s['agent_role']}"
    specs.append(("demo-wf", "resource", "workflow", wf, [("资源工坊", "演示·四模式")]))

    hf = build_handoff_plan(["Teacher", "Mirror", "Evaluator", "PathPlanner"])
    for s in hf["steps"]:
        s["summary"] = f"演示交接完成：{s['agent_role']}"
    specs.append(("demo-hf", "simulation", "handoff", hf, [("镜像预演", "演示·四模式")]))

    cf = build_council_plan(["激进型", "均衡型", "保守型"])
    for s in cf["steps"]:
        s["summary"] = f"演示评议：{s['agent_role']}"
    specs.append(("demo-cf", "multiverse", "council", cf, [("平行宇宙", "演示·四模式")]))

    sf = build_supervisor_plan(
        [
            {"type": "intent", "priority": 1, "reason": "识别意图=path", "agent_role": "IntentClassifier"},
            {"type": "path", "priority": 2, "reason": "生成学习路径", "agent_role": "PathPlanner"},
            {"type": "next_actions", "priority": 3, "reason": "汇总下一步", "agent_role": "ActionComposer"},
        ]
    )
    for s in sf["steps"]:
        s["summary"] = f"演示统筹：{s['agent_role']}"
    specs.append(("demo-sv", "companion", "supervisor", sf, [("伴学", "演示·四模式")]))

    from app.services.learning_loop import build_closed_loop_plan

    lp = build_closed_loop_plan(top_k=2, kinds=["doc", "quiz"])
    for s in lp["steps"]:
        s["summary"] = f"演示闭环：{s['agent_role']}"
        s["status"] = "completed"
    specs.append(("demo-lp", "closed_loop", "loop", lp, [("成长闭环", "演示·loop")]))

    created: list[dict[str, Any]] = []
    for prefix, scene, mode, plan, _meta in specs:
        run_id = f"{prefix}-{uuid4().hex[:8]}"
        # remove old demo runs of same mode+scene with demo user name to avoid clutter? keep all
        run = AgentRun(
            id=run_id,
            user_id="demo-four-modes",
            user_name="演示·四模式",
            scene=scene,
            mode=mode,
            status="completed",
            topic={
                "workflow": "文件系统 · 资源包演示",
                "handoff": "梯度下降 · 镜像预演演示",
                "council": "学习策略 · 平行宇宙演示",
                "supervisor": "学习路径 · 伴学统筹演示",
            }.get(mode, mode),
            graph_plan=plan,
            current_step=max((s["step_index"] for s in plan["steps"]), default=0),
            current_agent=str(plan["steps"][-1]["agent_role"]) if plan["steps"] else "",
            finished_at=now,
        )
        session.add(run)
        for s in plan["steps"]:
            session.add(
                AgentStep(
                    id=str(uuid4()),
                    run_id=run_id,
                    step_index=int(s["step_index"]),
                    agent_role=str(s["agent_role"]),
                    status="completed",
                    parallel_group=str(s.get("parallel_group") or ""),
                    summary=str(s.get("summary") or ""),
                    payload=dict(s.get("payload") or {}),
                    started_at=now,
                    finished_at=now,
                )
            )
        created.append({"id": run_id, "mode": mode, "scene": scene, "topic": run.topic})
    await session.commit()
    return created
