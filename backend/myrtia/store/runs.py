"""Run store — in-memory for the MVP (single process).

Holds run specs, status and final results. A SQLite backing is a Phase 4 swap
behind the same interface; nothing else in the backend should touch storage
internals directly.
"""

from __future__ import annotations

import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


_SECRET_KEYS = {"api_key", "openai_api_key", "anthropic_api_key", "key", "token"}


def _redact_secrets(obj: Any) -> Any:
    """Recursively blank out secret-looking fields so the API never returns keys."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in _SECRET_KEYS and isinstance(v, str) and v:
                obj[k] = "***redacted***"
            else:
                _redact_secrets(v)
    elif isinstance(obj, list):
        for it in obj:
            _redact_secrets(it)
    return obj


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunSpec:
    """Everything needed to launch an attack run."""

    attack_id: str                       # plugin id, e.g. "council"
    attack_config: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict)  # Myrtia target spec
    goals: list[str] = field(default_factory=list)        # behaviours to attack
    judge_id: str | None = None
    theme: str = ""                       # operator tag/topic for search & filtering


@dataclass
class Run:
    id: str
    spec: RunSpec
    status: RunStatus = RunStatus.PENDING
    created_at: float = field(default_factory=time.time)
    error: str | None = None
    results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        _redact_secrets(d.get("spec", {}))
        return d

    def best_score(self) -> int | None:
        """Max graded judge score across all turns/goals (None if unjudged)."""
        best: int | None = None
        for r in self.results:
            for t in r.get("council_turns", []) or []:
                s = t.get("judge_score")
                if isinstance(s, int):
                    best = s if best is None else max(best, s)
        return best

    def summary(self) -> dict[str, Any]:
        """Compact record for the searchable/filterable run history."""
        return {
            "id": self.id,
            "attack_id": self.spec.attack_id,
            "theme": self.spec.theme,
            "goals": self.spec.goals,
            "status": self.status.value,
            "created_at": self.created_at,
            "best_score": self.best_score(),
            "target_model": (self.spec.target or {}).get("model"),
            "error": self.error,
        }


class RunStore:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._load()

    def _load(self) -> None:
        """Restore runs from SQLite on startup so history survives restarts."""
        from myrtia.store import db
        for row in db.load_runs():
            spec_data = row.get("spec") or {}
            spec = RunSpec(
                attack_id=spec_data.get("attack_id", "?"),
                attack_config=spec_data.get("attack_config", {}),
                target=spec_data.get("target", {}),
                goals=spec_data.get("goals", []),
                judge_id=spec_data.get("judge_id"),
                theme=spec_data.get("theme", ""),
            )
            try:
                status = RunStatus(row.get("status", "pending"))
            except ValueError:
                status = RunStatus.PENDING
            error = row.get("error")
            # A run still marked RUNNING/PENDING at load time is an orphan (its
            # process died on a previous restart) — mark it interrupted, not running.
            if status in (RunStatus.RUNNING, RunStatus.PENDING):
                status = RunStatus.FAILED
                error = error or "interrupted (backend restarted)"
            run = Run(id=row["id"], spec=spec, status=status,
                      created_at=row.get("created_at") or time.time(),
                      error=error, results=row.get("results") or [])
            self._runs[run.id] = run
            if status == RunStatus.FAILED and error and "interrupted" in error:
                self.persist(run)  # write back the corrected status

    def create(self, spec: RunSpec) -> Run:
        run = Run(id=uuid.uuid4().hex, spec=spec)
        self._runs[run.id] = run
        self.persist(run)
        return run

    def persist(self, run: Run) -> None:
        """Write a run through to SQLite (spec redacted; results have no secrets)."""
        from myrtia.store import db
        spec = _redact_secrets(deepcopy(run.spec.__dict__))
        db.save_run(run.id, run.created_at, run.status.value, run.error, spec, run.results)

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list(self) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)


STORE = RunStore()
