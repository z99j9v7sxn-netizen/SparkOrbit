from app.services.agent_trace import build_council_plan, build_handoff_plan
from app.services.interview_agents import build_interview_prep_plan, council_roles_for
from app.services.interview_catalog import kinds_for


def test_interview_prep_plan_groups():
    plan = build_interview_prep_plan("job")
    assert plan["mode"] == "workflow"
    assert plan["parallel_groups"][0] == ["JobAnalyst", "ProfileParser"]
    assert plan["parallel_groups"][1] == ["QuestionPlanner"]
    assert set(plan["question_kinds"]) == set(kinds_for("job"))
    assert len(plan["parallel_groups"][2]) == 4
    assert len(plan["steps"]) == 7


def test_interview_prep_plan_academic_kinds():
    plan = build_interview_prep_plan("academic")
    assert plan["question_kinds"] == kinds_for("academic")
    assert all(s.startswith("Q-") for s in plan["parallel_groups"][2])


def test_council_roles_switch_by_scenario():
    assert council_roles_for("job") == ["技术官", "HR官", "业务官"]
    assert council_roles_for("academic") == ["学科导师", "综合素质官", "科研潜力官"]
    plan = build_council_plan(council_roles_for("academic"))
    assert plan["mode"] == "council"
    assert plan["steps"][-1]["agent_role"] == "CouncilSummarizer"


def test_turn_handoff_plan_roles():
    plan = build_handoff_plan(["AnswerAggregator", "MultimodalScorer", "FollowUpStrategist"])
    assert plan["order"] == ["AnswerAggregator", "MultimodalScorer", "FollowUpStrategist"]


def test_maybe_insert_followup_once():
    from app.services.interview_service import maybe_insert_followup

    questions = [
        {"index": 0, "kind": "tech", "question": "请介绍一个项目"},
        {"index": 1, "kind": "soft", "question": "如何沟通"},
    ]
    qs, inserted = maybe_insert_followup(
        questions,
        answered_index=0,
        strategy="probe",
        followup_question="这个项目里你负责哪一块？",
        followup_of="turn-1",
    )
    assert inserted
    assert len(qs) == 3
    assert qs[1]["question"] == "这个项目里你负责哪一块？"
    assert qs[1]["followup_of"] == "turn-1"
    assert qs[2]["index"] == 2

    qs2, inserted2 = maybe_insert_followup(
        qs,
        answered_index=1,
        strategy="challenge",
        followup_question="再追一层？",
        followup_of="turn-2",
    )
    assert not inserted2
    assert qs2 == qs


def test_maybe_insert_followup_skips_next():
    from app.services.interview_service import maybe_insert_followup

    qs, inserted = maybe_insert_followup(
        [{"index": 0, "kind": "tech", "question": "q1"}],
        answered_index=0,
        strategy="next",
        followup_question="不该插入",
        followup_of="x",
    )
    assert not inserted
    assert len(qs) == 1


def test_aggregate_interview_portrait_empty():
    from app.services.interview_service import aggregate_interview_portrait

    data = aggregate_interview_portrait([], {})
    assert data["session_count"] == 0
    assert data["latest"] is None
    assert data["job"]["count"] == 0
    assert data["loop_counts"]["mistake"] == 0


def test_aggregate_interview_portrait_job_weak_and_trend():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from app.services.interview_service import aggregate_interview_portrait

    t1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 10, tzinfo=timezone.utc)
    s1 = SimpleNamespace(
        id="s1",
        status="completed",
        scenario="job",
        job_role="backend",
        overall_score=62,
        dimension_scores={},
        created_at=t1,
        finished_at=t1,
    )
    s2 = SimpleNamespace(
        id="s2",
        status="completed",
        scenario="job",
        job_role="backend",
        overall_score=78,
        dimension_scores={},
        created_at=t2,
        finished_at=t2,
    )
    skipped = SimpleNamespace(
        id="s3",
        status="running",
        scenario="job",
        job_role="frontend",
        overall_score=None,
        dimension_scores={},
        created_at=t2,
        finished_at=None,
    )
    reports = {
        "s1": SimpleNamespace(
            session_id="s1",
            dimension_scores={
                "professional_knowledge": 80,
                "job_skill_match": 70,
                "language_expression": 55,
                "logical_thinking": 60,
                "stress_resistance": 72,
            },
            resource_refs=[{"kind": "mistake", "title": "弱项1"}, {"kind": "review", "title": "卡1"}],
        ),
        "s2": SimpleNamespace(
            session_id="s2",
            dimension_scores={
                "professional_knowledge": 88,
                "job_skill_match": 76,
                "language_expression": 64,
                "logical_thinking": 80,
                "stress_resistance": 74,
            },
            resource_refs=[{"kind": "resource", "title": "复盘"}],
        ),
    }
    data = aggregate_interview_portrait([s2, s1, skipped], reports)
    assert data["session_count"] == 2
    assert data["avg_score"] == 70.0
    assert data["latest"]["id"] == "s2"
    assert data["job"]["count"] == 2
    assert data["academic"]["count"] == 0
    assert data["job"]["dimension_avg"]["language_expression"] == 59.5
    assert data["trend"][0]["id"] == "s1"
    assert data["trend"][-1]["id"] == "s2"
    weak_keys = {item["key"] for item in data["weak_dims"]}
    assert "language_expression" in weak_keys
    assert data["loop_counts"]["mistake"] == 1
    assert data["loop_counts"]["review"] == 1
    assert data["loop_counts"]["resource"] == 1
    assert data["by_role"][0]["job_role"] == "backend"


def test_apply_interview_completed_event():
    from types import SimpleNamespace

    from app.schemas.student_profile import StudentProfileExtract
    from app.services.profile_refresh import _apply_structured_payload, _delta_hint

    updated = StudentProfileExtract(student_name="t")
    updated.prior_knowledge.score = 50
    updated.mistake_tendency.score = 50
    updated.motivation_level.score = 50
    event = SimpleNamespace(
        event_type="interview_completed",
        summary="完成后端开发模拟面试，总分 62",
        payload_json={
            "overall_score": 62,
            "dimension_scores": {"language_expression": 55, "professional_knowledge": 80},
            "weak_turns": 2,
        },
    )
    source = _apply_structured_payload(updated, [event])
    assert source == "interview"
    assert updated.prior_knowledge.score == 48
    assert updated.mistake_tendency.score < 50
    assert any("面试弱项" in x for x in updated.mistake_tendency.evidence)
    assert any("模拟面试" in x for x in updated.prior_knowledge.evidence)
    assert _delta_hint("interview_completed", {"overall_score": 62}) == "综合 62"


def test_practice_star_detection():
    from app.services.interview_practice import detect_star

    full = detect_star("当时项目需要优化下单接口，我采取了本地缓存加索引的方案，最终把耗时从 800ms 降到 90ms")
    assert full == {"situation": True, "task": True, "action": True, "result": True}

    partial = detect_star("我觉得这个技术很有意思")
    assert not partial["situation"]
    assert not partial["result"]

    assert detect_star("") == {"situation": False, "task": False, "action": False, "result": False}
