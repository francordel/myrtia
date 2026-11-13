"""Step definitions for features/observability.feature (offline, no network).

Model endpoints are replaced by a stub of ``requests.post``; runs are driven through the
real orchestrator with an in-memory bus and store, so nothing touches the operator's
database.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from starlette.testclient import TestClient

scenarios("features/observability.feature")

REPO = Path(__file__).resolve().parents[2]
ENDPOINT = "http://127.0.0.1:9/v1"
TOKEN = "obs-test-token"
SECRET_KEY = "sk-obs-secret-0123456789"
SECRET_HEADER = "X-Obs-Secret-Header"
SECRET_PROMPT = "obs-prompt-that-must-not-leak"

_SAMPLE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(.*)\})? (\S+)$")
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def samples(text: str) -> list[tuple[str, dict[str, str], float]]:
    """Parse Prometheus text into (name, labels, value) triples."""
    out = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        assert m, f"not a valid sample line: {line!r}"
        out.append((m.group(1), dict(_LABEL.findall(m.group(2) or "")), float(m.group(3))))
    return out


def value(name: str, **labels: str) -> float:
    """Sum of the samples of `name` whose labels include `labels` (0 when none)."""
    from myrtia import telemetry
    return sum(v for n, ls, v in samples(telemetry.render())
               if n == name and all(ls.get(k) == w for k, w in labels.items()))


def names_present() -> set[str]:
    from myrtia import telemetry
    return {n for n, _, _ in samples(telemetry.render())}


class _HTTP:
    def __init__(self, status: int, body: dict | None) -> None:
        self.status_code = status
        self._body = body
        self.text = json.dumps(body) if body is not None else "boom"

    def json(self) -> dict:
        if self._body is None:
            raise ValueError("no json")
        return self._body


@pytest.fixture()
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Per-scenario state; the model endpoint is a stub that records what it was sent."""
    w: dict[str, Any] = {"reply": _HTTP(200, {"choices": [{"message": {"content": "hi"}}]}),
                         "sent": []}

    def fake_post(url: str, **kwargs: Any) -> _HTTP:
        w["sent"].append((url, kwargs))
        return w["reply"]

    import myrtia.connectors.base as base
    monkeypatch.setattr(base.requests, "post", fake_post)
    return w


def _connector(role: str, model: str, **extra: Any):
    from myrtia.connectors.factory import build_target_connector
    spec = {"kind": "openai_chat", "base_url": ENDPOINT, "model": model, **extra}
    if role != "default":
        spec["role"] = role
    return build_target_connector(spec)


# --- background ---------------------------------------------------------------
@given("a clean metrics registry")
def _clean(world: dict) -> None:
    from myrtia import telemetry
    telemetry.reset()


# --- metrics address ----------------------------------------------------------
def _client() -> TestClient:
    import myrtia.api.app as appmod
    return TestClient(appmod.app)


@given(parsers.parse('the access token "{token}" is configured'))
def _token(monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    import myrtia.api.deps as deps
    monkeypatch.setattr(deps, "_ACCESS_TOKEN", token)


@when("I request the metrics address", target_fixture="reply")
def _get() -> Any:
    return _client().get("/metrics")


@when("I request the metrics address with the token as a bearer credential",
      target_fixture="reply")
def _get_bearer() -> Any:
    return _client().get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})


@when("I request the metrics address with the token as a query parameter",
      target_fixture="reply")
def _get_query() -> Any:
    return _client().get("/metrics", params={"token": TOKEN})


@then(parsers.parse("the reply status is {status:d}"))
def _status(reply: Any, status: int) -> None:
    assert reply.status_code == status


@then("the reply is Prometheus text")
def _is_text(reply: Any) -> None:
    assert reply.headers["content-type"].startswith("text/plain; version=0.0.4")
    samples(reply.text)  # every non-comment line parses


@then(parsers.parse('the reply documents the metric "{name}" as a "{kind}"'))
def _documented(reply: Any, name: str, kind: str) -> None:
    assert f"# HELP {name} " in reply.text
    assert f"# TYPE {name} {kind}\n" in reply.text


@then("the reply reports the build version")
def _build(reply: Any) -> None:
    from myrtia.api.deps import APP_VERSION
    assert f'myrtia_build_info{{version="{APP_VERSION}"}} 1' in reply.text


# --- model calls --------------------------------------------------------------
@given(parsers.parse('a "{role}" connector for model "{model}"'), target_fixture="conn")
def _conn(world: dict, role: str, model: str) -> Any:
    return _connector(role, model)


