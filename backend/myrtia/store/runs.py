"""Run store — in-memory for the MVP (single process).

Holds run specs, status and final results. A SQLite backing is a Phase 4 swap
behind the same interface; nothing else in the backend should touch storage
internals directly.
"""

from __future__ import annotations

import time
import uuid
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

    def create(self, spec: RunSpec) -> Run:
        run = Run(id=uuid.uuid4().hex, spec=spec)
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list(self) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)


STORE = RunStore()
