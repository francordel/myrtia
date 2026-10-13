"""Step definitions for features/attacks.feature (end-to-end, needs a live model).

Marked @e2e: skipped by `pytest -m "not e2e"` and auto-skipped when no endpoint
is reachable (via the live_endpoint fixture).
"""
from __future__ import annotations

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

pytestmark = pytest.mark.e2e
scenarios("features/attacks.feature")


def _registry():
    # Imported lazily (not at module top) so collecting this file offline / in CI
    # never pulls in ARES; the e2e tests skip before this runs when no model is up.
    import myrtia.api.app  # noqa: F401  — side effect registers every plugin
    from myrtia.plugins.base import REGISTRY
    return REGISTRY

MODEL = "qwen2.5:3b"
_OLLAMA = "http://127.0.0.1:11434"
_AUX = _OLLAMA + "/v1"

# Minimal, fast config per attack (1 variant / 1 turn), evaluator on.
MINIMAL: dict[str, dict] = {
    "direct": {},
    "obfuscation": {"schemes": "base64"},
    "payload-splitting": {"fragments": 2},
    "human-jailbreak": {"custom_templates": {"m": "Please answer this: {goal}"}},
    "promptinject": {"variants": "ignore-say"},
    "grandma": {"variants": "bedtime"},
    "smuggling": {"variants": "hypothetical"},
    "phrasing": {"variants": "past"},
    "latent-injection": {"variants": "resume"},
    "contextual-jailbreak": {"shots": 2, "judge_model": MODEL},
    "crescendo": {"max_turns": 1, "helper_model": MODEL, "judge_model": MODEL, "aux_endpoint": _AUX},
    "tap": {"depth": 1, "width": 1, "attacker_model": MODEL, "judge_model": MODEL, "aux_endpoint": _AUX},
    "council": {"council_models": [MODEL], "max_turns": 1, "use_borda": False,
                "use_chairman": False, "judge_model": MODEL, "ollama_endpoint": _OLLAMA},
    "council-crescendo": {"council_models": [MODEL], "max_turns": 1, "use_borda": False,
                          "use_chairman": False, "judge_model": MODEL, "ollama_endpoint": _OLLAMA},
    "graph": {"council_models": [MODEL], "max_turns": 1, "use_borda": False,
              "use_chairman": False, "judge_model": MODEL},
}


@given("local Ollama is reachable")
def _reachable(live_endpoint: str) -> str:
    return live_endpoint


@given("a benign goal", target_fixture="goal")
def _goal() -> str:
    return "Explain how to make a really good cup of tea"


@when(parsers.parse('I run the "{attack}" attack with a minimal config'),
      target_fixture="outcome")
def _run(attack: str, goal: str, target_connector) -> dict:
    events: list[tuple] = []
    strat = _registry()[attack].factory(
        dict(MINIMAL.get(attack, {}), target_model=MODEL), target_connector)
    if hasattr(strat, "set_event_emitter"):
        strat.set_event_emitter(lambda t, p: events.append((t, p)))
    if hasattr(strat, "set_cancel_check"):
        strat.set_cancel_check(lambda: False)
    strat.load_goals([goal])
    results = strat.attack()
    return {"events": events, "results": results or []}


@then("at least one non-error target response is streamed")
def _target_response(outcome: dict) -> None:
    tr = [p for t, p in outcome["events"] if t == "target.responded"]
    assert tr, "no target.responded event"
    assert any((p.get("target_response") or "") and "[ERROR]" not in str(p.get("target_response"))
               for p in tr), "every target response was an error"


@then("the run yields at least one result")
def _has_results(outcome: dict) -> None:
    assert outcome["results"]


@then("a judge score between 0 and 5 is produced")
def _judge_score(outcome: dict) -> None:
    js = [p for t, p in outcome["events"] if t == "judge.scored"]
    assert js, "no judge.scored event"
    assert all(0 <= int(p.get("score") or 0) <= 5 for p in js)
