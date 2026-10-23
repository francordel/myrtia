"""Risk reporting must never silently mix smoke/legacy runs with security tests."""

from fastapi.testclient import TestClient

import myrtia.api.app as appmod
from myrtia.events.schema import Event, EventType
from myrtia.store.runs import Run, RunSpec, RunStatus, RunStore


def _run(run_id: str, purpose: str, datasets: list[str], scores: list[int]) -> Run:
    return Run(
        id=run_id,
        spec=RunSpec(attack_id="direct", target={"model": "test-model"},
                     goals=[f"goal-{run_id}-{i}" for i in range(len(scores))],
                     purpose=purpose, goal_datasets=datasets),
        status=RunStatus.SUCCEEDED,
        results=[{"score": score} for score in scores],
    )


def test_stats_and_audit_exclude_smoke_and_legacy_by_default(monkeypatch) -> None:
    security = _run("security-run", "security", ["harmbench", "jailbreakbench"], [0, 5])
    smoke = _run("smoke-run", "smoke", ["manual"], [5])
    legacy = _run("legacy-run", "unreviewed", [], [5])
    runs = [security, smoke, legacy]
    monkeypatch.setattr(appmod.STORE, "list", lambda: runs)

    def backlog(run_id: str) -> list[Event]:
        run = next(r for r in runs if r.id == run_id)
        events = []
        for goal, result in zip(run.spec.goals, run.results):
            events.append(Event(run_id, EventType.GOAL_STARTED, {"goal": goal}))
            events.append(Event(run_id, EventType.JUDGE_SCORED, {"score": result["score"]}))
        return events

    monkeypatch.setattr(appmod.BUS, "backlog", backlog)
    client = TestClient(appmod.app)
    default = client.get("/stats").json()
    assert default["total_runs"] == 1 and default["total_goals"] == 2
    assert default["jailbroken"] == 1 and default["excluded_runs"] == 2
    assert {r["key"] for r in default["by_dataset"]} == {"harmbench", "jailbreakbench"}

    harmbench = client.get("/stats?dataset=harmbench").json()
    assert harmbench["total_goals"] == 1 and harmbench["jailbroken"] == 0
    assert client.get("/stats?purpose=all").json()["jailbroken"] == 3
    audit = client.get("/audit?format=json").json()
    assert audit["summary"]["jailbroken"] == 1
    assert audit["filters"]["purpose"] == "security"
    assert "automatic judge" in audit["methodology_note"]


def test_stats_collapse_multivariant_goal_started(monkeypatch) -> None:
    """Multi-variant attacks emit one goal.started per variant of the same goal; stats
    must count distinct goals (best score across variants), not one per variant."""
    run = Run(
        id="multivariant",
        spec=RunSpec(attack_id="obfuscation", target={"model": "test-model"},
                     goals=["A", "B"], purpose="security", goal_datasets=[]),
        status=RunStatus.SUCCEEDED, results=[],
    )
    monkeypatch.setattr(appmod.STORE, "list", lambda: [run])
    # Goal A tried with 3 variants (best = 5 -> jailbreak); goal B with 2 variants (no hit).
    stream = [("A", 2), ("A", 0), ("A", 5), ("B", 1), ("B", 1)]

    def backlog(run_id: str) -> list[Event]:
        events = []
        for goal, score in stream:
            events.append(Event(run_id, EventType.GOAL_STARTED, {"goal": goal, "variant": "v"}))
            events.append(Event(run_id, EventType.JUDGE_SCORED, {"score": score}))
        return events

    monkeypatch.setattr(appmod.BUS, "backlog", backlog)
    data = TestClient(appmod.app).get("/stats").json()
    assert data["total_goals"] == 2          # two distinct goals, not five variants
    assert data["jailbroken"] == 1           # goal A, best-of-variants >= 5
    assert data["asr"] == 50


def test_history_filters_and_reclassification(monkeypatch) -> None:
    resisted = _run("resisted", "security", ["harmbench"], [2])
    unjudged = _run("unjudged", "unreviewed", [], [])
    unjudged.spec.goals = ["goal-without-score"]
    runs = [resisted, unjudged]
    monkeypatch.setattr(appmod.STORE, "list", lambda: runs)
    monkeypatch.setattr(appmod.STORE, "get", lambda run_id: next((r for r in runs if r.id == run_id), None))
    saved = []
    monkeypatch.setattr(appmod.STORE, "persist", lambda run: saved.append(run.id))
    client = TestClient(appmod.app)
    assert [r["id"] for r in client.get("/runs?outcome=resisted").json()["runs"]] == ["resisted"]
    assert [r["id"] for r in client.get("/runs?outcome=not_judged").json()["runs"]] == ["unjudged"]
    assert [r["id"] for r in client.get("/runs?dataset=harmbench").json()["runs"]] == ["resisted"]
    assert client.patch("/runs/unjudged/purpose", json={"purpose": "smoke"}).status_code == 200
    assert unjudged.spec.purpose == "smoke" and saved == ["unjudged"]
    assert client.patch("/runs/unjudged/purpose", json={"purpose": "anything"}).status_code == 400


