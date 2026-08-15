"""Agent 行为验收（无外部 LLM / DB）。"""
from app.agents.orchestration import plan_for_mode
from app.agents.tools.intent import classify_companion_intent


def test_eval_resource_dag_accepts_c2_contract():
    """固定 kinds → 必须产出 order + parallel_groups + steps。"""
    plan = plan_for_mode("workflow", kinds=["doc", "quiz", "reading", "code"])
    assert "order" in plan and "parallel_groups" in plan and "steps" in plan
    assert plan["steps"][0]["payload"]["kind"] in plan["order"]
    # quiz / reading 不与 doc 同组并行
    g0 = set(plan["parallel_groups"][0])
    assert "quiz" not in g0
    assert "reading" not in g0


def test_eval_handoff_four_roles():
    plan = plan_for_mode("handoff")
    assert plan["order"] == ["Teacher", "Mirror", "Evaluator", "PathPlanner"]
    assert [s["agent_role"] for s in plan["steps"]] == plan["order"]


def test_eval_supervisor_intent_to_path_action():
    intent = classify_companion_intent("请帮我规划学习路径")
    assert intent == "path"
    plan = plan_for_mode(
        "supervisor",
        plan=[
            {"type": "intent", "priority": 1, "agent_role": "IntentClassifier"},
            {"type": "path", "priority": 2, "agent_role": "PathPlanner"},
        ],
    )
    roles = [s["agent_role"] for s in plan["steps"]]
    assert "Supervisor" in roles and "PathPlanner" in roles
