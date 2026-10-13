"""Step definitions for features/encodings.feature (offline, no network)."""
from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from myrtia.plugins.obfuscation import _encode

scenarios("features/encodings.feature")


@given(parsers.parse('a goal "{text}"'), target_fixture="goal")
def _goal(text: str) -> str:
    return text


@when(parsers.parse('I encode it with the "{scheme}" scheme'), target_fixture="encoded")
def _do_encode(goal: str, scheme: str) -> dict:
    enc, prompt = _encode(goal, scheme)
    return {"enc": enc, "prompt": prompt}


@then("the encoded text is not empty")
def _not_empty(encoded: dict) -> None:
    assert encoded["enc"]


@then("the encoded text differs from the goal")
def _differs(encoded: dict, goal: str) -> None:
    assert encoded["enc"] != goal


@then("the prompt asks the target to decode and comply")
def _decode_prompt(encoded: dict) -> None:
    assert "decode" in encoded["prompt"].lower()
    assert encoded["enc"] in encoded["prompt"]


@then("the encoded text equals the goal")
def _equals(encoded: dict, goal: str) -> None:
    assert encoded["enc"] == goal
