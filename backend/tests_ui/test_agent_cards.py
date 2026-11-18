"""Scenarios for the agent cards on the canvas (spec 002)."""
from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import CANVAS, card, close_editor, nodes, open_editor

scenarios("features/agent_cards.feature")

PANEL = "#gtool"  # the floating panel used by the add menu, the tool picker and forms
TOOLS = ["direct", "obfuscation", "payload-splitting", "human-jailbreak", "promptinject"]


def _part(page: Page, n: int, label: str):
    """The row of attacker `n` whose label is exactly `label`."""
    exact = re.compile(rf"^\s*{re.escape(label)}\s*$")
    return card(page, n).locator(".gpart").filter(
        has=page.locator(".gpart-open", has_text=exact))


def _reveal(page: Page, n: int) -> None:
    """Open the card's detail (description and part rows) by moving focus into the card.

    Focus is used rather than the pointer because the browser driver may scroll the page
    while clicking, which would move the card from under a stationary pointer. Opening on
    pointing is covered by its own scenario.
    """
    card(page, n).focus()
    expect(card(page, n).locator(".gdetail")).to_be_visible()


def _add_menu(page: Page, node):
    node.locator(".gadd").click()
    panel = page.locator(PANEL)
    expect(panel).to_be_visible()
    return panel


def _grant_tools(page: Page, n: int, tools: list[str]) -> None:
    panel = _add_menu(page, card(page, n))
    panel.locator('[data-add="tools"]').click()
    for tool in tools:
        panel.locator(f'input[data-tid="{tool}"]').check()
    panel.locator("[data-close]").last.click()
    expect(panel).to_be_hidden()


# ── what a card shows ────────────────────────────────────────────────────────

@then(parsers.parse('the card of attacker {n:d} is named "{name}"'))
def card_is_named(ui: Page, n: int, name: str) -> None:
    expect(card(ui, n).locator(".gname")).to_have_text(name)


@then(parsers.parse('the card of attacker {n:d} lists the part "{label}"'))
def card_lists_part(ui: Page, n: int, label: str) -> None:
    expect(_part(ui, n, label)).to_have_count(1)


@then(parsers.parse('the card of attacker {n:d} does not list the part "{label}"'))
def card_does_not_list_part(ui: Page, n: int, label: str) -> None:
    expect(_part(ui, n, label)).to_have_count(0)


@then(parsers.parse('the part "{label}" of attacker {n:d} cannot be removed'))
def part_cannot_be_removed(ui: Page, n: int, label: str) -> None:
    expect(_part(ui, n, label)).to_have_count(1)
    expect(_part(ui, n, label).locator(".gpart-rm")).to_have_count(0)


@then(parsers.parse('the card of attacker {n:d} shows the description "{text}"'))
def card_shows_description(ui: Page, n: int, text: str) -> None:
    expect(card(ui, n).locator(".gdesc")).to_have_text(text)


@then(parsers.parse("the summary of attacker {n:d} shows {count:d} attack tools"))
def summary_counts_tools(ui: Page, n: int, count: int) -> None:
    expect(card(ui, n).locator('.gsum .gchip[data-type="tool"]')).to_have_text(str(count))


@then(parsers.parse("the summary of attacker {n:d} shows no attack tools"))
def summary_has_no_tools(ui: Page, n: int) -> None:
    expect(card(ui, n).locator('.gsum .gchip[data-type="tool"]')).to_have_count(0)
    expect(card(ui, n).locator('.gsum .gchip[data-type="prompt"]')).to_have_text("Default")


@then(parsers.parse("the detail of attacker {n:d} is hidden"))
def detail_is_hidden(ui: Page, n: int) -> None:
    ui.mouse.move(2, 2)
    expect(card(ui, n).locator(".gdetail")).to_be_hidden()


@when(parsers.parse("I point at the card of attacker {n:d}"))
def point_at(ui: Page, n: int) -> None:
    card(ui, n).locator(".gm").hover()


@then(parsers.parse("the detail of attacker {n:d} is shown"))
def detail_is_shown(ui: Page, n: int) -> None:
    expect(card(ui, n).locator(".gdetail")).to_be_visible()
    expect(card(ui, n).locator(".gpart").first).to_be_visible()


