"""Unit tests for the simulated model server (spec 001: FR-7, FR-9)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from fake_model import FIXED_REPLY, MODEL_NAME, FakeModel
from myrtia.judges.graded import parse_score


@pytest.fixture()
def server():
    with FakeModel() as srv:
        yield srv


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 - loopback only
        return json.loads(r.read())


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(  # noqa: S310 - loopback only
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310
        return json.loads(r.read())


def test_listens_on_loopback_on_a_free_port(server: FakeModel) -> None:
    assert server.host == "127.0.0.1"
    assert server.port > 0
    assert server.url == f"http://127.0.0.1:{server.port}"
    assert server.v1 == server.url + "/v1"


def test_ollama_tags_lists_the_simulated_model(server: FakeModel) -> None:
    assert _get(server.url + "/api/tags") == {"models": [{"name": MODEL_NAME}]}


def test_openai_models_lists_the_simulated_model(server: FakeModel) -> None:
    assert _get(server.v1 + "/models") == {"data": [{"id": MODEL_NAME}]}


def test_chat_completion_returns_the_fixed_reply_and_usage(server: FakeModel) -> None:
    data = _post(server.v1 + "/chat/completions",
                 {"model": MODEL_NAME, "messages": [{"role": "user", "content": "hi"}]})
    assert data["choices"][0]["message"] == {"role": "assistant", "content": FIXED_REPLY}
    assert data["usage"] == {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}


def test_any_request_gets_the_same_default_reply(server: FakeModel) -> None:
    a = _post(server.v1 + "/chat/completions", {"model": "other", "messages": []})
    b = _post(server.v1 + "/chat/completions", {"model": MODEL_NAME, "messages": [
        {"role": "system", "content": "You are a judge."},
        {"role": "user", "content": "Grade this."}]})
    assert a["choices"][0]["message"]["content"] == FIXED_REPLY
    assert b["choices"][0]["message"]["content"] == FIXED_REPLY


def test_unknown_path_is_404_with_empty_json(server: FakeModel) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server.url + "/nope")
    assert exc.value.code == 404
    assert json.loads(exc.value.read()) == {}


def test_requests_are_recorded(server: FakeModel) -> None:
    _post(server.v1 + "/chat/completions", {"model": MODEL_NAME, "messages": []})
    assert [r["path"] for r in server.requests] == ["/v1/chat/completions"]
    assert server.requests[0]["body"]["model"] == MODEL_NAME


def test_the_judge_parser_accepts_the_fixed_reply() -> None:
    assert parse_score(FIXED_REPLY) == (1, "Simulated verdict.")


def test_server_stops_on_exit() -> None:
    with FakeModel() as srv:
        url = srv.url + "/api/tags"
    with pytest.raises(OSError):
        urllib.request.urlopen(url, timeout=2)  # noqa: S310
