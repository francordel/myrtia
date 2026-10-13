"""Shared pytest fixtures for Myrtia's behaviour-driven tests.

Two tiers of scenario:
  * fast, offline: encoding transforms and the evaluator's reply parsing / config
    logic — pure functions, no network.
  * end-to-end (@e2e): every attack run against a live OpenAI-compatible endpoint
    (local Ollama by default). These self-skip when no endpoint is reachable, so
    `pytest -m "not e2e"` is always green in CI.
"""
from __future__ import annotations

import os
import sys
import urllib.request

import pytest

# Make `import myrtia...` work when pytest is run from anywhere.
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

OLLAMA_BASE = os.getenv("MYRTIA_TEST_ENDPOINT", "http://127.0.0.1:11434/v1")
OLLAMA_MODEL = os.getenv("MYRTIA_TEST_MODEL", "qwen2.5:3b")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: needs a live model endpoint (local Ollama)")


def _endpoint_up() -> bool:
    tags = OLLAMA_BASE.rsplit("/v1", 1)[0] + "/api/tags"
    try:
        urllib.request.urlopen(tags, timeout=2)  # noqa: S310
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture(scope="session")
def live_endpoint() -> str:
    if not _endpoint_up():
        pytest.skip(f"no live model endpoint at {OLLAMA_BASE}")
    return OLLAMA_BASE


@pytest.fixture()
def target_connector(live_endpoint: str):
    from myrtia.connectors.factory import build_target_connector
    return build_target_connector({
        "kind": "openai_chat", "base_url": live_endpoint,
        "model": OLLAMA_MODEL, "api_key": None,
    })
