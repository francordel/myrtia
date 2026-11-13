"""Scenarios that fail on purpose.

Not collected by default (the file name does not match `test_*.py`). The harness
scenarios run this file in a separate pytest process and inspect what it leaves behind.
"""
from __future__ import annotations


def test_fails_on_assertion(console_page) -> None:
    assert console_page.locator(".this-element-does-not-exist").count() == 1


def test_raises_script_error(console_page) -> None:
    console_page.evaluate("setTimeout(() => { throw new Error('boom-script') }, 0)")
    console_page.wait_for_timeout(300)
