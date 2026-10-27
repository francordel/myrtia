"""Auth-header handling of the OpenAI-compatible connector (Bearer by default,
custom header such as IBM RITS's RITS_API_KEY on request)."""

from __future__ import annotations

import pytest

from myrtia.connectors.base import OpenAIChatConnector, Status
from myrtia.connectors.factory import build_target_connector
from myrtia.judges.graded import GradedJudge
from myrtia.plugins.crescendo import CrescendoLive

URL = "http://127.0.0.1:11434/v1"


def _capture(monkeypatch) -> dict:
    seen: dict = {}

    class HTTPResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(_url, *, headers, **_kwargs):
        seen["headers"] = headers
        return HTTPResponse()

    monkeypatch.setattr("myrtia.connectors.base.requests.post", fake_post)
    return seen


def test_bearer_is_the_default(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    conn = OpenAIChatConnector(URL, "m", api_key="sekret")
    assert conn.generate("hi").status == Status.SUCCESS
    assert seen["headers"]["Authorization"] == "Bearer sekret"


def test_auth_header_replaces_bearer(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    conn = build_target_connector({"kind": "openai_chat", "base_url": URL, "model": "m",
                                   "api_key": "sekret", "auth_header": "RITS_API_KEY"})
    conn.generate("hi")
    assert seen["headers"]["RITS_API_KEY"] == "sekret"
    assert "Authorization" not in seen["headers"]


def test_extra_headers_are_sent_and_explicit_authorization_wins(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    conn = build_target_connector({"kind": "openai_chat", "base_url": URL, "model": "m",
                                   "api_key": "sekret",
                                   "headers": {"X-Team": "red", "Authorization": "Custom abc"}})
    conn.generate("hi")
    assert seen["headers"]["X-Team"] == "red"
    assert seen["headers"]["Authorization"] == "Custom abc"


def test_auth_header_never_leaks_into_connector_config() -> None:
    conn = build_target_connector({"kind": "openai_chat", "base_url": URL, "model": "m",
                                   "api_key": "sekret", "auth_header": "RITS_API_KEY"})
    assert "sekret" not in str(conn.config)


def test_invalid_auth_header_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_target_connector({"kind": "openai_chat", "base_url": URL, "model": "m",
                                "api_key": "k", "auth_header": "X\r\nEvil: 1"})


def test_ssrf_guard_still_applies_with_auth_header() -> None:
    with pytest.raises(ValueError):
        build_target_connector({"kind": "openai_chat", "base_url": "http://169.254.169.254/v1",
                                "model": "m", "api_key": "k", "auth_header": "RITS_API_KEY"})


def test_judge_and_crescendo_helper_use_the_auth_header(monkeypatch) -> None:
    seen = _capture(monkeypatch)
    GradedJudge("m", URL, "sekret", "RITS_API_KEY").score("goal", "reply")
    assert seen["headers"]["RITS_API_KEY"] == "sekret" and "Authorization" not in seen["headers"]

    seen.clear()
    atk = CrescendoLive({"aux_api_key": "sekret", "aux_auth_header": "RITS_API_KEY",
                           "aux_endpoint": URL}, object())
    atk._aux("m").generate("hi")
    assert seen["headers"]["RITS_API_KEY"] == "sekret" and "Authorization" not in seen["headers"]


def test_role_auth_inherits_only_for_the_same_endpoint() -> None:
    from myrtia.connectors.factory import role_auth
    cfg = {"api_key": "tkey", "auth_header": "RITS_API_KEY", "target_base_url": "https://t.example/v1"}
    assert role_auth(cfg, "aux", "https://t.example/v1/") == ("tkey", "RITS_API_KEY")
    # a different host must never receive the target's key
    assert role_auth(cfg, "aux", "http://127.0.0.1:11434/v1") == (None, None)
    # an explicit role credential always wins, with its own header
    cfg.update(aux_api_key="akey", aux_auth_header="X-API-Key")
    assert role_auth(cfg, "aux", "http://127.0.0.1:11434/v1") == ("akey", "X-API-Key")
    # direct API callers without target_base_url keep the old always-inherit behaviour
    assert role_auth({"api_key": "k"}, "judge", "http://anything/v1") == ("k", None)


def test_crescendo_judge_uses_its_own_endpoint_and_credentials(monkeypatch) -> None:
    atk = CrescendoLive({"aux_endpoint": "https://helper.example/v1", "aux_api_key": "hk",
                         "aux_auth_header": "X-Helper",
                         "judge_endpoint": "http://127.0.0.1:11434/v1"}, object())
    assert atk._aux("m").base_url == "https://helper.example/v1"
    judge = atk._aux("m", judge=True)
    assert judge.base_url == "http://127.0.0.1:11434/v1"
    assert judge.api_key is None  # the helper's cloud key must not reach the local judge
    shared = CrescendoLive({"aux_endpoint": "https://helper.example/v1", "aux_api_key": "hk",
                            "aux_auth_header": "X-Helper"}, object())
    assert shared._aux("m", judge=True).api_key == "hk"


def test_crescendo_judge_failure_is_reported_not_scored_as_resisted() -> None:
    from myrtia.connectors.base import Response

    class Broken:
        def generate(self, *_a, **_k):
            return Response(Status.ERROR, error_message="HTTP 404: model not found")

    atk = CrescendoLive({}, object())
    atk._judge = Broken()
    score, rationale = atk._judge_response("goal", "reply")
    assert score == 0 and rationale.startswith("[judge error]") and "404" in rationale
