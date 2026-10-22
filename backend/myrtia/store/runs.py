"""Run store — in-memory for the MVP (single process).

Holds run specs, status and final results. A SQLite backing is a Phase 4 swap
behind the same interface; nothing else in the backend should touch storage
internals directly.
"""

from __future__ import annotations

import re
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


_SECRET_HINTS = ("api_key", "apikey", "key", "token", "secret", "password", "authorization", "bearer")
_SECRET_VALUE_RE = re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{6,}|sk-[A-Za-z0-9_-]{8,})\b")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}")


def _scrub_value(s: str) -> str:
    s = _SECRET_VALUE_RE.sub("***redacted***", s)
    s = _BEARER_RE.sub("Bearer ***redacted***", s)
    return s


def _redact_secrets(obj: Any) -> Any:
    """Recursively blank secret-looking fields (by key name) and scrub secret-looking
    values (API keys / bearer tokens) in strings, so the API never returns keys."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(h in kl for h in _SECRET_HINTS) and isinstance(v, str) and v:
                obj[k] = "***redacted***"
            elif kl in ("headers", "extra_body") and isinstance(v, dict):
                # Custom agent auth lives under arbitrary header/body key names
                # (e.g. X-Custom-Auth) that the key-name hints miss — blank all
                # of their string values so no secret is persisted/returned.
                obj[k] = {hk: ("***redacted***" if isinstance(hv, str) and hv
                               else _redact_secrets(hv))
                          for hk, hv in v.items()}
            else:
                obj[k] = _redact_secrets(v)
        return obj
    if isinstance(obj, list):
        for i, it in enumerate(obj):
            obj[i] = _redact_secrets(it)
        return obj
    if isinstance(obj, str):
        return _scrub_value(obj)
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
    title: str = ""                       # human-readable experiment name
    defenses: list = field(default_factory=list)  # ordered shield pipeline in front of the target
    purpose: str = "unreviewed"              # security | smoke | unreviewed (legacy)
    goal_datasets: list[str] = field(default_factory=list)  # parallel to goals


@dataclass
class Run:
    id: str
    spec: RunSpec
    status: RunStatus = RunStatus.PENDING
    created_at: float = field(default_factory=time.time)
    error: str | None = None
    results: list[dict] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        _redact_secrets(d.get("spec", {}))
        return d

    def best_score(self) -> int | None:
        """Max graded judge score across all turns/goals (None if unjudged).

        Multi-turn attacks (council, graph, crescendo, tap) carry a per-turn
        ``council_turns`` list with ``judge_score``; single-turn attacks carry a
        flat ``score`` per result. Read both so every judged run reports a best
        score to History and the outcome filter."""
        best: int | None = None

        def bump(s: Any) -> None:
            nonlocal best
            if isinstance(s, int) and not isinstance(s, bool):
                best = s if best is None else max(best, s)

        for r in self.results:
            turns = r.get("council_turns") or []
            for t in turns:
                bump(t.get("judge_score"))
            if not turns:
                bump(r.get("score"))
        return best

    def summary(self) -> dict[str, Any]:
        """Compact record for the searchable/filterable run history."""
        return {
            "id": self.id,
            "attack_id": self.spec.attack_id,
            "theme": self.spec.theme,
            "title": self.spec.title,
            "goals": self.spec.goals,
            "status": self.status.value,
            "created_at": self.created_at,
            "best_score": self.best_score(),
            "target_model": (self.spec.target or {}).get("model"),
            "error": self.error,
            "purpose": self.spec.purpose,
            "goal_datasets": self.spec.goal_datasets,
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
                title=spec_data.get("title", ""),
                defenses=spec_data.get("defenses", []),
                purpose=spec_data.get("purpose", "unreviewed"),
                goal_datasets=spec_data.get("goal_datasets", []),
            )
            try:
                status = RunStatus(row.get("status", "pending"))
            except ValueError:
                status = RunStatus.PENDING
            error = row.get("error")
            run = Run(id=row["id"], spec=spec, status=status,
                      created_at=row.get("created_at") or time.time(),
                      error=error, results=row.get("results") or [],
                      token_usage=row.get("token_usage") or {})
            self._runs[run.id] = run

    def cleanup_orphaned_runs(self) -> int:
        """Mark stale RUNNING or PENDING runs from a previous backend session as interrupted.

        Called exclusively during FastAPI server startup lifespan, never at module import time,
        preventing CLI tools or background workers from aborting active runs in flight.
        """
        count = 0
        for run in list(self._runs.values()):
            if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
                run.status = RunStatus.FAILED
                run.error = run.error or "interrupted (backend restarted)"
                self.persist(run)
                count += 1
        return count

    def create(self, spec: RunSpec) -> Run:
        run = Run(id=uuid.uuid4().hex, spec=spec)
        self._runs[run.id] = run
        self.persist(run)
        return run

    def persist(self, run: Run) -> None:
        """Write a run through to SQLite (spec redacted; results have no secrets)."""
        from myrtia.store import db
        spec = _redact_secrets(deepcopy(run.spec.__dict__))
        db.save_run(run.id, run.created_at, run.status.value, run.error, spec, run.results, run.token_usage)

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list(self) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)


STORE = RunStore()
