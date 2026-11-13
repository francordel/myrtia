"""Baseline scenarios for the graph builder (spec 001: FR-16)."""
from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

from fake_model import MODEL_NAME

scenarios("features/builder.feature")

CANVAS = "#agenticPane"


def _nodes(page: Page, role: str):
    return page.locator(f"{CANVAS} .gnode.{role}")


def _set_model(page: Page, node_id: str, model: str) -> None:
    """Open a node's editor, change its model and confirm."""
    page.locator(f'{CANVAS} .gnode[data-id="{node_id}"] .gr').click()
    dialog = page.locator("#gdialog")
    expect(dialog).to_be_visible()
    dialog.locator("#gd_model").fill(model)
    dialog.get_by_role("button", name="Done").click()
    expect(dialog).to_be_hidden()


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@given("I have added an attacker")
@when("I add an attacker")
def add_attacker(ui: Page) -> None:
    before = _nodes(ui, "attacker").count()
    ui.locator("#gAddAtk").click()
    expect(_nodes(ui, "attacker")).to_have_count(before + 1)


@when("I remove the last attacker")
def remove_last_attacker(ui: Page) -> None:
    _nodes(ui, "attacker").last.locator(".gx").click()


@when(parsers.parse('I set the model of attacker {n:d} to "{model}"'))
def set_attacker_model(ui: Page, n: int, model: str) -> None:
    _set_model(ui, f"a{n}", model)


@when(parsers.parse('I choose the "{name}" topology'))
def choose_topology(ui: Page, name: str) -> None:
    ui.locator(f'{CANVAS} [data-topo="{name.lower()}"]').click()


@given("every agent uses the simulated model")
def every_agent_uses_the_simulated_model(ui: Page) -> None:
    ids = _nodes(ui, "attacker").evaluate_all("nodes => nodes.map(n => n.dataset.id)")
    for node_id in [*ids, "target", "evaluator"]:
        _set_model(ui, node_id, MODEL_NAME)


@when(parsers.parse('I launch a run with the goal "{goal}"'))
def launch_run(ui: Page, goal: str) -> None:
    ui.locator("#gGoal").fill(goal)
    ui.locator("#gLaunch").click()


@then("the graph builder is shown")
def builder_is_shown(ui: Page) -> None:
    expect(ui.locator(CANVAS)).to_be_visible()
    expect(ui.locator("#gLaunch")).to_be_visible()


@then(parsers.parse("the canvas shows {count:d} attacker nodes"))
def canvas_shows_attackers(ui: Page, count: int) -> None:
    expect(_nodes(ui, "attacker")).to_have_count(count)


@then(parsers.re(r"the canvas shows an? (?P<role>target|evaluator|chairman) node"))
def canvas_shows_one(ui: Page, role: str) -> None:
    expect(_nodes(ui, role)).to_have_count(1)
    expect(_nodes(ui, role)).to_be_visible()


@then(parsers.parse('the node of attacker {n:d} shows "{model}"'))
def node_shows_model(ui: Page, n: int, model: str) -> None:
    expect(ui.locator(f'{CANVAS} .gnode[data-id="a{n}"] .gm')).to_have_text(model)


@then("the live view shows a target response")
def live_view_shows_target_response(ui: Page) -> None:
    response = ui.locator("#stream .ev.target").first
    expect(response).to_be_visible()
    expect(response).to_contain_text("Simulated reply.")


@then("the live view shows a judge score")
def live_view_shows_judge_score(ui: Page) -> None:
    verdict = ui.locator("#stream .ev.judge").first
    expect(verdict).to_be_visible()
    expect(verdict).to_contain_text("Simulated verdict.")


@then("the run ends as finished")
def run_ends_as_finished(ui: Page) -> None:
    expect(ui.locator("#nextRun")).to_be_visible()
    expect(ui.locator("#nextRunTitle")).to_have_text("Attack finished")
