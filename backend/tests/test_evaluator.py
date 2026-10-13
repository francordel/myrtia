"""Step definitions for features/evaluator.feature (offline, no network)."""
from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from myrtia.judges.graded import GradedJudge, judge_from_config, parse_score

scenarios("features/evaluator.feature")


# --- parsing a judge reply ------------------------------------------------
@given(parsers.re(r"a judge reply '(?P<reply>.*)'"), target_fixture="reply")
def _reply(reply: str) -> str:
    return reply


@when("I parse the score", target_fixture="parsed")
def _parse(reply: str) -> int:
    score, _ = parse_score(reply)
    return score


@then(parsers.parse("the score is {expected:d}"))
def _score_is(parsed: int, expected: int) -> None:
    assert parsed == expected


# --- building the evaluator from config -----------------------------------
@given("an attack config with no evaluator model", target_fixture="config")
def _cfg_default() -> dict:
    return {}


@given(parsers.parse('an attack config with evaluator model "{model}"'),
       target_fixture="config")
def _cfg_model(model: str) -> dict:
    return {"judge_model": model}


@when("I build the evaluator from the config", target_fixture="evaluator")
def _build(config: dict):
    return judge_from_config(config)


@then("an evaluator is created")
def _created(evaluator) -> None:
    assert isinstance(evaluator, GradedJudge)


@then("no evaluator is created")
def _not_created(evaluator) -> None:
    assert evaluator is None