def test_active_runs_are_independent_of_history_filters(monkeypatch) -> None:
    first = _run("first", "smoke", ["manual"], [0])
    first.spec.title = "Alpha experiment"
    first.status = RunStatus.RUNNING
    second = _run("second", "security", ["harmbench"], [0])
    second.spec.title = "Beta experiment"
    second.status = RunStatus.RUNNING
    finished = _run("finished", "security", ["harmbench"], [0])
    monkeypatch.setattr(appmod.STORE, "list", lambda: [first, second, finished])

    data = TestClient(appmod.app).get("/runs?q=missing&purpose=security").json()
    assert data["runs"] == []
    assert [(r["id"], r["title"]) for r in data["active_runs"]] == [
        ("first", "Alpha experiment"), ("second", "Beta experiment")]


def test_experiment_title_in_history_and_exports(monkeypatch) -> None:
    run = _run("titled-run", "security", ["harmbench"], [2])
    run.spec.title = "Baseline <Qwen>"
    monkeypatch.setattr(appmod.STORE, "list", lambda: [run])
    monkeypatch.setattr(appmod.STORE, "get", lambda run_id: run if run_id == run.id else None)
    client = TestClient(appmod.app)

    assert client.get("/runs?q=baseline").json()["runs"][0]["title"] == run.spec.title
    assert client.get(f"/runs/{run.id}").json()["spec"]["title"] == run.spec.title
    assert client.get(f"/runs/{run.id}/export?format=json").json()["reproducibility"]["title"] == run.spec.title
    csv = client.get(f"/runs/{run.id}/export?format=csv").text
    assert csv.startswith("experiment_title,goal,")
    assert "Baseline <Qwen>," in csv
    report = client.get(f"/runs/{run.id}/report").text
    assert "Baseline &lt;Qwen&gt;" in report
    assert "Baseline <Qwen>" not in report


def test_experiment_title_validation() -> None:
    client = TestClient(appmod.app)
    body = {"attack_id": "direct", "goals": ["test goal"], "title": "X" * 121}
    assert "title" in client.post("/runs", json=body).json()["error"]
    body["title"] = "two\nlines"
    assert "title" in client.post("/runs", json=body).json()["error"]


def test_experiment_title_created_and_restored(monkeypatch) -> None:
    from myrtia.store import db

    created = []
    monkeypatch.setattr(appmod.STORE, "list", lambda: [])

    def create(spec: RunSpec) -> Run:
        created.append(spec)
        return Run(id="new-title-run", spec=spec)

    async def do_nothing(run: Run) -> None:
        pass

    monkeypatch.setattr(appmod.STORE, "create", create)
    monkeypatch.setattr(appmod.ORCHESTRATOR, "run", do_nothing)
    client = TestClient(appmod.app)
    response = client.post("/runs", json={"attack_id": "direct", "goals": ["test goal"],
                                         "title": "  My experiment  "})
    assert response.status_code == 200
    assert created[0].title == "My experiment"

    monkeypatch.setattr(db, "load_runs", lambda: [
        {"id": "titled", "status": "succeeded", "spec": {"attack_id": "direct", "title": "My experiment"}},
        {"id": "legacy", "status": "succeeded", "spec": {"attack_id": "direct"}},
    ])
    store = RunStore()
    assert store.get("titled").spec.title == "My experiment"
    assert store.get("legacy").spec.title == ""


def test_token_usage_persisted_and_loaded(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from myrtia.store import db
    from myrtia.store.runs import Run, RunSpec, RunStore

    db_file = tmp_path / "test_runs.sqlite"
    monkeypatch.setattr(db, "_PATH", Path(db_file))
    monkeypatch.setattr(db, "_conn", None)

    run = Run(
        id="tk-run",
        spec=RunSpec(attack_id="direct", title="Tokens Test"),
        token_usage={"target": {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}},
    )
    store = RunStore()
    store.persist(run)

    # Reset conn and reload to simulate restart
    monkeypatch.setattr(db, "_conn", None)
    loaded_store = RunStore()
    restored = loaded_store.get("tk-run")
    assert restored is not None
    assert restored.token_usage == {"target": {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}}


def test_csv_export_escapes_formula_injection(monkeypatch) -> None:
    # CWE-1236: Prevent CSV formula injection by escaping cells starting with =, +, -, @, \t, \r
    run = _run("formula-injection-run", "security", ["=cmd|' /C calc'!A0"], [5])
    run.spec.title = "+Executive Summary"
    run.results = [{
        "goal": "@dangerous_goal",
        "prompt": "=2+5",
        "response": "-response with formula",
        "score": 5,
        "success": True,
    }]
    monkeypatch.setattr(appmod.STORE, "get", lambda run_id: run if run_id == run.id else None)
    client = TestClient(appmod.app)
    csv_text = client.get(f"/runs/{run.id}/export?format=csv").text
    lines = csv_text.strip().splitlines()
    assert len(lines) >= 2
    # Title starting with + should be escaped as '+
    assert "'+Executive Summary" in lines[1]
    # Goal starting with @ should be escaped as '@
    assert "'@dangerous_goal" in lines[1]
    # Prompt starting with = should be escaped as '=
    assert "'=2+5" in lines[1]
    # Response starting with - should be escaped as '-
    assert "'-response with formula" in lines[1]


