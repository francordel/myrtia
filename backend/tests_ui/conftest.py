"""Fixtures for the UI scenarios (see specs/features/001-ui-e2e-tests).

The tier starts two local processes once per session: a simulated model server and a
private Myrtia instance pointed at it (temporary database, no keys). Every scenario
then gets a fresh browser context in which requests to any host other than this machine
are blocked. A scenario that fails, or whose page raises an unhandled script error,
leaves a screenshot and the browser's messages under `test-results/`.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# Make `import myrtia...` work when pytest is run from anywhere.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app_launcher import AppInstance  # noqa: E402
from fake_model import FakeModel  # noqa: E402

INSTALL_HINT = (
    "The browser for the UI scenarios is not installed. Install it with:\n"
    "    uv run --group ui playwright install chromium")

_LOCAL = re.compile(r"^(https?|wss?)://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(/|$)")
_INLINE = ("data:", "blob:", "about:")

# The operator's own run store. Its state is recorded before anything else runs so the
# tier can prove it never touches it (FR-4).
OPERATOR_DB = Path(os.environ.get("MYRTIA_DB") or _BACKEND.parent / ".data" / "myrtia.db")


def file_state(path: Path) -> tuple[int, str] | None:
    """(size, sha256) of a file, or None when it does not exist."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return len(data), hashlib.sha256(data).hexdigest()


_OPERATOR_DB_BEFORE = file_state(OPERATOR_DB)


def is_local_url(url: str) -> bool:
    """True for this machine and for inline URLs; everything else is blocked (FR-8)."""
    return url.startswith(_INLINE) or bool(_LOCAL.match(url))


def missing_browser_message(error: BaseException) -> str | None:
    """The install hint when `error` means the browser binary is absent (FR-12)."""
    text = str(error)
    if "Executable doesn't exist" in text or "playwright install" in text:
        return INSTALL_HINT
    return None


def results_dir() -> Path:
    """Where failure evidence is written (overridable for the harness's own tests)."""
    return Path(os.environ.get("MYRTIA_UI_RESULTS") or _BACKEND / "test-results")


def evidence_dir(nodeid: str) -> Path:
    test = re.sub(r"\[(chromium|firefox|webkit)\]$", "", nodeid.split("::", 1)[-1])
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", test).strip("-")
    return results_dir() / name[:120]


# ── session: simulated model + private application instance ──────────────────

@pytest.fixture(scope="session")
def sim_model() -> Generator[FakeModel, None, None]:
    with FakeModel() as model:
        yield model


@pytest.fixture(scope="session")
def app(sim_model: FakeModel) -> Generator[AppInstance, None, None]:
    with AppInstance(model_url=sim_model.url) as instance:
        yield instance


@pytest.fixture(scope="session")
def operator_db_before() -> tuple[int, str] | None:
    return _OPERATOR_DB_BEFORE


# ── browser: one engine, one size, clear error when it is missing ────────────

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


@pytest.fixture(scope="session")
def browser(launch_browser: Any) -> Generator[Any, None, None]:
    try:
        instance = launch_browser()
    except Exception as error:  # noqa: BLE001 - re-raised unless it is the known case
        hint = missing_browser_message(error)
        if hint is None:
            raise
        pytest.fail(hint, pytrace=False)
    yield instance
    instance.close()


# ── per scenario: isolation, evidence, script-error guard ────────────────────

class PageLog:
    """What the browser reported during one scenario."""

    def __init__(self) -> None:
        self.console: list[str] = []
        self.script_errors: list[str] = []
        self.blocked: list[str] = []

    def text(self) -> str:
        lines = [f"[script error] {e}" for e in self.script_errors]
        lines += [f"[blocked] {u}" for u in self.blocked]
        lines += self.console
        return "\n".join(lines) + "\n"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item) -> Generator[None, Any, None]:
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        item.stash[_CALL_FAILED] = report.failed


_CALL_FAILED: pytest.StashKey[bool] = pytest.StashKey()


@pytest.fixture()
def page_log() -> PageLog:
    return PageLog()


