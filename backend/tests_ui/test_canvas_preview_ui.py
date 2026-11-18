"""Playwright UI scenarios for Canvas Preview (Spec 003)."""

from __future__ import annotations

from playwright.sync_api import Page, expect
from pytest_bdd import given, parsers, scenarios, then, when

from fake_model import MODEL_NAME

scenarios("features/canvas_preview.feature")

CANVAS = "#agenticPane"


def _set_model(page: Page, node_id: str, model: str) -> None:
    page.locator(f'{CANVAS} .gnode[data-id="{node_id}"] .gr').click()
    dialog = page.locator("#gdialog")
    expect(dialog).to_be_visible()
    dialog.locator("#gd_model").fill(model)
    dialog.get_by_role("button", name="Done").click()
    expect(dialog).to_be_hidden()


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@given("every agent uses the simulated model")
def every_agent_uses_the_simulated_model(ui: Page) -> None:
    ids = ui.locator(f"{CANVAS} .gnode.attacker").evaluate_all(
        "nodes => nodes.map(n => n.dataset.id)"
    )
    for node_id in [*ids, "target", "evaluator"]:
        _set_model(ui, node_id, MODEL_NAME)


@when(parsers.parse('I open the canvas preview and run with goal "{goal}"'))
def open_and_run_preview(ui: Page, goal: str) -> None:
    ui.locator("#gPreviewBtn").click()
    panel = ui.locator("#gPreviewPanel")
    expect(panel).to_be_visible()
    ui.locator("#gPreviewGoal").fill(goal)
    ui.locator("#gPreviewRun").click()
    expect(ui.locator("#gPreviewStatus")).to_contain_text("Completed", timeout=30000)


@then("the graph builder stays visible")
def builder_stays_visible(ui: Page) -> None:
    expect(ui.locator("#gcanvas")).to_be_visible()
    expect(ui.locator("#gPreviewPanel")).to_be_visible()


@then("the docked preview panel shows the target response and judge score")
def preview_shows_target_and_judge(ui: Page) -> None:
    log = ui.locator("#gPreviewLog")
    expect(log).to_contain_text("Target")
    expect(log).to_contain_text("Judge")


@then("no node remains highlighted after the preview finishes")
def no_node_highlighted(ui: Page) -> None:
    expect(ui.locator(f"{CANVAS} .gnode.is-active")).to_have_count(0)


@when(parsers.parse('a preview event arrives for "{event_type}"'))
def trigger_highlight_event(ui: Page, event_type: str) -> None:
    ui.evaluate("(et) => gHighlightForEvent({type: et, payload: {}})", event_type)


@then("the target node on the canvas is highlighted as active")
def target_highlighted(ui: Page) -> None:
    expect(ui.locator(f"{CANVAS} .gnode.target.is-active")).to_have_count(1)



@when("I close the canvas preview panel")
def close_preview_panel(ui: Page) -> None:
    ui.locator("#gPreviewBtn").click()
    ui.locator("#gPreviewClose").click()


@when("a preview failure event is received")
def receive_preview_failure(ui: Page) -> None:
    ui.locator("#gPreviewBtn").click()
    ui.evaluate(
        "() => gAppendPreviewEvent({seq: 99, type: 'run.finished', payload: {status: 'failed', error: 'Simulated endpoint failure'}})"
    )


@then("the docked preview panel shows the error message")
def preview_shows_error(ui: Page) -> None:
    expect(ui.locator("#gPreviewLog")).to_contain_text("Simulated endpoint failure")
