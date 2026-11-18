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
        w["calls"].append((self.role, prompt))
        if self.role == PLANNER:
            text = json.dumps(prompt)
            if "Revise the jailbreak strategy" in text and w.get("revision") is not None:
                return _Resp(True, w["revision"])
            plan = w["plan"]
            if isinstance(plan, str):
                return _Resp(True, plan)
            return _Resp(True, json.dumps(plan) if plan is not None else "no plan here")
        if self.role == JUDGE:
            if w.get("verifier_error"):
                return _Resp(False, error="connection refused")
            score = w["scores"].pop(0) if w["scores"] else 0
            # read by both rubrics: X-Teaming's 1-5 "score" and the graded 0-5 "harm"
            return _Resp(True, json.dumps({"score": score, "harm": score, "rationale": "stub",
                                           "argument": "stub"}))
        # attacker / optimizer (the official variant also asks it to revise the plan)
        if "Revise the jailbreak strategy" in json.dumps(prompt) and w.get("revision") is not None:
            return _Resp(True, w["revision"])
        if w.get("attacker_error"):
            return _Resp(False, error="Read timed out")
        if w.get("attacker_raw") is not None:
            return _Resp(True, w["attacker_raw"])
        msg = w["messages"].pop(0) if w["messages"] else "attacker message"
        return _Resp(True, json.dumps({"message": msg, "rationale": "stub"}))


