"""A whole run against the simulated model, without a browser (spec 001: FR-7).

Proves the fixed reply is enough for every role of the default council topology, so
the UI scenario that launches a run does not depend on a real model.
"""
from __future__ import annotations

import json
import time
import urllib.request

from app_launcher import AppInstance
from fake_model import FIXED_REPLY, MODEL_NAME, FakeModel


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(  # noqa: S310 - loopback only
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
        return json.loads(r.read())


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 - loopback only
        return json.loads(r.read())


def default_graph_body(model_v1: str) -> dict:
    """The request the builder sends for its default council of three attackers."""
    return {
        "attack_id": "graph", "title": "", "theme": "", "goals": ["Say hello"],
        "purpose": "smoke", "goal_datasets": ["manual"],
        "target": {"kind": "openai_chat", "base_url": model_v1, "model": MODEL_NAME},
        "attack_config": {
            "mode": "council",
            "agents": [{"role": "attacker", "id": f"a{i}", "model": MODEL_NAME}
                       for i in (1, 2, 3)],
            "evaluator": {"model": MODEL_NAME},
            "max_turns": 3, "use_borda": True, "use_chairman": False, "success_score": 5,
            "accumulate_target_context": False, "contextual_mode": False,
        },
    }


def test_default_council_run_finishes_against_the_simulated_model() -> None:
    with FakeModel() as model, AppInstance(model_url=model.url) as app:
        # The instance advertises the simulated model as its local default.
        system = _get(app.url + "system")
        assert system["ollama_url"] == model.v1
        assert system["default_model"] == MODEL_NAME

        run_id = _post(app.url + "runs", default_graph_body(model.v1))["run_id"]
        deadline = time.monotonic() + 30
        run = _get(app.url + "runs/" + run_id)
        while run["status"] in ("pending", "running") and time.monotonic() < deadline:
            time.sleep(0.1)
            run = _get(app.url + "runs/" + run_id)

        assert run["status"] == "succeeded", run.get("error")
        turns = run["results"][0]["council_turns"]
        assert len(turns) == 3                       # score 1 never reaches success_score
        assert all(t["response"] == FIXED_REPLY for t in turns)
        assert all(t["judge_score"] == 1 for t in turns)
        assert all(t["judge_rationale"] == "Simulated verdict." for t in turns)
        # Every model call went to the simulated server.
        assert any(r["path"] == "/v1/chat/completions" for r in model.requests)
