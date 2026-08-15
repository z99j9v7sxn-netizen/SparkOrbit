"""薄编排层：统一四 mode 计划构建，执行仍在 services。"""
from __future__ import annotations

from typing import Any

from app.services import agent_trace

MODE_WORKFLOW = "workflow"
MODE_HANDOFF = "handoff"
MODE_SUPERVISOR = "supervisor"
MODE_COUNCIL = "council"


def plan_for_mode(mode: str, **kwargs: Any) -> dict[str, Any]:
    m = (mode or "").strip().lower()
    if m == MODE_WORKFLOW:
        return agent_trace.build_resource_workflow_plan(list(kwargs.get("kinds") or []))
    if m == MODE_HANDOFF:
        roles = list(kwargs.get("roles") or ["Teacher", "Mirror", "Evaluator", "PathPlanner"])
        return agent_trace.build_handoff_plan(roles)
    if m == MODE_COUNCIL:
        roles = list(kwargs.get("roles") or [])
        return agent_trace.build_council_plan(roles)
    if m == MODE_SUPERVISOR:
        return agent_trace.build_supervisor_plan(
            list(kwargs.get("plan") or kwargs.get("tasks") or []),
        )
    raise ValueError(f"unknown orchestration mode: {mode}")
