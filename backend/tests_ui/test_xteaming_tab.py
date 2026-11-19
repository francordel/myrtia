"""Steps for features/xteaming_tab.feature: the X-Teaming run-mode tab (spec 012)."""
from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/xteaming_tab.feature")


@given("the Myrtia console is open", target_fixture="ui")
def _console(console_page: Any) -> Any:
    return console_page


@when("I open the X-Teaming run mode")
def _open(ui: Any) -> None:
    ui.get_by_role("tab", name="X-Teaming").click()


@then(parsers.parse('the attack is set to "{plugin}"'))
def _attack(ui: Any, plugin: str) -> None:
    assert ui.locator("#attack").input_value() == plugin


@then("its description mentions X-Teaming")
def _desc(ui: Any) -> None:
    assert "X-Teaming" in ui.locator("#attackdesc").inner_text()


@then("the attack-plugin selector is hidden")
def _selector_hidden(ui: Any) -> None:
    assert not ui.locator("#attackRow").is_visible()


@then("the graph canvas is hidden")
def _canvas_hidden(ui: Any) -> None:
    assert not ui.locator("#agenticPane").is_visible()