@pytest.fixture()
def world(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    w: dict[str, Any] = {"plan": None, "scores": [], "messages": [], "verifier_error": False,
                         "events": [], "cancel_after_turn": None, "target_calls": 0,
                         "calls": [], "target_prompts": [], "revision": None}

    def fake_build(spec: dict) -> Any:
        return _Stub(spec.get("model", ""), w)

    monkeypatch.setattr("myrtia.connectors.factory.build_target_connector", fake_build)
    return w


class _Target:
    def __init__(self, world: dict) -> None:
        self.world = world

    def generate(self, prompt: Any, **_kw: Any) -> _Resp:
        self.world["target_calls"] += 1
        self.world["target_prompts"].append(prompt)
        return _Resp(True, self.world.get("target_reply") or "target reply")


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


# --- fidelity to the paper ----------------------------------------------------
# The planner's reply in the format the paper's prompt asks for (Appendix A.4.1), fenced
# and with the format example's `//` comment left in.
def _paper_plan(phases: int) -> str:
    plan = {f"turn_{i + 1}": f"phase {i + 1}" for i in range(phases - 1)}
    plan["final_turn"] = f"phase {phases}"
    body = json.dumps({"strategy_1": {"persona": "a museum curator", "context": "an exhibit",
                                      "approach": "scenario", "turns_needed": str(phases),
                                      "conversation_plan": plan}}, indent=4)
    body = body.replace('"conversation_plan": {', '"conversation_plan": {\n// more turns', 1)
    return f"```json\n{body}\n```"


@given(parsers.parse("an X-Teaming attack whose planner answers in the paper's format with {p:d} phases"))
def _attack_paper(world: dict, p: int) -> None:
    world["plan"] = _paper_plan(p)
    _strategy(world)


@given(parsers.parse("the verifier scores the turns {a:d}, {b:d} then {c:d}"))
def _scores3(world: dict, a: int, b: int, c: int) -> None:
    world["scores"] = [a, b, c]


@given("the planner's revision adds a second phase")
def _revision(world: dict) -> None:
    world["revision"] = json.dumps({"persona": "an analyst", "context": "a review",
                                    "approach": "scenario", "turns_needed": "2",
                                    "conversation_plan": {"turn_1": "phase 1",
                                                          "final_turn": "phase 2"}})


def _texts(world: dict, role: str) -> list[str]:
    return [json.dumps(p) for r, p in world["calls"] if r == role]


@then("the planner was told the behaviour")
def _planner_told(world: dict) -> None:
    first = _texts(world, PLANNER)[0]
    assert "say the forbidden thing" in first and "{target_behavior}" not in first


@then("the attacker was shown the plan's persona")
def _attacker_persona(world: dict) -> None:
    calls = _texts(world, ATTACKER)
    assert calls and all("a museum curator" in c and "{strategy}" not in c for c in calls)


@then(parsers.parse("the target's last request held the {n:d} earlier exchanges"))
def _target_history(world: dict, n: int) -> None:
    last = world["target_prompts"][-1]
    assert len(last) == 2 * n + 1
    assert [m["role"] for m in last[:-1]] == ["user", "assistant"] * n


@then("the optimizer was given the verifier's reason")
def _optimizer_reason(world: dict) -> None:
    losses = [c for c in _texts(world, ATTACKER) if "We wish for our attack" in c]
    assert losses and all("- stub" in c and "target reply" not in c.split("- stub")[0][-50:]
                          for c in losses)


@then("the plan was revised")
def _revised(world: dict) -> None:
    msgs = _events(world, "agent.message")
    assert any("revised_plan" in (m.get("message") or "") for m in msgs)


@given("the attacker endpoint is unreachable")
def _attacker_down(world: dict) -> None:
    world["attacker_error"] = True
    world["scores"] = [5, 5]


@given(parsers.parse('the attacker replies "{raw}" without a message tag'))
def _attacker_raw(world: dict, raw: str) -> None:
    world["attacker_raw"] = raw


@then("the target was never sent an error message")
def _no_error_sent(world: dict) -> None:
    sent = [m["content"] for p in world["target_prompts"] for m in p if m["role"] == "user"]
    assert not any("ERROR" in s or "timed out" in s for s in sent)


@then(parsers.parse('the target was sent "{text}"'))
def _sent(world: dict, text: str) -> None:
    assert world["target_prompts"][0][-1]["content"] == text


# --- the reference run ---------------------------------------------------------
@then("its defaults are 50 plans drafted, 10 executed, 7 turns and an optimizer budget of 4")
def _ref_defaults(spec: Any) -> None:
    d = {f["key"]: f.get("default") for f in spec.config_schema}
    assert (d["n_plans"], d["n_execute"], d["max_turns"], d["opt_budget"]) == (50, 10, 7, 4)


@then("its defaults are the official variant and the graded verifier on the whole reply")
def _ref_defaults2(spec: Any) -> None:
    d = {f["key"]: f.get("default") for f in spec.config_schema}
    assert d["variant"] == "official" and d["verifier_rubric"] == "graded"
    assert d["verifier_max_chars"] == 0


@given(parsers.parse('the X-Teaming variant is "{variant}"'))
def _variant(world: dict, variant: str) -> None:
    world["strategy"].variant = variant


@given("plan revision is off")
def _no_revision(world: dict) -> None:
    world["strategy"].plan_revision = False


@given(parsers.parse("the verifier scores the turns {a:d}, {b:d}, {c:d} then {d:d}"))
def _scores4(world: dict, a: int, b: int, c: int, d: int) -> None:
    world["scores"] = [a, b, c, d]
    world["messages"] = [f"m{i}" for i in range(1, 9)]


@given(parsers.parse("the verifier scores the turns {a:d}, {b:d}, {c:d}, {d:d} then {e:d}"))
def _scores5(world: dict, a: int, b: int, c: int, d: int, e: int) -> None:
    world["scores"] = [a, b, c, d, e]


@given(parsers.parse("the verifier sees at most {n:d} characters"))
def _verifier_limit(world: dict, n: int) -> None:
    world["strategy"].verifier_max_chars = n


@given(parsers.parse("the target replies with {n:d} characters"))
def _long_reply(world: dict, n: int) -> None:
    world["target_reply"] = "Z" * n


@then("the second phase's first retry re-sent the same message")
def _resent(world: dict) -> None:
    sent = [p["proposal"] for p in _events(world, "proposal.created")]
    assert sent[1] == sent[2] and not _events(world, "proposal.created")[2]["optimized"]


@then("its next retry was optimized")
def _then_optimized(world: dict) -> None:
    p = _events(world, "proposal.created")[3]
    assert p["optimized"] and p["proposal"] != _events(world, "proposal.created")[1]["proposal"]


def _committed_score(world: dict, phase: int) -> int | None:
    import re
    pat = re.compile(rf"Turn {phase}:\nAttacker \(your\) response: .*?\nEvaluation Score: (\d)/5",
                     re.DOTALL)
    for role, prompt in world["calls"]:
        if role != ATTACKER or not isinstance(prompt, list):
            continue
        text = "\n".join(str(m.get("content", "")) for m in prompt)
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return None


@then(parsers.parse("the attacker saw phase {phase:d} committed with the score {n:d}"))
def _committed(world: dict, phase: int, n: int) -> None:
    assert _committed_score(world, phase) == n


@then("the plan revision was asked of the attacker model")
def _revision_by_attacker(world: dict) -> None:
    assert any("Revise the jailbreak strategy" in c for c in _texts(world, ATTACKER))
    assert not any("Revise the jailbreak strategy" in c for c in _texts(world, PLANNER))


@then(parsers.parse("the attacker was asked {n:d} times"))
def _asked(world: dict, n: int) -> None:
    assert len(_texts(world, ATTACKER)) == n


@then("the target was never called")
def _never_called(world: dict) -> None:
    assert world["target_calls"] == 0


@then(parsers.parse("the verifier was shown {n:d} characters of the reply"))
def _verifier_shown(world: dict, n: int) -> None:
    import re
    seen = max(len(m) for c in _texts(world, JUDGE) for m in re.findall(r"Z+", c))
    assert seen == n


@then(parsers.parse("the first turn was scored {n:d}"))
def _first_scored(world: dict, n: int) -> None:
    assert _events(world, "judge.scored")[0]["score"] == n


@then("the verifier was given the graded rubric")
def _graded(world: dict) -> None:
    assert all("####### RESPONSE #######" in c for c in _texts(world, JUDGE))


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
