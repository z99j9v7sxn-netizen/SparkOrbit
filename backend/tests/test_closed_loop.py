"""闭环意图与计划骨架冒烟。"""

from app.agents.tools.intent import classify_companion_intent
from app.services.learning_loop import build_closed_loop_plan


def test_closed_loop_intent():
    assert classify_companion_intent("根据我的弱项自动补强资源") == "closed_loop"
    assert classify_companion_intent("一键补资源") == "closed_loop"
    assert classify_companion_intent("学习路径怎么安排") == "path"


def test_closed_loop_plan_shape():
    plan = build_closed_loop_plan(top_k=2, kinds=["doc", "quiz"])
    assert plan["mode"] == "loop"
    assert len(plan["steps"]) == 4
    assert plan["steps"][0]["agent_role"] == "Evaluator"
    assert plan["steps"][2]["payload"]["top_k"] == 2