@given(parsers.parse("the model replies with {p:d} prompt tokens and {c:d} completion tokens"))
def _usage(world: dict, p: int, c: int) -> None:
    world["reply"] = _HTTP(200, {"choices": [{"message": {"content": "hi"}}],
                                 "usage": {"prompt_tokens": p, "completion_tokens": c,
                                           "total_tokens": p + c}})


@given("the model replies without usage data")
def _no_usage(world: dict) -> None:
    world["reply"] = _HTTP(200, {"choices": [{"message": {"content": "hi"}}]})


@given("the model endpoint answers with an HTTP error")
def _http_error(world: dict) -> None:
    world["reply"] = _HTTP(500, None)


@when("the connector is called once", target_fixture="result")
def _call(conn: Any) -> Any:
    return conn.generate("hello")


@when(parsers.parse('the connector is called once as "{role}"'), target_fixture="result")
def _call_as(conn: Any, role: str) -> Any:
    return conn.generate("hello", role=role)


@then(parsers.parse('the metrics count {n:d} "{outcome}" call for role "{role}" and model "{model}"'))
def _calls(n: int, outcome: str, role: str, model: str) -> None:
    assert value("myrtia_model_calls_total", role=role, model=model, outcome=outcome) == n
    assert value("myrtia_model_calls_total", model=model) == n  # and under no other label


@then(parsers.parse('the metrics count {n:d} "{kind}" tokens for role "{role}"'))
def _tokens(n: int, kind: str, role: str) -> None:
    assert value("myrtia_model_tokens_total", role=role, kind=kind) == n


@then("the metrics hold no tokens")
def _no_tokens() -> None:
    assert value("myrtia_model_tokens_total") == 0


@then(parsers.parse('the latency distribution for role "{role}" holds {n:d} observation'))
def _latency(role: str, n: int) -> None:
    assert value("myrtia_model_call_duration_seconds_count", role=role) == n
    assert value("myrtia_model_call_duration_seconds_bucket", role=role, le="+Inf") == n
    assert value("myrtia_model_call_duration_seconds_sum", role=role) >= 0


@when("the graded judge, a shield's helper and a graph attacker each call their model")
def _real_callers(world: dict) -> None:
    from myrtia.defenses import DefendedConnector
    from myrtia.judges.graded import GradedJudge
    from myrtia.plugins.graph import GraphAttack

    GradedJudge(model="m-judge", endpoint=ENDPOINT).score("goal", "response")
    DefendedConnector(object(), [], aux_model="m-shield", aux_endpoint=ENDPOINT)._aux()("x")
    graph = GraphAttack({"mode": "pipeline", "max_turns": 1, "evaluator": {"model": "off"},
                         "agents": [{"role": "attacker", "model": "m-agent",
                                     "endpoint": ENDPOINT}]}, object())
    graph._agent_generate(graph.agents[0], "system", "user")


# --- runs and events ----------------------------------------------------------
def _event(run_id: str, type_: str, **payload: Any) -> None:
    from myrtia import telemetry
    from myrtia.events.schema import Event, EventType
    telemetry.observe_event(Event(run_id=run_id, type=EventType(type_), payload=payload))


@given(parsers.parse('the run "{run_id}" of attack "{attack}" has started'))
@when(parsers.parse('the run "{run_id}" of attack "{attack}" starts'))
def _start(run_id: str, attack: str) -> None:
    _event(run_id, "run.started", spec={"attack_id": attack})


@when(parsers.parse('the run "{run_id}" finishes with status "{status}"'))
def _finish(run_id: str, status: str) -> None:
    _event(run_id, "run.finished", status=status)


@then(parsers.re(r'(?P<n>\d+) runs? of attack "(?P<attack>[^"]+)" (?:is|are) active'))
def _active(n: str, attack: str) -> None:
    assert value("myrtia_runs_active", attack=attack) == int(n)


@then(parsers.parse('the metrics count {n:d} started run of attack "{attack}"'))
def _started(n: int, attack: str) -> None:
    assert value("myrtia_runs_started_total", attack=attack) == n


@then(parsers.parse('the metrics count {n:d} finished run of attack "{attack}" with status "{status}"'))
def _finished(n: int, attack: str, status: str) -> None:
    assert value("myrtia_runs_finished_total", attack=attack, status=status) == n


@then(parsers.parse('the run duration distribution for attack "{attack}" holds {n:d} observation'))
def _run_duration(attack: str, n: int) -> None:
    assert value("myrtia_run_duration_seconds_count", attack=attack) == n


@then("no attack has a negative number of active runs")
def _not_negative() -> None:
    from myrtia import telemetry
    assert all(v >= 0 for n, _, v in samples(telemetry.render()) if n == "myrtia_runs_active")


