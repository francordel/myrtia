"""Goal pack installation and filtering without a network dependency."""

from __future__ import annotations

import hashlib
import io

from starlette.testclient import TestClient

from myrtia.api.app import app
from myrtia.data import goal_datasets


def _source(data: bytes) -> dict:
    return {
        "name": "Toy goals", "description": "test", "homepage": "https://example.org",
        "license": "MIT", "revision": "test", "url": "https://example.org/goals.csv",
        "sha256": hashlib.sha256(data).hexdigest(), "rows": 2,
        "goal_column": "goal", "theme_column": "category",
    }


def test_downloaded_goals_appear_in_catalog_and_dataset_filter(tmp_path, monkeypatch) -> None:
    data = b"goal,category\nExplain backups,operations\nExplain recovery,continuity\n"
    monkeypatch.setenv("MYRTIA_GOAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(goal_datasets, "SOURCES", {"toy": _source(data)})
    monkeypatch.setattr(goal_datasets.urllib.request, "urlopen", lambda _request, timeout: io.BytesIO(data))
    client = TestClient(app)

    assert client.get("/datasets").json()["datasets"][-1]["installed"] is False
    installed = client.post("/datasets/toy/install").json()
    assert installed["ok"] is True and installed["count"] == 2
    assert client.get("/datasets").json()["datasets"][-1]["installed"] is True
    only_toy = client.get("/behaviors", params={"dataset": "toy"}).json()
    assert only_toy["total"] == 2
    assert {b["dataset"] for b in only_toy["behaviors"]} == {"toy"}
    assert len(client.get("/behaviors", params={"dataset": "toy", "theme": "operations"}).json()["behaviors"]) == 1
    assert client.get("/behaviors").json()["total"] == 280  # bundled 278 + downloaded 2


def test_dataset_hash_mismatch_never_installs(tmp_path, monkeypatch) -> None:
    data = b"goal,category\nExplain backups,operations\nExplain recovery,continuity\n"
    spec = _source(data)
    spec["sha256"] = "0" * 64
    monkeypatch.setenv("MYRTIA_GOAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(goal_datasets, "SOURCES", {"toy": spec})
    monkeypatch.setattr(goal_datasets.urllib.request, "urlopen", lambda _request, timeout: io.BytesIO(data))
    result = TestClient(app).post("/datasets/toy/install").json()
    assert result["ok"] is False and "SHA-256" in result["error"]
    assert list(tmp_path.iterdir()) == []


def test_unknown_dataset_filter_is_rejected() -> None:
    assert TestClient(app).get("/behaviors", params={"dataset": "unknown"}).status_code == 400
