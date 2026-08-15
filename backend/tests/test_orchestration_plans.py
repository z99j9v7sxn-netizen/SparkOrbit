from app.agents.orchestration import MODE_HANDOFF, MODE_SUPERVISOR, MODE_WORKFLOW, plan_for_mode
from app.services.agent_trace import (
    build_council_plan,
    build_handoff_plan,
    build_resource_workflow_plan,
    build_supervisor_plan,
)


def test_resource_workflow_dag_groups():
    plan = build_resource_workflow_plan(["doc", "mindmap", "quiz", "reading", "media"])
    assert plan["mode"] == "workflow"
    assert ["doc", "mindmap", "media"] == plan["parallel_groups"][0] or set(plan["parallel_groups"][0]) >= {
        "doc",
        "mindmap",
        "media",
    }
    assert "quiz" in plan["parallel_groups"][1]
    assert "reading" in plan["parallel_groups"][2]
    assert len(plan["steps"]) == 5


def test_handoff_plan_order():
    plan = build_handoff_plan(["Teacher", "Mirror", "Evaluator", "PathPlanner"])
    assert plan["mode"] == "handoff"
    assert plan["order"] == ["Teacher", "Mirror", "Evaluator", "PathPlanner"]
    assert plan["steps"][0]["agent_role"] == "Teacher"


def test_council_plan_has_summarizer():
    plan = build_council_plan(["激进型", "均衡型", "保守型"])
    assert plan["mode"] == "council"
    assert plan["steps"][-1]["agent_role"] == "CouncilSummarizer"


def test_supervisor_plan_priority():
    plan = build_supervisor_plan(
        [
            {"type": "path", "priority": 2, "reason": "路径", "agent_role": "PathPlanner"},
            {"type": "intent", "priority": 1, "reason": "意图", "agent_role": "IntentClassifier"},
        ]
    )
    assert plan["mode"] == "supervisor"
    assert plan["steps"][0]["agent_role"] == "Supervisor"
    assert plan["steps"][1]["agent_role"] == "IntentClassifier"
    assert plan["steps"][2]["agent_role"] == "PathPlanner"


def test_plan_for_mode_dispatch():
    assert plan_for_mode(MODE_WORKFLOW, kinds=["doc"])["mode"] == "workflow"
    assert plan_for_mode(MODE_HANDOFF)["mode"] == "handoff"
    assert plan_for_mode(MODE_SUPERVISOR, plan=[{"type": "chat", "priority": 1}])["mode"] == "supervisor"