@then(parsers.parse(
    "the card of attacker {n:d} is the same size as the card of attacker {m:d}"))
def cards_same_size(ui: Page, n: int, m: int) -> None:
    ui.mouse.move(2, 2)
    size = "el => [el.offsetWidth, el.offsetHeight]"
    assert card(ui, n).evaluate(size) == card(ui, m).evaluate(size)


@then(parsers.parse("the card of attacker {n:d} contains no injected element"))
def card_has_no_injected_element(ui: Page, n: int) -> None:
    expect(card(ui, n).locator("img, b, script")).to_have_count(0)
    expect(card(ui, n).locator(".gdesc")).to_have_text("<b>bold</b>")


# ── naming ───────────────────────────────────────────────────────────────────

@when(parsers.parse('I name attacker {n:d} "{name}" with the description "{text}"'))
def name_and_describe(ui: Page, n: int, name: str, text: str) -> None:
    dialog = open_editor(ui, f"a{n}")
    dialog.locator("#gd_name").fill(name)
    dialog.locator("#gd_desc").fill(text)
    close_editor(ui)


@given(parsers.parse('attacker {n:d} is named "{name}"'))
def attacker_is_named(ui: Page, n: int, name: str) -> None:
    open_editor(ui, f"a{n}").locator("#gd_name").fill(name)
    close_editor(ui)


@when(parsers.parse("I clear the name of attacker {n:d}"))
def clear_name(ui: Page, n: int) -> None:
    open_editor(ui, f"a{n}").locator("#gd_name").fill("")
    close_editor(ui)


@when("I reload the page")
def reload_page(ui: Page) -> None:
    ui.reload()
    ui.wait_for_selector(f"{CANVAS} .gnode")


# ── parts ────────────────────────────────────────────────────────────────────

@given(parsers.parse('attacker {n:d} has the attack tool "{tool}"'))
@when(parsers.parse('I add the attack tool "{tool}" from the card of attacker {n:d}'))
def add_tool(ui: Page, n: int, tool: str) -> None:
    _grant_tools(ui, n, [tool])


@given(parsers.parse("attacker {n:d} has {count:d} attack tools"))
def has_tools(ui: Page, n: int, count: int) -> None:
    _grant_tools(ui, n, TOOLS[:count])


@given(parsers.parse('attacker {n:d} has the custom prompt "{text}"'))
def has_custom_prompt(ui: Page, n: int, text: str) -> None:
    open_editor(ui, f"a{n}").locator("#gd_sys").fill(text)
    close_editor(ui)


@when(parsers.parse("I add few-shot priming from the card of attacker {n:d}"))
def add_priming(ui: Page, n: int) -> None:
    _add_menu(ui, card(ui, n)).locator('[data-add="priming"]').click()
    expect(ui.locator("#gdialog #gd_prime_ctx")).to_be_visible()
    close_editor(ui)


@when(parsers.parse('I remove the part "{label}" from the card of attacker {n:d}'))
def remove_part(ui: Page, n: int, label: str) -> None:
    _reveal(ui, n)
    _part(ui, n, label).locator(".gpart-rm").click()


@when(parsers.parse('I open the part "{label}" on the card of attacker {n:d}'))
def open_part(ui: Page, n: int, label: str) -> None:
    _reveal(ui, n)
    _part(ui, n, label).locator(".gpart-open").click()


@then(parsers.parse('the settings of the tool "{tool}" are shown'))
def tool_settings_shown(ui: Page, tool: str) -> None:
    panel = ui.locator(PANEL)
    expect(panel).to_be_visible()
    expect(panel.locator(".gd-h")).to_contain_text(tool)
    expect(panel.locator("#tc_scheme")).to_be_visible()


@when("I undo")
def undo(ui: Page) -> None:
    ui.locator("#gUndo").click()


# ── new attacker ─────────────────────────────────────────────────────────────

@when(parsers.parse('I choose "New attacker" on the card of attacker {n:d}'))
def choose_new_attacker(ui: Page, n: int) -> None:
    _add_menu(ui, card(ui, n)).locator('[data-add="attacker"]').click()


