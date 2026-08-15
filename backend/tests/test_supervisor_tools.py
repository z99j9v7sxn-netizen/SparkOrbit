"""工具层 / next_actions / 资源 run 持久化契约测试（无 LLM）。"""
from __future__ import annotations

import json
from pathlib import Path

from app.agents.tools.runtime import action_result, tool_open_feynman, tool_start_resource_run
from app.services.companion_supervisor import _default_next_actions, _kinds_for_intent
from app.services.resource_agents import get_resource_run, register_resource_run, update_resource_run_status


def test_action_result_schema():
    a = action_result(type="open_path", label="查看", tool_name="generate_learning_path", path_id="p1")
    assert a["type"] == "open_path"
    assert a["status"] == "ok"
    assert a["tool_name"] == "generate_learning_path"
    assert a["path_id"] == "p1"


def test_tool_start_resource_run_registers_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.resource_agents._runs_dir",
        lambda: Path(tmp_path),
    )
    res = tool_start_resource_run(
        user_id="u1",
        planet_slug="planet-x",
        kinds=["deck", "quiz"],
        extra="课件",
    )
    assert res["status"] == "ok"
    assert res["type"] == "stream_resources"
    assert res["run_id"]
    assert res["tool_name"] == "start_resource_run"
    hit = get_resource_run(res["run_id"])
    assert hit is not None
    assert hit["user_id"] == "u1"
    assert hit["kinds"] == ["deck", "quiz"]
    disk = Path(tmp_path) / f"{res['run_id']}.json"
    assert disk.is_file()
    data = json.loads(disk.read_text(encoding="utf-8"))
    assert data["planet_slug"] == "planet-x"


def test_tool_start_resource_run_needs_planet():
    res = tool_start_resource_run(user_id="u1", planet_slug="", kinds=["doc"])
    assert res["status"] == "error"
    assert res["type"] == "need_planet"


def test_resource_run_status_update(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.resource_agents._runs_dir", lambda: Path(tmp_path))
    register_resource_run("res-test1", {"user_id": "u", "planet_slug": "p", "kinds": ["doc"]})
    update_resource_run_status("res-test1", "completed", ok=True)
    hit = get_resource_run("res-test1")
    assert hit and hit["status"] == "completed"
    assert hit.get("ok") is True


def test_get_resource_run_missing_is_none():
    """缺失 run 应返回 None（路由层据此 404，而非误判 403）。"""
    from app.services.resource_agents import get_resource_run

    assert get_resource_run("res-does-not-exist-xyz") is None


def test_kinds_for_intent_avoids_media_default():
    assert "media" not in _kinds_for_intent("resource")
    assert _kinds_for_intent("quiz") == ["quiz"]
    assert "deck" in _kinds_for_intent("deck")


def test_default_next_actions_shape():
    actions = _default_next_actions("chat", "planet-a")
    types = {a["type"] for a in actions}
    assert "generate_path" in types
    assert "generate_deck" in types
    assert "feynman" in types
    feyn = tool_open_feynman(planet_slug="planet-a")
    assert feyn["type"] == "feynman"
    assert feyn["tool_name"] == "open_feynman"