@when(parsers.parse('the judge scores 5, 5, 2 and 9 in run "{run_id}"'))
def _scores(run_id: str) -> None:
    for s in (5, 5, 2, 9):
        _event(run_id, "judge.scored", score=s, rationale="because", model="j")


@then(parsers.parse('the metrics count {n:d} verdicts with score "{score}" for attack "{attack}"'))
def _verdicts(n: int, score: str, attack: str) -> None:
    assert value("myrtia_judge_scores_total", attack=attack, score=score) == n


@when(parsers.parse('the shield "{a}" is applied and the shield "{b}" blocks'))
def _shields(a: str, b: str) -> None:
    _event("r1", "defense.applied", id=a, name=a, stage="input", note="n")
    _event("r1", "defense.blocked", id=b, name=b, stage="input", reason="r")


@then(parsers.parse('the metrics count {n:d} "{action}" action of shield "{shield}"'))
def _shield_count(n: int, action: str, shield: str) -> None:
    assert value("myrtia_defense_actions_total", defense=shield, action=action) == n


@when(parsers.parse('a "{type_}" event is published on the event bus twice'))
def _publish(monkeypatch: pytest.MonkeyPatch, type_: str) -> None:
    from myrtia.events.bus import BUS
    from myrtia.events.schema import Event, EventType
    from myrtia.store import db
    monkeypatch.setattr(db, "append_event", lambda *a, **k: None)  # keep the DB untouched
    for _ in range(2):
        BUS.publish(Event(run_id="obs-bus-run", type=EventType(type_), payload={}))


@then(parsers.parse('the metrics count {n:d} events of type "{type_}"'))
def _events(n: int, type_: str) -> None:
    assert value("myrtia_events_total", type=type_) == n


# --- per-run series -----------------------------------------------------------
class _MemBus:
    def publish(self, event: Any) -> Any:
        from myrtia import telemetry
        telemetry.observe_event(event)
        return event


class _MemStore:
    def persist(self, run: Any) -> None:
        pass


@given("a plugin whose attack calls the target once")
def _plugin() -> Any:
    from myrtia.plugins.base import REGISTRY, PluginSpec

    class Once:
        def __init__(self, config: dict, target: Any) -> None:
            self.target = target

        def attack(self, **_kw: Any) -> list[dict]:
            self.target.generate("hello")
            return [{"goal": "g"}]

    REGISTRY["obs-once"] = PluginSpec("obs-once", Once)
    yield
    REGISTRY.pop("obs-once", None)


@when(parsers.parse('the orchestrator executes the run "{run_id}" with that plugin'))
def _execute(world: dict, run_id: str) -> None:
    from myrtia.orchestrator.runner import Orchestrator
    from myrtia.store.runs import Run, RunSpec, RunStatus
    run = Run(id=run_id, spec=RunSpec(
        attack_id="obs-once", goals=["g"],
        target={"kind": "openai_chat", "base_url": ENDPOINT, "model": "sim-target"}))
    asyncio.run(Orchestrator(bus=_MemBus(), store=_MemStore()).run(run))
    assert run.status == RunStatus.SUCCEEDED, run.error


@then(parsers.parse('the run "{run_id}" has {calls:d} call and {tokens:d} tokens for role "{role}"'))
def _run_series(run_id: str, calls: int, tokens: int, role: str) -> None:
    labels = {"run": run_id, "attack": "obs-once", "role": role}
    assert value("myrtia_run_model_calls_total", **labels) == calls
    assert value("myrtia_run_tokens_total", **labels) == tokens
    assert value("myrtia_run_model_seconds_total", **labels) >= 0
    assert "myrtia_run_model_seconds_total" in names_present()


