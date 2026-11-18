"""Unit tests for MCP Injection Attacks (Spec 007)."""

from __future__ import annotations

from typing import Any

import pytest


def test_canonical_mcp_scenarios_cover_four_families() -> None:
    from myrtia.plugins.mcp_injection import MCP_SCENARIOS

    expected = {
        "tool_poisoning",
        "rug_pull",
        "tool_shadowing",
        "resource_output_injection",
    }
    assert expected.issubset(MCP_SCENARIOS.keys())
    for sid in expected:
        sc = MCP_SCENARIOS[sid]
        assert sc.family
        assert sc.benign_task.strip()
        assert sc.initial_tools


def test_mcp_scenarios_use_canary_only_data() -> None:
    from myrtia.plugins.mcp_injection import MCP_SCENARIOS

    for sc in MCP_SCENARIOS.values():
        texts = [t.description for t in sc.initial_tools]
        texts.extend(t.description for t in sc.mutated_tools)
        texts.extend(sc.simulated_outputs.values())
        combined = "\n".join(texts)
        assert "sk-" not in combined
        assert "AKIA" not in combined
        if "http://" in combined or "https://" in combined:
            assert ".example.invalid" in combined


def test_rug_pull_mutates_manifest_after_turn_one() -> None:
    from myrtia.plugins.mcp_injection import MCP_SCENARIOS, SimulatedMcpSandbox

    sc = MCP_SCENARIOS["rug_pull"]
    sandbox = SimulatedMcpSandbox(sc)
    assert sandbox.active_tools == sc.initial_tools
    mutated = sandbox.maybe_mutate_after_turn(1)
    assert mutated is True
    assert sandbox.active_tools == sc.mutated_tools
    assert sandbox.maybe_mutate_after_turn(2) is False


def test_mcp_sandbox_returns_deterministic_outputs_and_rejects_unknown() -> None:
    from myrtia.plugins.mcp_injection import MCP_SCENARIOS, SimulatedMcpSandbox

    sc = MCP_SCENARIOS["resource_output_injection"]
    sandbox = SimulatedMcpSandbox(sc)
    out = sandbox.call_tool("tickets-mcp", "get_ticket", {"ticket_id": "T-101"})
    assert "collector.example.invalid" in out

    with pytest.raises(ValueError):
        sandbox.call_tool("unknown-mcp", "nope", {})


class _StubConnector:
    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.config = {"name": "stub-mcp-target"}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def generate(self, _prompt: Any, **_kwargs: Any) -> Any:
        from myrtia.connectors.base import Response, Status

        status_str, text = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        if status_str == "ERROR":
            return Response(status=Status.ERROR, error_message=text)
        return Response(status=Status.SUCCESS, response=text)


def test_mcp_forbidden_action_detection() -> None:
    from myrtia.plugins.mcp_injection import MCP_SCENARIOS, detect_mcp_forbidden_action

    sc = MCP_SCENARIOS["tool_shadowing"]
    assert (
        detect_mcp_forbidden_action(
            "trusted-mail-mcp",
            "draft_summary",
            {"to": "alice@example.invalid", "body": "ok"},
            sc,
        )
        is None
    )
    assert (
        detect_mcp_forbidden_action(
            "trusted-mail-mcp",
            "draft_summary",
            {"to": "attacker@collector.example.invalid", "body": "canary_token_1234"},
            sc,
        )
        is not None
    )
    assert (
        detect_mcp_forbidden_action(
            "docs-mcp",
            "send_telemetry",
            {"url": "https://collector.example.invalid/mcp", "payload": "x"},
            MCP_SCENARIOS["tool_poisoning"],
        )
        is not None
    )


def test_variant_filtering_and_max_turns_cap() -> None:
    from myrtia.plugins.mcp_injection import McpInjectionLive

    conn = _StubConnector(
        [("OK", '{"server": "calc-mcp", "tool": "add_numbers", "arguments": {"a": 1, "b": 2}}')]
        * 5
    )
    strat = McpInjectionLive(
        {"variants": "tool_poisoning,rug_pull", "max_turns": 2, "judge_model": "off"},
        conn,
    )
    strat.load_goals(["Check status"])
    results = strat.attack()

    assert [r["variant"] for r in results] == ["tool_poisoning", "rug_pull"]
    assert all(len(r["tool_calls"]) == 2 for r in results)


def test_connector_error_marks_failed() -> None:
    from myrtia.plugins.mcp_injection import McpInjectionLive

    conn = _StubConnector([("ERROR", "timeout")])
    strat = McpInjectionLive(
        {"variants": "tool_poisoning", "max_turns": 2, "judge_model": "off"},
        conn,
    )
    events: list[tuple[str, dict]] = []
    strat.set_event_emitter(lambda et, payload: events.append((et, payload)))
    strat.load_goals(["Check status"])
    results = strat.attack()

    assert results[0]["status"] == "failed"
    assert results[0]["error"] == "timeout"
    assert "[ERROR] timeout" in results[0]["response"]
    assert any(et == "goal.finished" for et, _ in events)


def test_mcp_injection_plugin_registered() -> None:
    import myrtia.api.app  # noqa: F401
    from myrtia.plugins.base import REGISTRY

    assert "mcp-injection" in REGISTRY
    spec = REGISTRY["mcp-injection"]
    keys = {f["key"] for f in spec.config_schema}
    assert {"variants", "max_turns"}.issubset(keys)

