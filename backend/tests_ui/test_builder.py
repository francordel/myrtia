"""Baseline scenarios for the graph builder (spec 001: FR-16)."""
from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

from conftest import CANVAS, nodes, set_model
from fake_model import MODEL_NAME

scenarios("features/builder.feature")

@given("every agent uses the simulated model")
def every_agent_uses_the_simulated_model(ui: Page) -> None:
    ids = nodes(ui, "attacker").evaluate_all("nodes => nodes.map(n => n.dataset.id)")
    for node_id in [*ids, "target", "evaluator"]:
        set_model(ui, node_id, MODEL_NAME)


@when(parsers.parse('I launch a run with the goal "{goal}"'))
def launch_run(ui: Page, goal: str) -> None:
    ui.locator("#gGoal").fill(goal)
    ui.locator("#gLaunch").click()


@then("the graph builder is shown")
def builder_is_shown(ui: Page) -> None:
    expect(ui.locator(CANVAS)).to_be_visible()
    expect(ui.locator("#gLaunch")).to_be_visible()


@then(parsers.re(r"the canvas shows an? (?P<role>target|evaluator|chairman) node"))
def canvas_shows_one(ui: Page, role: str) -> None:
    expect(nodes(ui, role)).to_have_count(1)
    expect(nodes(ui, role)).to_be_visible()


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