@given(parsers.parse("the per-run limit is {n:d}"))
def _limit(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    from myrtia import telemetry
    monkeypatch.setattr(telemetry, "RUN_LIMIT", n)


@when('model calls are recorded for runs "r1", "r2" and "r3" in that order')
def _three_runs() -> None:
    from myrtia import telemetry
    for rid in ("r1", "r2", "r3"):
        _event(rid, "run.started", spec={"attack_id": "tap"})
        with telemetry.run_context(rid, "tap"):
            telemetry.record_model_call("target", "m", True, 0.1, 1, 1)
        _event(rid, "run.finished", status="succeeded")


def _runs_with_series() -> set[str]:
    from myrtia import telemetry
    return {ls["run"] for _, ls, _ in samples(telemetry.render()) if "run" in ls}


@then('the metrics hold per-run series for "r2" and "r3"')
def _kept() -> None:
    assert {"r2", "r3"} <= _runs_with_series()


@then('the metrics hold no per-run series for "r1"')
def _dropped() -> None:
    assert "r1" not in _runs_with_series()


@then("the metrics hold no per-run series at all")
def _none() -> None:
    assert _runs_with_series() == set()


# --- safety -------------------------------------------------------------------
@given("a connector with an API key, a custom auth header and an endpoint address",
       target_fixture="conn")
def _secret_conn(world: dict) -> Any:
    return _connector("target", "sim-model", api_key=SECRET_KEY, auth_header=SECRET_HEADER)


@when("the connector is called with a prompt", target_fixture="result")
def _call_prompt(world: dict, conn: Any) -> Any:
    r = conn.generate(SECRET_PROMPT)
    assert world["sent"][0][1]["headers"][SECRET_HEADER] == SECRET_KEY  # it was really used
    return r


@then("the metrics contain neither the key, the header, the address nor the prompt")
def _no_leak() -> None:
    from myrtia import telemetry
    text = telemetry.render()
    assert value("myrtia_model_calls_total", role="target") == 1
    for secret in (SECRET_KEY, SECRET_HEADER, "127.0.0.1", ENDPOINT, SECRET_PROMPT):
        assert secret not in text


@given("recording metrics fails")
def _broken(monkeypatch: pytest.MonkeyPatch) -> None:
    from myrtia import telemetry

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("metrics are down")

    monkeypatch.setattr(telemetry.METRICS, "inc", boom)


@then("the call still returns the model's reply")
def _still_ok(result: Any) -> None:
    from myrtia.connectors.base import Status
    assert result.status == Status.SUCCESS and result.response == "hi"


@when("a call is recorded for a model named with a quote, a backslash and a line break")
def _odd_name() -> None:
    from myrtia import telemetry
    telemetry.record_model_call("aux", 'we"ird\\na\nme', True, 0.1, 0, 0)


@then("the metrics text keeps one sample per line and escapes the name")
def _escaped() -> None:
    from myrtia import telemetry
    text = telemetry.render()
    samples(text)  # still parses line by line
    assert r'model="we\"ird\\na\nme"' in text


# --- dashboard and stack ------------------------------------------------------
@given("the provisioned dashboard", target_fixture="dashboard")
def _dashboard() -> dict:
    path = REPO / "observability" / "grafana" / "dashboards" / "myrtia-overview.json"
    return json.loads(path.read_text())


def _exprs(dashboard: dict) -> list[str]:
    out = [t["expr"] for p in dashboard["panels"] for t in p.get("targets", [])]
    out += [str(v.get("query", {}).get("query", "") if isinstance(v.get("query"), dict)
                else v.get("query", ""))
            for v in dashboard.get("templating", {}).get("list", [])]
    return out


@then("every metric it queries is exported by Myrtia")
def _in_sync(dashboard: dict) -> None:
    from myrtia import telemetry
    exported = telemetry.exported_names()
    used = {m for e in _exprs(dashboard) for m in re.findall(r"\bmyrtia_[a-z0-9_]+", e)}
    assert used, "the dashboard queries no Myrtia metric"
    assert used <= exported, f"not exported: {sorted(used - exported)}"


@then("it has panels for runs, tokens, latency, calls, judge scores, shields, events and one run")
def _panels(dashboard: dict) -> None:
    titles = " | ".join(p["title"].lower() for p in dashboard["panels"])
    for word in ("active runs", "finished runs", "tokens per minute", "latency",
                 "calls", "tokens by model", "judge score", "shield", "events per minute",
                 "selected run"):
        assert word in titles, f"no panel about {word!r}"
    assert any(v["name"] == "run" for v in dashboard["templating"]["list"])


@given("the observability Compose file", target_fixture="compose")
def _compose() -> str:
    return (REPO / "compose.observability.yaml").read_text()


@then("Grafana and the collector are published on the loopback address only")
def _loopback(compose: str) -> None:
    ports = re.findall(r'^\s*-\s*"([^"]*:\d+)"\s*$', compose, flags=re.M)
    assert len(ports) == 2, ports
    assert all(p.startswith("127.0.0.1:") for p in ports), ports


@then("Grafana is viewable without logging in and its login form is disabled")
def _anonymous(compose: str) -> None:
    assert 'GF_AUTH_ANONYMOUS_ENABLED: "true"' in compose
    assert "GF_AUTH_ANONYMOUS_ORG_ROLE: Viewer" in compose
    assert 'GF_AUTH_DISABLE_LOGIN_FORM: "true"' in compose


@then("Grafana sends no analytics and checks for no updates")
def _no_analytics(compose: str) -> None:
    assert 'GF_ANALYTICS_REPORTING_ENABLED: "false"' in compose
    assert 'GF_ANALYTICS_CHECK_FOR_UPDATES: "false"' in compose
