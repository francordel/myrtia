from pathlib import Path
import time
from unittest.mock import patch

from myrtia.store.runs import RunSpec, RunStatus, RunStore
from myrtia.store import db


def test_run_store_load_does_not_corrupt_active_runs(tmp_path: Path):
    db_file = tmp_path / "test_runs.db"
    with patch("myrtia.store.db._PATH", db_file), patch("myrtia.store.db._conn", None):
        # 1. Save an active run directly to SQLite
        spec = RunSpec(attack_id="base64", target={"model": "test"}, goals=["goal1"])
        db.save_run(
            run_id="run-active-123",
            created_at=time.time(),
            status="running",
            error=None,
            spec=spec.__dict__,
            results=[],
        )

        # 2. Instantiate a new RunStore (simulating a secondary process / import)
        store = RunStore()
        run = store.get("run-active-123")
        assert run is not None
        # It must NOT be marked as failed or interrupted
        assert run.status == RunStatus.RUNNING
        assert run.error is None

        # Verify DB was not overwritten with FAILED
        rows = db.load_runs()
        row = next(r for r in rows if r["id"] == "run-active-123")
        assert row["status"] == "running"
        assert row["error"] is None

        # 3. Explicitly invoking cleanup_orphaned_runs (lifespan startup) should mark it interrupted
        cleaned = store.cleanup_orphaned_runs()
        assert cleaned == 1
        assert store.get("run-active-123").status == RunStatus.FAILED
        assert "interrupted" in store.get("run-active-123").error

        # Verify DB is now updated
        rows = db.load_runs()
        row = next(r for r in rows if r["id"] == "run-active-123")
        assert row["status"] == "failed"
        assert "interrupted" in row["error"]
