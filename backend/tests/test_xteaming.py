"""Step definitions for features/xteaming.feature (offline: stub connectors, no network).

The planner, attacker and verifier are replaced by stub connectors dispatched by model
name; the target is a stub that echoes a fixed reply. Nothing touches the network or a
live model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/xteaming.feature")

REPO = Path(__file__).resolve().parents[2]
PLANNER, ATTACKER, JUDGE = "planner-m", "attacker-m", "judge-m"


class _Resp:
    def __init__(self, ok: bool, text: str = "", error: str = "") -> None:
        from myrtia.connectors.base import Status
        self.status = Status.SUCCESS if ok else Status.ERROR
        self.response = text
        self.error_message = error


class _Stub:
    """A stub connector whose reply depends on the role it was built for."""

    def __init__(self, role: str, world: dict) -> None:
        self.role = role
        self.world = world
        self.model = role

    def generate(self, prompt: Any, **_kw: Any) -> _Resp:
        w = self.world
        if self.role == PLANNER:
            plan = w["plan"]
            return _Resp(True, json.dumps(plan) if plan is not None else "no plan here")
        if self.role == JUDGE:
            if w.get("verifier_error"):
                return _Resp(False, error="connection refused")
            score = w["scores"].pop(0) if w["scores"] else 0
            return _Resp(True, json.dumps({"score": score, "rationale": "stub"}))
        # attacker / optimizer
        msg = w["messages"].pop(0) if w["messages"] else "attacker message"
        return _Resp(True, json.dumps({"message": msg, "rationale": "stub"}))


@pytest.fixture()
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    w: dict[str, Any] = {"plan": None, "scores": [], "messages": [], "verifier_error": False,
                         "events": [], "cancel_after_turn": None, "target_calls": 0}

    def fake_build(spec: dict) -> Any:
        return _Stub(spec.get("model", ""), w)

    monkeypatch.setattr("myrtia.connectors.factory.build_target_connector", fake_build)
    return w


class _Target:
    def __init__(self, world: dict) -> None:
        self.world = world

    def generate(self, prompt: Any, **_kw: Any) -> _Resp:
        self.world["target_calls"] += 1
        return _Resp(True, "target reply")


def _plan(phases: int) -> dict:
    return {"plans": [{"persona": "an analyst", "context": "a review", "approach": "scenario",
                       "phases": [f"phase {i + 1}" for i in range(phases)]}]}


def _strategy(world: dict, **cfg: Any) -> Any:
    from myrtia.plugins.xteaming import XTeamingLive
    config = {"planner_model": PLANNER, "attacker_model": ATTACKER, "judge_model": JUDGE,
              "n_plans": 1, "n_execute": 1, **cfg}
    s = XTeamingLive(config, _Target(world))

    def emit(etype: str, payload: dict) -> None:
        world["events"].append((etype, payload))

    s.set_event_emitter(emit)
    s.load_goals(["say the forbidden thing"])
    world["strategy"] = s
    return s


def _events(world: dict, etype: str) -> list[dict]:
    return [p for t, p in world["events"] if t == etype]


# --- discovery ----------------------------------------------------------------
@when(parsers.parse('I look up the "{plugin}" plugin'), target_fixture="spec")
def _lookup(plugin: str) -> Any:
    import myrtia.api.app  # noqa: F401 - registers every plugin
    from myrtia.plugins.base import REGISTRY
    return REGISTRY.get(plugin)


@then("it is registered")
def _registered(spec: Any) -> None:
    assert spec is not None and spec.id == "xteaming"


@then("it has a description, a paper reference and how-it-works steps")
def _described(spec: Any) -> None:
    assert spec.description and spec.paper and spec.how
    assert "2504.13203" in spec.paper


@then("its configuration offers n_plans, n_execute, max_turns, success_score and opt_budget")
def _schema(spec: Any) -> None:
    keys = {f["key"] for f in spec.config_schema}
    assert {"n_plans", "n_execute", "max_turns", "success_score", "opt_budget"} <= keys


# --- running a plan -----------------------------------------------------------
@given(parsers.parse("an X-Teaming attack whose planner returns {n:d} plan of {p:d} phases"))
def _attack(world: dict, n: int, p: int) -> None:
    world["plan"] = _plan(p)
    _strategy(world)


@given(parsers.parse("an X-Teaming attack whose planner returns {n:d} plan of {p:d} phase"))
def _attack1(world: dict, n: int, p: int) -> None:
    world["plan"] = _plan(p)
    _strategy(world)


@given("an X-Teaming attack whose planner returns nothing usable")
def _attack_bad(world: dict) -> None:
    world["plan"] = None
    _strategy(world)


@given(parsers.parse("the verifier scores the turns {a:d} then {b:d}"))
def _scores2(world: dict, a: int, b: int) -> None:
    world["scores"] = [a, b]


@given(parsers.parse("the verifier scores the turns {a:d}"))
def _scores1(world: dict, a: int) -> None:
    world["scores"] = [a]


@given(parsers.parse("the verifier scores the turns {a:d} then {b:d}, then the optimized message scores {c:d}"))
def _opt_scores(world: dict, a: int, b: int, c: int) -> None:
    world["scores"] = [a, b, c]


@given(parsers.parse("the optimizer budget is {n:d}"))
def _budget(world: dict, n: int) -> None:
    world["strategy"].opt_budget = n


@given("the verifier endpoint is unreachable")
def _verifier_down(world: dict) -> None:
    world["verifier_error"] = True
    world["scores"] = [5]  # would succeed if it were reachable


@given("the run is cancelled after the first turn")
def _cancel(world: dict) -> None:
    world["scores"] = [1, 1, 1]  # never a success, so only cancellation stops it

    def cancelled() -> bool:
        return world["target_calls"] >= 1  # stop once the first turn has happened

    world["strategy"].set_cancel_check(cancelled)


@when("the attack runs against a stub target")
def _run(world: dict) -> None:
    world["results"] = world["strategy"].attack()


@then("the goal is reported as succeeded")
def _succeeded(world: dict) -> None:
    assert world["results"][0]["success"] is True


@then("the goal is reported as not succeeded")
def _not_succeeded(world: dict) -> None:
    assert world["results"][0]["success"] is False


@then(parsers.parse("the best score is {n:d}"))
def _best(world: dict, n: int) -> None:
    assert world["results"][0]["score"] == n


@then(parsers.parse("{n:d} turns were used"))
def _turns(world: dict, n: int) -> None:
    assert world["results"][0]["turns_used"] == n


@then("the planner's plan was emitted as an agent message")
def _plan_emitted(world: dict) -> None:
    msgs = _events(world, "agent.message")
    assert any(m.get("sender") == "planner" for m in msgs)


@then(parsers.parse("there were {a:d} attacker proposals, {b:d} target replies and {c:d} scores"))
def _counts(world: dict, a: int, b: int, c: int) -> None:
    assert len(_events(world, "proposal.created")) == a
    assert len(_events(world, "target.responded")) == b
    assert len(_events(world, "judge.scored")) == c


@then("the attacker message was optimized before the goal was reached")
def _optimized(world: dict) -> None:
    assert any(p.get("optimized") for p in _events(world, "proposal.created"))


@then("the attack still ran one plan against the target")
def _ran_one(world: dict) -> None:
    assert world["target_calls"] >= 1


@then("the attack stopped early and returned a result for the goal")
def _stopped(world: dict) -> None:
    assert len(world["results"]) == 1
    assert world["target_calls"] <= 2  # did not run all three phases


# --- content and safety -------------------------------------------------------
@when("the default role prompts are loaded", target_fixture="prompts")
def _load_defaults() -> dict:
    from myrtia.plugins import xteaming_prompts
    return xteaming_prompts.load()


@then("there are prompts for the planner, attacker, verifier and optimizer")
def _four(prompts: dict) -> None:
    keys = ("planner_system", "attacker_system", "verifier_system", "optimizer_user")
    assert set(keys) <= set(prompts)
    assert all(prompts[k].strip() for k in keys)


@then("none of them contains a worked harmful exemplar")
def _no_exemplar(prompts: dict) -> None:
    for text in prompts.values():
        low = text.lower()
        # the repo's worked-exemplar markers (see council_official.py)
        assert "[system]" not in low and "template (send this" not in low
        assert "goal:" not in low


@given(parsers.parse('a private prompt file that sets the planner prompt to "{value}"'))
def _private_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str) -> None:
    f = tmp_path / "xteaming.private.yaml"
    f.write_text(f'planner_system: "{value}"\n')
    monkeypatch.setenv("MYRTIA_XTEAMING_PROMPTS_FILE", str(f))


@given("the private prompt file is set to a path that does not exist")
def _missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MYRTIA_XTEAMING_PROMPTS_FILE", str(tmp_path / "nope.yaml"))


@when("the role prompts are loaded", target_fixture="prompts")
def _load() -> dict:
    from myrtia.plugins import xteaming_prompts
    return xteaming_prompts.load()


@then(parsers.parse('the planner prompt is "{value}"'))
def _planner_is(prompts: dict, value: str) -> None:
    assert prompts["planner_system"] == value


@then("the planner prompt is the committed default")
def _planner_default(prompts: dict) -> None:
    from myrtia.plugins import xteaming_prompts
    assert prompts["planner_system"] == xteaming_prompts.TEMPLATES["planner_system"]


# --- provenance ---------------------------------------------------------------
@then("the third-party notices record X-Teaming as reimplemented from the paper")
def _notices() -> None:
    text = (REPO / "THIRD_PARTY_NOTICES.md").read_text().lower()
    assert "x-teaming" in text and "2504.13203" in text and "reimplement" in text


@then("they state that the upstream repository carries no licence and is not used")
def _no_licence() -> None:
    text = (REPO / "THIRD_PARTY_NOTICES.md").read_text().lower()
    assert "no licence" in text or "no license" in text or "unlicensed" in text