@then(parsers.parse('the new attacker form proposes the model "{model}"'))
def form_proposes_model(ui: Page, model: str) -> None:
    expect(ui.locator("#ga_model")).to_have_value(model)


@when(parsers.parse('I confirm the new attacker as "{name}" described as "{text}"'))
def confirm_new_attacker(ui: Page, name: str, text: str) -> None:
    ui.locator("#ga_name").fill(name)
    ui.locator("#ga_desc").fill(text)
    ui.locator("#ga_create").click()


@when("I cancel the new attacker form")
def cancel_new_attacker(ui: Page) -> None:
    ui.locator("#ga_cancel").click()
    expect(ui.locator(PANEL)).to_be_hidden()


@given(parsers.parse("the canvas has {count:d} attackers"))
@when(parsers.parse("the canvas has {count:d} attackers"))
def canvas_has_attackers(ui: Page, count: int) -> None:
    while nodes(ui, "attacker").count() < count:
        before = nodes(ui, "attacker").count()
        ui.locator("#gAddAtk").click()
        expect(nodes(ui, "attacker")).to_have_count(before + 1)
    close_editor(ui)


@then("I am told the attacker limit is reached")
def told_limit_reached(ui: Page) -> None:
    expect(ui.locator("#toasts .toast").last).to_contain_text("limit")
    expect(ui.locator("#ga_create")).to_have_count(0)


# ── chairman, run request, geometry, keyboard ────────────────────────────────

@when("I open the add control on the chairman card")
def open_chairman_add(ui: Page) -> None:
    _add_menu(ui, nodes(ui, "chairman").first)


@then(parsers.parse('the add control offers exactly "{first}" and "{second}"'))
def add_control_offers(ui: Page, first: str, second: str) -> None:
    expect(ui.locator(f"{PANEL} [data-add]")).to_have_text([first, second])


@then("the run request for the graph contains no name or description")
def run_request_has_no_names(ui: Page) -> None:
    body = json.loads(ui.evaluate("JSON.stringify(graphBody(false))"))
    agents = body["attack_config"]["agents"]
    assert len(agents) == 3
    assert all("name" not in a and "desc" not in a for a in agents)
    assert "Persuader" not in json.dumps(body)


@then(parsers.parse(
    "the height used to draw the connections of attacker {n:d} matches its card"))
def connection_height_matches(ui: Page, n: int) -> None:
    half_used, half_real = ui.evaluate(
        """id => [G_CARD_HY[id],
                  document.querySelector(`.gnode[data-id="${id}"]`).offsetHeight / 2]""",
        f"a{n}")
    assert half_real > 40            # taller than the old fixed half-height of 38
    assert abs(half_used - half_real) <= 1.5


@then(parsers.parse(
    "every control on the card of attacker {n:d} is a button with an accessible name"))
def controls_are_buttons(ui: Page, n: int) -> None:
    controls = card(ui, n).locator(".gadd, .gpart-open, .gpart-rm, .gx, .gport")
    found = controls.evaluate_all(
        """els => els.map(e => [e.className, e.tagName,
                                (e.getAttribute('aria-label') || e.textContent || '').trim()])""")
    assert len(found) >= 6           # add, two rows to open, one to remove, delete, connect
    assert all(tag == "BUTTON" and name for _cls, tag, name in found), found


_COVERED = """card => [...card.querySelectorAll('.gadd, .gx')].filter(el => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const other = top && top.closest('.gnode');
    return other && other !== card;
}).map(el => el.className)"""


@when(parsers.parse("I point at the overlapped card of attacker {n:d}"))
def point_at_card(ui: Page, n: int) -> None:
    # Before pointing (pointer parked away from the canvas, focus dropped), a neighbour
    # really does cover part of this card.
    card(ui, n).scroll_into_view_if_needed()
    ui.mouse.move(2, 2)
    ui.evaluate("document.activeElement && document.activeElement.blur()")
    assert card(ui, n).evaluate(_COVERED), "expected an overlapped card in this layout"
    card(ui, n).locator(".gm").hover()


@then(parsers.parse("no other card covers the controls of attacker {n:d}"))
def controls_not_covered(ui: Page, n: int) -> None:
    assert card(ui, n).evaluate(_COVERED) == []
