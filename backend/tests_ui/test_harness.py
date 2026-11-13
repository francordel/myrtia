"""Scenarios about the UI test system itself (spec 001: FR-4, FR-8, FR-10, FR-11)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import Error, Page, expect
from pytest_bdd import given, scenarios, then, when

from app_launcher import AppInstance
from conftest import OPERATOR_DB, PageLog, file_state
from fake_model import FakeModel
from test_full_run import default_graph_body

scenarios("features/harness.feature")

_HERE = Path(__file__).resolve().parent
EXTERNAL_URL = "https://external-host.invalid/"


# ── the operator's data is untouched ─────────────────────────────────────────

@given("the operator's run history as it was before the scenarios started",
       target_fixture="before")
def operator_history_before(operator_db_before):
    return operator_db_before


@when("a run is launched in the private instance", target_fixture="run_id")
def launch_private_run(app: AppInstance, sim_model: FakeModel) -> str:
    req = urllib.request.Request(  # noqa: S310 - loopback only
        app.url + "runs", data=json.dumps(default_graph_body(sim_model.v1)).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
        run_id = json.loads(r.read())["run_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with urllib.request.urlopen(app.url + "runs/" + run_id, timeout=10) as r:  # noqa: S310
            if json.loads(r.read())["status"] not in ("pending", "running"):
                break
        time.sleep(0.1)
    return run_id


@then("the private instance has stored that run")
def private_instance_stored_run(app: AppInstance, run_id: str) -> None:
    db = Path(app.data_dir) / "myrtia.db"
    assert db.is_file() and db.stat().st_size > 0
    assert db.resolve() != OPERATOR_DB.resolve()
    with urllib.request.urlopen(app.url + "runs/" + run_id, timeout=10) as r:  # noqa: S310
        assert json.loads(r.read())["status"] == "succeeded"


@then("the operator's run history is unchanged")
def operator_history_unchanged(before) -> None:
    assert file_state(OPERATOR_DB) == before


# ── nothing leaves the machine ───────────────────────────────────────────────

@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@when("the browser requests a page from an external host")
def request_external_page(ui: Page) -> None:
    other = ui.context.new_page()
    with pytest.raises(Error):
        other.goto(EXTERNAL_URL)
    other.close()


@then("the request is blocked")
def request_is_blocked(page_log: PageLog) -> None:
    assert EXTERNAL_URL in page_log.blocked


@then("the graph builder is shown")
def builder_is_shown(ui: Page) -> None:
    expect(ui.locator("#agenticPane")).to_be_visible()
    expect(ui.locator("#agenticPane .gnode").first).to_be_visible()


# ── failures leave evidence; script errors fail the scenario ─────────────────

@pytest.fixture(scope="module")
def inner_run(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run the deliberately failing scenarios once, in their own pytest process."""
    results = tmp_path_factory.mktemp("inner-results")
    env = {**os.environ, "MYRTIA_UI_RESULTS": str(results)}
    proc = subprocess.run(  # noqa: S603 - fixed, local command
        [sys.executable, "-m", "pytest", str(_HERE / "inner_cases.py"), "-q",
         "-p", "no:cacheprovider"],
        cwd=str(_HERE.parent), env=env, capture_output=True, text=True, timeout=180)
    return {"code": proc.returncode, "output": proc.stdout + proc.stderr, "results": results}


@given("a UI scenario that fails", target_fixture="case")
def failing_case() -> str:
    return "test_fails_on_assertion"


@given("a UI scenario whose page raises an unhandled script error", target_fixture="case")
def script_error_case() -> str:
    return "test_raises_script_error"


@when("it finishes", target_fixture="finished")
def it_finishes(inner_run: dict) -> dict:
    assert inner_run["code"] != 0, inner_run["output"]
    return inner_run


@then("a screenshot and the browser's messages are saved for it")
def evidence_is_saved(finished: dict, case: str) -> None:
    folder = finished["results"] / case
    shot, log = folder / "screenshot.png", folder / "console.txt"
    assert shot.is_file() and shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", finished["output"]
    assert log.is_file() and "[blocked]" in log.read_text()


@then("the scenario is reported as failed with that error")
def scenario_reported_failed(finished: dict, case: str) -> None:
    out = finished["output"]
    assert "unhandled script error" in out
    assert "boom-script" in out
    assert f"inner_cases.py::{case}" in out
