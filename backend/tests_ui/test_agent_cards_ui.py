"""Playwright UI scenarios for Agent Cards (Spec 002)."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, scenarios, then, when

scenarios("features/agent_cards.feature")

CANVAS = "#agenticPane"


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@given("attacker 1 has a custom prompt, a tool, and contextual priming configured")
@when("attacker 1 has a custom prompt, a tool, and contextual priming configured")
def configure_attacker_1(ui: Page) -> None:
    ui.evaluate(
        """() => {
            const a = GS.attackers[0];
            a.system = 'Custom persuasion instructions';
            a.tools = ['obfuscation'];
            a.priming = {mode: 'contextual', context: 'Prior agreement'};
            gsSave();
            renderGraph();
        }"""
    )


@then('the node of attacker 1 shows "Custom prompt", the tool chip, and "Few-shot priming"')
def node_shows_carries(ui: Page) -> None:
    node = ui.locator(f'{CANVAS} .gnode[data-id="a1"]')
    expect(node).to_contain_text("Custom prompt")
    expect(node).to_contain_text("obfuscation")
    expect(node).to_contain_text("Few-shot priming")


@when("I remove the tool chip from attacker 1's card")
def remove_tool_chip(ui: Page) -> None:
    node = ui.locator(f'{CANVAS} .gnode[data-id="a1"]')
    node.locator('.gc-chip[data-gc="tool"] .gc-rm').click()


@when("I remove the priming chip from attacker 1's card")
def remove_priming_chip(ui: Page) -> None:
    node = ui.locator(f'{CANVAS} .gnode[data-id="a1"]')
    node.locator('.gc-chip[data-gc="priming"] .gc-rm').click()


@then('the node of attacker 1 no longer shows that tool or "Few-shot priming"')
def node_removed_chips(ui: Page) -> None:
    node = ui.locator(f'{CANVAS} .gnode[data-id="a1"]')
    expect(node).not_to_contain_text("obfuscation")
    expect(node).not_to_contain_text("Few-shot priming")
    expect(ui.locator("#gdialog")).to_be_hidden()


@when('I click "+ Agent" on attacker 1\'s card')
def click_add_agent(ui: Page) -> None:
    node = ui.locator(f'{CANVAS} .gnode[data-id="a1"]')
    node.locator('.gc-act[data-act="add-agent"]').click()


@then("the canvas shows 4 attacker nodes")
def four_attackers(ui: Page) -> None:
    expect(ui.locator(f"{CANVAS} .gnode.attacker")).to_have_count(4)

