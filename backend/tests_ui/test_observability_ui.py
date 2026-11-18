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


# --- Traces control (spec 009) ---------------------------------------------------
TRACES_ON = "MYRTIA_TRACES=on uv run --extra otel myrtia"


@given("tracing is switched off")
def _tracing_off(ui: Any, sim_dashboard: FakeGrafana) -> None:
    """The instance runs with tracing on; answer for it as if it were off."""
    base = sim_dashboard.url
    body = {"enabled": True, "url": base, "reachable": True,
            "dashboard_url": base + "/d/myrtia-overview/myrtia-overview",
            "traces_url": base + "/d/myrtia-traces/myrtia-traces",
            "start_command": START,
            "tracing": {"enabled": False, "start_command": TRACES_ON,
                        "reason": "tracing is switched off (set MYRTIA_TRACES=on)"}}
    ui.route("**/observability", lambda route: route.fulfill(json=body))


@when("I press the Traces control", target_fixture="opened")
def _press_traces(ui: Any, sim_dashboard: FakeGrafana, request: Any) -> Any:
    button = ui.get_by_role("button", name="Traces")
    expects_dialog = (not sim_dashboard.up) or "switch tracing on" in request.node.name.replace("_", " ")
    if expects_dialog:
        button.click()
        return None
    with ui.context.expect_page() as new_page:
        button.click()
    return new_page.value


@then("the traces dashboard opens in a new tab")
def _traces_tab(opened: Any, sim_dashboard: FakeGrafana) -> None:
    opened.wait_for_load_state()
    assert opened.url == sim_dashboard.url + "/d/myrtia-traces/myrtia-traces"
    opened.close()


@then("a dialog says tracing is switched off")
def _traces_dialog(ui: Any, sim_dashboard: FakeGrafana) -> None:
    dialog = ui.get_by_role("dialog", name="Run traces")
    dialog.wait_for()
    text = dialog.inner_text()
    assert "Tracing is switched off" in text and "MYRTIA_TRACES=on" in text
    link = ui.get_by_role("link", name="Open anyway")
    assert link.get_attribute("href") == sim_dashboard.url + "/d/myrtia-traces/myrtia-traces"


@then("the dialog shows the command that starts Myrtia with tracing on")
def _traces_command(ui: Any) -> None:
    assert ui.locator("#obsCmd").inner_text().strip() == TRACES_ON
