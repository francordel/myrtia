"""Unit tests for the browser fixtures (spec 001: FR-8, FR-12, NFR-3)."""
from __future__ import annotations

import pytest

from conftest import INSTALL_HINT, evidence_dir, is_local_url, missing_browser_message


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/", "http://127.0.0.1/runs", "http://localhost:5173/x",
    "ws://127.0.0.1:8000/runs/1/events", "data:image/png;base64,AAAA", "about:blank",
    "blob:http://127.0.0.1:8000/abc",
])
def test_local_and_inline_urls_are_allowed(url: str) -> None:
    assert is_local_url(url)


@pytest.mark.parametrize("url", [
    "https://fonts.googleapis.com/css2?family=Roboto", "https://api.openai.com/v1/models",
    "http://127.0.0.1.evil.example/", "http://localhost.evil.example/",
    "http://169.254.169.254/latest/meta-data", "http://192.168.1.10:11434/v1",
])
def test_every_other_host_is_blocked(url: str) -> None:
    assert not is_local_url(url)


def test_missing_browser_error_becomes_the_install_hint() -> None:
    error = RuntimeError(
        "BrowserType.launch: Executable doesn't exist at /x/chrome-headless-shell\n"
        "Looks like Playwright was just installed or updated.\n"
        "Please run the following command to download new browsers: playwright install")
    assert missing_browser_message(error) == INSTALL_HINT
    assert "uv run --group ui playwright install chromium" in INSTALL_HINT


def test_other_launch_errors_are_not_rewritten() -> None:
    assert missing_browser_message(RuntimeError("Target page crashed")) is None


def test_evidence_folder_is_named_after_the_scenario(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MYRTIA_UI_RESULTS", str(tmp_path))
    folder = evidence_dir("backend/tests_ui/test_builder.py::test_adding an attacker[x/y]")
    assert folder.parent == tmp_path
    assert folder.name == "test_adding-an-attacker-x-y"
    # The browser name the plugin appends to every test id is dropped.
    assert evidence_dir("t.py::test_opens[chromium]").name == "test_opens"


def test_the_console_opens_in_a_desktop_sized_window(console_page) -> None:
    assert console_page.viewport_size == {"width": 1280, "height": 800}
    assert console_page.locator("#agenticPane .gnode").count() >= 1