@pytest.fixture()
def context(context: Any, page_log: PageLog) -> Any:
    def route(r: Any) -> None:
        url = r.request.url
        if is_local_url(url):
            r.continue_()
        else:
            page_log.blocked.append(url)
            r.abort()

    context.route("**/*", route)
    # Scenarios act as a returning operator: the first-visit welcome offer covers the
    # canvas and is not what they test.
    context.add_init_script(
        "try { localStorage.setItem('myrtia-demo-seen', '1'); } catch (e) {}")
    return context


@pytest.fixture()
def page(context: Any, page_log: PageLog,
         request: pytest.FixtureRequest) -> Generator[Any, None, None]:
    pg = context.new_page()
    pg.set_default_timeout(8000)  # a missing element fails the scenario quickly
    pg.on("console", lambda m: page_log.console.append(f"[{m.type}] {m.text}"))
    pg.on("pageerror", lambda e: page_log.script_errors.append(str(e)))
    yield pg
    failed = request.node.stash.get(_CALL_FAILED, False)
    if failed or page_log.script_errors:
        folder = evidence_dir(request.node.nodeid)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            pg.screenshot(path=str(folder / "screenshot.png"), full_page=True)
        except Exception as error:  # noqa: BLE001 - evidence must not mask the failure
            page_log.console.append(f"[evidence] screenshot failed: {error}")
        (folder / "console.txt").write_text(page_log.text())
    if page_log.script_errors:
        pytest.fail("The page raised an unhandled script error:\n  "
                    + "\n  ".join(page_log.script_errors), pytrace=False)


@pytest.fixture()
def console_page(page: Any, app: AppInstance) -> Any:
    """The Myrtia console, opened on the graph builder."""
    page.goto(app.url)
    page.wait_for_selector("#agenticPane .gnode")
    return page


# ── steps shared by the UI features ──────────────────────────────────────────

from playwright.sync_api import Page, expect  # noqa: E402
from pytest_bdd import given, parsers, then, when  # noqa: E402

CANVAS = "#agenticPane"


def nodes(page: Page, role: str) -> Any:
    return page.locator(f"{CANVAS} .gnode.{role}")


def card(page: Page, n: int) -> Any:
    """The card of attacker `n` (1-based, in creation order)."""
    return page.locator(f'{CANVAS} .gnode[data-id="a{n}"]')


def open_editor(page: Page, node_id: str) -> Any:
    """Open a node's editor and return the dialog."""
    page.locator(f'{CANVAS} .gnode[data-id="{node_id}"] .gm').click()
    dialog = page.locator("#gdialog")
    expect(dialog).to_be_visible()
    return dialog


def close_editor(page: Page) -> None:
    dialog = page.locator("#gdialog")
    dialog.get_by_role("button", name="Done").click()
    expect(dialog).to_be_hidden()


def set_model(page: Page, node_id: str, model: str) -> None:
    open_editor(page, node_id).locator("#gd_model").fill(model)
    close_editor(page)


@given("the Myrtia console is open", target_fixture="ui")
def console_is_open(console_page: Page) -> Page:
    return console_page


@given("I have added an attacker")
@when("I add an attacker")
def add_attacker(ui: Page) -> None:
    before = nodes(ui, "attacker").count()
    ui.locator("#gAddAtk").click()
    expect(nodes(ui, "attacker")).to_have_count(before + 1)


@when("I remove the last attacker")
def remove_last_attacker(ui: Page) -> None:
    nodes(ui, "attacker").last.locator(".gx").click()


@given(parsers.parse('attacker {n:d} uses the model "{model}"'))
@when(parsers.parse('I set the model of attacker {n:d} to "{model}"'))
def set_attacker_model(ui: Page, n: int, model: str) -> None:
    set_model(ui, f"a{n}", model)


@given(parsers.parse('I have chosen the "{name}" topology'))
@when(parsers.parse('I choose the "{name}" topology'))
def choose_topology(ui: Page, name: str) -> None:
    ui.locator(f'{CANVAS} [data-topo="{name.lower()}"]').click()


@then(parsers.parse("the canvas shows {count:d} attacker nodes"))
def canvas_shows_attackers(ui: Page, count: int) -> None:
    expect(nodes(ui, "attacker")).to_have_count(count)
