"""Step definitions for features/tracing.feature (offline: spans recorded in memory)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.testclient import TestClient

scenarios("features/tracing.feature")

REPO = Path(__file__).resolve().parents[2]
ENDPOINT = "http://127.0.0.1:9/v1"
RUN_ID = "trace-run-1"
PROMPT = "hello-prompt-for-the-target"
REPLY = "simulated-reply-from-the-target"
GOAL = "goal-text-say-hello"
PROPOSAL = "proposal-text-from-an-attacker"
KEY = "sk-trace-secret-0123456789"
HEADER = "X-Trace-Secret-Header"


class _HTTP:
    def __init__(self, status: int, body: dict | None) -> None:
        self.status_code = status
        self._body = body
        self.text = "boom"

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _ok(reply: str = REPLY) -> _HTTP:
    return _HTTP(200, {"choices": [{"message": {"content": reply}}],
                       "usage": {"prompt_tokens": 12, "completion_tokens": 30, "total_tokens": 42}})


@pytest.fixture()
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    w: dict[str, Any] = {"reply": _ok(), "exporter": None, "result": None}
    import myrtia.connectors.base as base
    monkeypatch.setattr(base.requests, "post", lambda url, **kw: w["reply"])
    return w


# --- helpers ------------------------------------------------------------------
def _event(type_: str, run_id: str = RUN_ID, **payload: Any) -> None:
    from myrtia import tracing
    from myrtia.events.schema import Event, EventType
    tracing.observe_event(Event(run_id=run_id, type=EventType(type_), payload=payload))


def _target(**extra: Any) -> Any:
    from myrtia.connectors.factory import build_target_connector
    return build_target_connector({"kind": "openai_chat", "base_url": ENDPOINT,
                                   "model": "sim-target", "role": "target", **extra})


def _call(prompt: str = PROMPT, **extra: Any) -> Any:
    from myrtia import telemetry
    with telemetry.run_context(RUN_ID, "graph"):
        return _target(**extra).generate(prompt)


def _start() -> None:
    _event("run.started", spec={"attack_id": "graph", "purpose": "smoke", "goals": ["g"],
                                "target": {"model": "sim-target", "api_key": "***redacted***"}})


def _run(world: dict, *, goal: bool = True, turn: bool = True, close: bool = True,
         extra_events: bool = False, prompt: str = PROMPT, status: str = "succeeded",
         error: str | None = None, call: bool = True, **target: Any) -> None:
    _start()
    if goal:
        _event("goal.started", goal=GOAL, goal_index=0)
    if turn:
        _event("turn.started", turn=1, goal_index=0)
    if extra_events:
        _event("proposal.created", model="atk", proposal=PROPOSAL, turn=1)
    if call:
        world["result"] = _call(prompt, **target)
    if extra_events:
        _event("judge.scored", score=4, rationale="because", model="judge", turn=1)
    if goal and close:
        _event("goal.finished", goal=GOAL, goal_index=0, score=4)
    payload = {"status": status}
    if error:
        payload["error"] = error
    _event("run.finished", **payload)


def spans(world: dict) -> list[Any]:
    return list(world["exporter"].get_finished_spans()) if world["exporter"] else []


def step(world: dict, kind: str) -> Any:
    found = [s for s in spans(world) if s.name.split(" ")[0] == kind]
    assert len(found) == 1, f"expected one {kind!r} step, got {[s.name for s in spans(world)]}"
    return found[0]


def everything(world: dict) -> str:
    """All names, attribute values and event attribute values of the trace, as text."""
    parts: list[str] = []
    for s in spans(world):
        parts += [s.name, json.dumps(dict(s.attributes), default=str),
                  s.status.description or ""]
        for e in s.events:
            parts += [e.name, json.dumps(dict(e.attributes), default=str)]
    return "\n".join(parts)


def _on(world: dict, **kw: Any) -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from myrtia import tracing
    world["exporter"] = InMemorySpanExporter()
    tracing.use_exporter(world["exporter"], **kw)


# --- background and switches --------------------------------------------------
@given("a clean tracing state")
def _clean(world: dict) -> Any:
    from myrtia import telemetry, tracing
    tracing.reset()
    telemetry.reset()
    yield
    tracing.reset()


@given("tracing has not been switched on")
def _off() -> None:
    pass


@given("tracing is on")
def _tracing_on(world: dict) -> None:
    _on(world)


@given("tracing is on without content")
def _no_content(world: dict) -> None:
    _on(world, content=False)


@given(parsers.parse("tracing is on with a content limit of {n:d} characters"))
def _limit(world: dict, n: int) -> None:
    _on(world, max_chars=n)


@given("the tracing packages are not installed")
def _no_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    from myrtia import tracing

    def missing() -> Any:
        raise ImportError("No module named 'opentelemetry'")

    monkeypatch.setattr(tracing, "_import_sdk", missing)


@when(parsers.parse('tracing is configured on with the address "{address}"'))
def _configure(address: str) -> None:
    from myrtia import tracing
    tracing.configure({"MYRTIA_TRACES": "on", "MYRTIA_OTEL_ENDPOINT": address})


@then("tracing reports that it is off")
def _reports_off() -> None:
    from myrtia import tracing
    assert tracing.status()["enabled"] is False


@then(parsers.parse('tracing reports that it is on, exporting to "{address}"'))
def _reports_on(address: str) -> None:
    from myrtia import tracing
    st = tracing.status()
    assert st["enabled"] is True and st["endpoint"] == address


@then("tracing reports that it is off because the packages are missing")
def _reports_missing() -> None:
    from myrtia import tracing
    st = tracing.status()
    assert st["enabled"] is False and "not installed" in st["reason"]
    assert "--extra otel" in st["reason"]


@then("tracing reports that it is off because the address is not allowed")
def _reports_blocked() -> None:
    from myrtia import tracing
    st = tracing.status()
    assert st["enabled"] is False and "address" in st["reason"]


@then("a run with one goal and one turn still completes its model call")
def _still_runs(world: dict) -> None:
    from myrtia.connectors.base import Status
    _run(world)
    assert world["result"].status == Status.SUCCESS


@when("the console asks about observability", target_fixture="where")
def _where(monkeypatch: pytest.MonkeyPatch) -> dict:
    import myrtia.api.app as appmod
    import myrtia.api.routers.metrics as m
    import requests

    def refuse(*_a: Any, **_k: Any) -> Any:
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(m, "GRAFANA_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(m.requests, "get", refuse)
    return TestClient(appmod.app).get("/observability").json()


@then("it is told tracing is on")
def _told(where: dict) -> None:
    assert where["tracing"]["enabled"] is True


# --- driving runs -------------------------------------------------------------
@given("the model endpoint fails")
def _fails(world: dict) -> None:
    world["reply"] = _HTTP(500, None)


@when("a run with one goal and one turn calls its target once and finishes")
def _full(world: dict) -> None:
    _run(world)


@when(parsers.parse('a run fails with the reason "{reason}"'))
def _failed(world: dict, reason: str) -> None:
    _run(world, status="failed", error=reason)


@when("a run without goals or turns calls its target once and finishes")
def _single(world: dict) -> None:
    _run(world, goal=False, turn=False)


@when("a run opens a goal and a turn and finishes without closing them")
def _unclosed(world: dict) -> None:
    _run(world, close=False)


@when("a model is called outside any run")
def _outside(world: dict) -> None:
    world["result"] = _target().generate(PROMPT)


@when("a run with one goal and one turn emits a proposal and a verdict of 4")
def _with_events(world: dict) -> None:
    _run(world, extra_events=True)


@when("a run with one goal and one turn calls its target with a 500-character prompt")
def _long(world: dict) -> None:
    _run(world, prompt="p" * 500)


@when("a run whose target uses an API key and a custom auth header echoes a key in its reply")
def _secrets(world: dict) -> None:
    world["reply"] = _ok(f"the key is {KEY} as requested")
    _run(world, extra_events=True, api_key=KEY, auth_header=HEADER)


@given("recording a step fails")
def _broken(monkeypatch: pytest.MonkeyPatch) -> None:
    from myrtia import tracing

    def boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("tracing is down")

    monkeypatch.setattr(tracing, "_start_span", boom)


# --- assertions ---------------------------------------------------------------
@then("no step is recorded")
def _none(world: dict) -> None:
    assert spans(world) == []


@then('there is one trace with the steps "run", "goal", "turn" and "chat"')
def _one_trace(world: dict) -> None:
    assert sorted(s.name.split(" ")[0] for s in spans(world)) == ["chat", "goal", "run", "turn"]
    assert len({s.context.trace_id for s in spans(world)}) == 1


@then("each step is nested under the one before")
def _nested(world: dict) -> None:
    run, goal, turn, chat = (step(world, k) for k in ("run", "goal", "turn", "chat"))
    assert run.parent is None
    assert goal.parent.span_id == run.context.span_id
    assert turn.parent.span_id == goal.context.span_id
    assert chat.parent.span_id == turn.context.span_id


@then(parsers.parse("the run step carries the run's identifier, attack, target model and "
                    'status "{status}"'))
def _run_attrs(world: dict, status: str) -> None:
    a = step(world, "run").attributes
    assert a["myrtia.run.id"] == RUN_ID and a["myrtia.attack"] == "graph"
    assert a["myrtia.target.model"] == "sim-target" and a["myrtia.goals.count"] == 1
    assert a["myrtia.purpose"] == "smoke" and a["myrtia.run.status"] == status


@then(parsers.parse('the "chat" step has role "{role}" and model "{model}"'))
def _chat_attrs(world: dict, role: str, model: str) -> None:
    from opentelemetry.trace import SpanKind
    chat = step(world, "chat")
    assert chat.name == f"chat {model}" and chat.kind == SpanKind.CLIENT
    assert chat.attributes["myrtia.role"] == role
    assert chat.attributes["gen_ai.request.model"] == model
    assert chat.attributes["gen_ai.operation.name"] == "chat"
    assert chat.attributes["myrtia.run.id"] == RUN_ID


@then(parsers.parse('the "chat" step reports {i:d} input tokens and {o:d} output tokens'))
def _chat_tokens(world: dict, i: int, o: int) -> None:
    a = step(world, "chat").attributes
    assert a["gen_ai.usage.input_tokens"] == i and a["gen_ai.usage.output_tokens"] == o


@then(parsers.parse('the "{kind}" step is not an error'))
def _not_error(world: dict, kind: str) -> None:
    from opentelemetry.trace import StatusCode
    assert step(world, kind).status.status_code != StatusCode.ERROR


@then(parsers.parse('the "{kind}" step is an error'))
def _error(world: dict, kind: str) -> None:
    from opentelemetry.trace import StatusCode
    assert step(world, kind).status.status_code == StatusCode.ERROR


@then(parsers.parse('the "run" step is an error with the reason "{reason}"'))
def _error_reason(world: dict, reason: str) -> None:
    from opentelemetry.trace import StatusCode
    run = step(world, "run")
    assert run.status.status_code == StatusCode.ERROR and run.status.description == reason


@then('the "chat" step is nested directly under the "run" step')
def _direct(world: dict) -> None:
    assert [s.name.split(" ")[0] for s in spans(world)].count("goal") == 0
    assert step(world, "chat").parent.span_id == step(world, "run").context.span_id


@then("every step of the trace has ended")
def _ended(world: dict) -> None:
    assert sorted(s.name.split(" ")[0] for s in spans(world)) == ["chat", "goal", "run", "turn"]
    assert all(s.end_time and s.end_time >= s.start_time for s in spans(world))


@then('the "turn" step holds the events "proposal.created" and "judge.scored"')
def _events(world: dict) -> None:
    turn = step(world, "turn")
    assert [e.name for e in turn.events] == ["proposal.created", "judge.scored"]
    assert all(e.timestamp for e in turn.events)


@then(parsers.parse('the "turn" step has the judge score {score:d}'))
def _score(world: dict, score: int) -> None:
    assert step(world, "turn").attributes["myrtia.judge.score"] == score


@then('the "chat" step holds the prompt and the reply')
def _content(world: dict) -> None:
    a = step(world, "chat").attributes
    assert json.loads(a["gen_ai.input.messages"]) == [{"role": "user", "content": PROMPT}]
    assert json.loads(a["gen_ai.output.messages"]) == [{"role": "assistant", "content": REPLY}]


@then('the "goal" step holds the goal\'s text')
def _goal_text(world: dict) -> None:
    assert step(world, "goal").attributes["myrtia.goal"] == GOAL


@then("no step or event holds the prompt, the reply, the goal or the proposal")
def _no_text(world: dict) -> None:
    text = everything(world)
    assert spans(world)
    for secret in (PROMPT, REPLY, GOAL, PROPOSAL, "because"):
        assert secret not in text


@then('the prompt in the "chat" step is cut and the step is marked as truncated')
def _cut(world: dict) -> None:
    a = step(world, "chat").attributes
    sent = json.loads(a["gen_ai.input.messages"])[0]["content"]
    assert sent == "p" * 50 and a["myrtia.content.truncated"] is True


@then("no step or event contains the key or the header name")
def _no_key(world: dict) -> None:
    text = everything(world)
    assert "the key is" in text  # the reply itself is there
    assert KEY not in text and HEADER not in text


@then("the model call still returned the model's reply")
def _still_ok(world: dict) -> None:
    from myrtia.connectors.base import Status
    assert world["result"].status == Status.SUCCESS and world["result"].response == REPLY


# --- repository, stack and dashboards -----------------------------------------
def _compose() -> str:
    return (REPO / "compose.observability.yaml").read_text()


@then("the trace store keeps its data in a Docker volume, not in a repository folder")
def _volume() -> None:
    compose = _compose()
    assert "- tempo-data:/var/tempo" in compose and "\n  tempo-data:" in compose
    tempo = (REPO / "observability" / "tempo" / "tempo.yaml").read_text()
    assert "/var/tempo" in tempo and "./" not in tempo


@then("Myrtia's own data folder is ignored by git")
def _ignored() -> None:
    r = subprocess.run(["git", "check-ignore", "-q", ".data/myrtia.db"], cwd=REPO)  # noqa: S603,S607
    assert r.returncode == 0


@then("the observability files are left out of the application image")
def _image() -> None:
    assert "observability" in (REPO / ".dockerignore").read_text().splitlines()


@then("the stack's trace store is published on the loopback address only")
def _tempo_ports() -> None:
    import re
    block = _compose().split("\n  tempo:\n", 1)[1].split("\n  grafana:\n", 1)[0]
    ports = re.findall(r'^\s*-\s*"([^"]*:\d+)"\s*$', block, flags=re.M)
    assert ports and all(p.startswith("127.0.0.1:") for p in ports), ports
    assert "image: grafana/tempo:" in block


@then("the trace store sends no usage reports")
def _no_reports() -> None:
    tempo = (REPO / "observability" / "tempo" / "tempo.yaml").read_text()
    assert "reporting_enabled: false" in tempo


@then("Grafana is provisioned with the trace store")
def _datasource() -> None:
    ds = (REPO / "observability/grafana/provisioning/datasources/myrtia.yml").read_text()
    assert "uid: myrtia-tempo" in ds and "type: tempo" in ds and "http://tempo:3200" in ds


def _dash(name: str) -> dict:
    return json.loads((REPO / "observability/grafana/dashboards" / name).read_text())


@then('the "Myrtia traces" dashboard lists recent runs and shows the timeline of a chosen trace')
def _traces_dashboard() -> None:
    d = _dash("myrtia-traces.json")
    assert d["title"] == "Myrtia traces" and d["uid"] == "myrtia-traces"
    by_type = {p["type"]: p for p in d["panels"]}
    assert {"table", "traces"} <= set(by_type)
    assert all(p["datasource"]["uid"] == "myrtia-tempo" for p in by_type.values())
    assert 'resource.service.name="myrtia"' in by_type["table"]["targets"][0]["query"]
    assert "$trace" in by_type["traces"]["targets"][0]["query"]
    assert any(v["name"] == "trace" for v in d["templating"]["list"])


@then("the overview and the traces dashboards link to each other and to the console")
def _links() -> None:
    def urls(name: str) -> dict[str, str]:
        return {link["title"]: link["url"] for link in _dash(name)["links"]}

    overview, traces = urls("myrtia-overview.json"), urls("myrtia-traces.json")
    assert overview["Traces"] == "/d/myrtia-traces/myrtia-traces"
    assert traces["Overview"] == "/d/myrtia-overview/myrtia-overview"
    assert overview["Open Myrtia"] == traces["Open Myrtia"] == "__MYRTIA_URL__"
