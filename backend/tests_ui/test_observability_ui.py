"""Steps for features/observability.feature: the console's Dashboard control."""
from __future__ import annotations

from typing import Any

from pytest_bdd import given, scenarios, then, when

from fake_grafana import PAGE_TITLE, FakeGrafana

scenarios("features/observability.feature")

START = "docker compose -f compose.observability.yaml up -d"


@given("the Myrtia console is open", target_fixture="ui")
def _console(console_page: Any) -> Any:
    return console_page


@given("the dashboard is running")
def _running(sim_dashboard: FakeGrafana) -> None:
    sim_dashboard.up = True


@given("the dashboard is not running")
def _stopped(sim_dashboard: FakeGrafana) -> None:
    sim_dashboard.up = False


@when("I press the Dashboard control", target_fixture="opened")
def _press(ui: Any, sim_dashboard: FakeGrafana) -> Any:
    button = ui.get_by_role("button", name="Dashboard")
    if not sim_dashboard.up:
        button.click()
        return None
    with ui.context.expect_page() as new_page:
        button.click()
    return new_page.value


@then("the dashboard opens in a new tab")
def _new_tab(opened: Any, sim_dashboard: FakeGrafana) -> None:
    opened.wait_for_load_state()
    assert opened.url == sim_dashboard.url + "/d/myrtia-overview/myrtia-overview"
    assert opened.title() == PAGE_TITLE
    opened.close()


@then("the console is still on the graph builder")
def _still_there(ui: Any) -> None:
    assert ui.locator("#agenticPane .gnode").first.is_visible()
    assert not ui.locator("#obsModal").is_visible()


@then("a dialog says the dashboard is not running")
def _dialog(ui: Any) -> None:
    dialog = ui.get_by_role("dialog", name="Observability dashboard")
    dialog.wait_for()
    assert "not running" in dialog.inner_text()


@then("the dialog shows the command that starts it")
def _command(ui: Any) -> None:
    assert ui.locator("#obsCmd").inner_text().strip() == START


@then("the dialog offers to open the dashboard anyway")
def _anyway(ui: Any, sim_dashboard: FakeGrafana) -> None:
    link = ui.get_by_role("link", name="Open anyway")
    assert link.get_attribute("href") == sim_dashboard.url + "/d/myrtia-overview/myrtia-overview"
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in (link.get_attribute("rel") or "")


@when("I close the dialog")
def _close(ui: Any) -> None:
    ui.locator("#obsClose").click()
