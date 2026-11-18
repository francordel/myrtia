"""Metrics: what the models and the runs are doing, in the Prometheus text format.

A small in-process registry (standard library only) fed from two places every run
already passes through: the connectors report each model call (`record_model_call`)
and the event bus reports each published event (`observe_event`). `render()` is served
at `GET /metrics`; see docs/observability.md for the dashboard that reads it.

Rules kept here on purpose:
  * Labels are bounded: role, model, attack, status, score, shield id, event type. A
    run id is a label only for the most recent runs (`RUN_LIMIT`), then it is dropped.
  * Nothing sensitive is a label: no prompt, reply, goal, key, header or endpoint.
  * Recording never raises: a metrics problem must not break a model call or a run.
  * Counters start at zero with the process; nothing is rebuilt from stored runs.
"""

from __future__ import annotations

import contextvars
import logging
import os
import threading
from collections import OrderedDict
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_CALL_BUCKETS = (0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)
_RUN_BUCKETS = (5, 15, 30, 60, 120, 300, 600, 1800, 3600)

# name -> (type, help, label names, histogram buckets)
CATALOG: dict[str, tuple[str, str, tuple[str, ...], tuple[float, ...]]] = {
    "myrtia_build_info": ("gauge", "Myrtia version, always 1.", ("version",), ()),
    "myrtia_model_calls_total": (
        "counter", "Model calls by caller role, model and outcome.",
        ("role", "model", "outcome"), ()),
    "myrtia_model_call_duration_seconds": (
        "histogram", "Duration of model calls by caller role and model.",
        ("role", "model"), _CALL_BUCKETS),
    "myrtia_model_tokens_total": (
        "counter", "Tokens reported by model replies, by caller role, model and kind.",
        ("role", "model", "kind"), ()),
    "myrtia_runs_started_total": ("counter", "Runs started, by attack.", ("attack",), ()),
    "myrtia_runs_finished_total": (
        "counter", "Runs finished, by attack and final status.", ("attack", "status"), ()),
    "myrtia_runs_active": ("gauge", "Runs in flight, by attack.", ("attack",), ()),
    "myrtia_run_duration_seconds": (
        "histogram", "Duration of finished runs, by attack.", ("attack",), _RUN_BUCKETS),
    "myrtia_judge_scores_total": (
        "counter", "Judge verdicts by attack and score (0-5, or invalid).",
        ("attack", "score"), ()),
    "myrtia_defense_actions_total": (
        "counter", "Shield actions by shield and action (applied or blocked).",
        ("defense", "action"), ()),
    "myrtia_events_total": ("counter", "Events published on run streams, by type.", ("type",), ()),
    "myrtia_run_model_calls_total": (
        "counter", "Model calls of a recent run, by role.", ("run", "attack", "role"), ()),
    "myrtia_run_tokens_total": (
        "counter", "Tokens of a recent run, by role and kind.",
        ("run", "attack", "role", "kind"), ()),
    "myrtia_run_model_seconds_total": (
        "counter", "Time a recent run spent waiting for models, by role.",
        ("run", "attack", "role"), ()),
}
_PER_RUN = tuple(n for n, spec in CATALOG.items() if "run" in spec[2])

# How many runs keep their per-run series (spec 008, FR-13/FR-14).
RUN_LIMIT = max(1, int(os.getenv("MYRTIA_METRICS_RUNS", "20") or 20))


def exported_names() -> set[str]:
    """Every sample name `render()` can produce (histograms add their three suffixes)."""
    out: set[str] = set()
    for name, (kind, *_rest) in CATALOG.items():
        out |= {f"{name}_bucket", f"{name}_sum", f"{name}_count"} if kind == "histogram" else {name}
    return out


_INF = 'le="+Inf"'


def _escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(float(v))


class Metrics:
    """Thread-safe counters, gauges and histograms keyed by (metric, label values)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, dict[tuple[str, ...], float]] = {}
        self._hists: dict[str, dict[tuple[str, ...], list[float]]] = {}

    def _key(self, name: str, labels: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(labels.get(k, "")) for k in CATALOG[name][2])

    def inc(self, name: str, labels: dict[str, Any], amount: float = 1) -> None:
        """Add to a counter or a gauge."""
        key = self._key(name, labels)
        with self._lock:
            series = self._values.setdefault(name, {})
            series[key] = series.get(key, 0) + amount

    def set(self, name: str, labels: dict[str, Any], value: float) -> None:
        with self._lock:
            self._values.setdefault(name, {})[self._key(name, labels)] = value

    def observe(self, name: str, labels: dict[str, Any], value: float) -> None:
        buckets = CATALOG[name][3]
        key = self._key(name, labels)
        with self._lock:
            h = self._hists.setdefault(name, {}).setdefault(key, [0.0] * (len(buckets) + 2))
            for i, le in enumerate(buckets):
                if value <= le:
                    h[i] += 1
                    break
            h[-2] += value
            h[-1] += 1

    def drop(self, names: tuple[str, ...], label: str, value: str) -> None:
        """Remove every series of `names` whose `label` equals `value`."""
        with self._lock:
            for name in names:
                i = CATALOG[name][2].index(label)
                series = self._values.get(name, {})
                for key in [k for k in series if k[i] == value]:
                    del series[key]

    def clear(self) -> None:
        with self._lock:
            self._values.clear()
            self._hists.clear()

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name, (kind, help_, label_names, buckets) in CATALOG.items():
                lines.append(f"# HELP {name} {help_}")
                lines.append(f"# TYPE {name} {kind}")

                def fmt(key: tuple[str, ...], extra: str = "") -> str:
                    parts = [f'{k}="{_escape(v)}"' for k, v in zip(label_names, key)]
                    if extra:
                        parts.append(extra)
                    return "{" + ",".join(parts) + "}" if parts else ""

                if kind == "histogram":
                    for key, h in sorted(self._hists.get(name, {}).items()):
                        running = 0.0
                        for i, le in enumerate(buckets):
                            running += h[i]
                            le_label = 'le="' + _num(le) + '"'
                            lines.append(f"{name}_bucket{fmt(key, le_label)} {_num(running)}")
                        lines.append(f"{name}_bucket{fmt(key, _INF)} {_num(h[-1])}")
                        lines.append(f"{name}_sum{fmt(key)} {_num(h[-2])}")
                        lines.append(f"{name}_count{fmt(key)} {_num(h[-1])}")
                else:
                    for key, v in sorted(self._values.get(name, {}).items()):
                        lines.append(f"{name}{fmt(key)} {_num(v)}")
        return "\n".join(lines) + "\n"


METRICS = Metrics()

# --- run bookkeeping ---------------------------------------------------------------
_state_lock = threading.Lock()
_open_runs: dict[str, tuple[str, float]] = {}        # run id -> (attack, start ts), from events
_run_series: "OrderedDict[str, bool]" = OrderedDict()  # run id -> finished?, oldest first
_RUN: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "myrtia_run", default=None)


def bind_run(run_id: str, attack: str) -> None:
    """Attach the current context to a run, so the model calls made in it feed that
    run's series. The orchestrator copies this context into the attack's worker thread."""
    _RUN.set((str(run_id), str(attack or "unknown")))


@contextmanager
def run_context(run_id: str, attack: str) -> Iterator[None]:
    token = _RUN.set((str(run_id), str(attack or "unknown")))
    try:
        yield
    finally:
        _RUN.reset(token)


def _track_run(run_id: str) -> None:
    """Remember that `run_id` has per-run series; evict beyond RUN_LIMIT, finished first."""
    evicted: list[str] = []
    with _state_lock:
        if run_id in _run_series:
            return
        _run_series[run_id] = False
        while len(_run_series) > RUN_LIMIT:
            victim = next((r for r, done in _run_series.items() if done and r != run_id),
                          next(r for r in _run_series if r != run_id))
            del _run_series[victim]
            evicted.append(victim)
    for victim in evicted:
        METRICS.drop(_PER_RUN, "run", victim)


# --- recording ---------------------------------------------------------------------
def record_model_call(role: str, model: str, ok: bool, seconds: float,
                      prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    """One finished model call. Never raises."""
    try:
        role, model = str(role or "aux"), str(model or "unknown")
        seconds = max(0.0, float(seconds))
        METRICS.inc("myrtia_model_calls_total",
                    {"role": role, "model": model, "outcome": "ok" if ok else "error"})
        METRICS.observe("myrtia_model_call_duration_seconds", {"role": role, "model": model}, seconds)
        tokens = (("prompt", int(prompt_tokens or 0)), ("completion", int(completion_tokens or 0)))
        for kind, n in tokens:
            if n > 0:
                METRICS.inc("myrtia_model_tokens_total",
                            {"role": role, "model": model, "kind": kind}, n)
        bound = _RUN.get()
        if bound is None:
            return
        run_id, attack = bound
        _track_run(run_id)
        labels = {"run": run_id, "attack": attack, "role": role}
        METRICS.inc("myrtia_run_model_calls_total", labels)
        METRICS.inc("myrtia_run_model_seconds_total", labels, seconds)
        for kind, n in tokens:
            if n > 0:
                METRICS.inc("myrtia_run_tokens_total", {**labels, "kind": kind}, n)
    except Exception:  # noqa: BLE001 - metrics must never break a model call
        logger.debug("could not record a model call", exc_info=True)


def observe_event(event: Any) -> None:
    """Update the run, judge, shield and event metrics from one published event.
    Never raises."""
    try:
        etype = getattr(event.type, "value", str(event.type))
        payload = event.payload if isinstance(event.payload, dict) else {}
        run_id = str(event.run_id)
        METRICS.inc("myrtia_events_total", {"type": etype})

        if etype == "run.started":
            spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
            attack = str(spec.get("attack_id") or "unknown")
            with _state_lock:
                known = run_id in _open_runs
                _open_runs[run_id] = (attack, float(event.ts))
            METRICS.inc("myrtia_runs_started_total", {"attack": attack})
            if not known:
                METRICS.inc("myrtia_runs_active", {"attack": attack})
        elif etype == "run.finished":
            with _state_lock:
                opened = _open_runs.pop(run_id, None)
                if run_id in _run_series:
                    _run_series[run_id] = True
            attack = opened[0] if opened else "unknown"
            METRICS.inc("myrtia_runs_finished_total",
                        {"attack": attack, "status": str(payload.get("status") or "unknown")})
            if opened:
                METRICS.inc("myrtia_runs_active", {"attack": attack}, -1)
                METRICS.observe("myrtia_run_duration_seconds", {"attack": attack},
                                max(0.0, float(event.ts) - opened[1]))
        elif etype == "judge.scored":
            with _state_lock:
                attack = _open_runs.get(run_id, ("unknown", 0.0))[0]
            score = payload.get("score")
            valid = isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 5
            METRICS.inc("myrtia_judge_scores_total",
                        {"attack": attack, "score": str(score) if valid else "invalid"})
        elif etype in ("defense.applied", "defense.blocked"):
            METRICS.inc("myrtia_defense_actions_total",
                        {"defense": str(payload.get("id") or "unknown"),
                         "action": etype.split(".", 1)[1]})
    except Exception:  # noqa: BLE001 - metrics must never break a run
        logger.debug("could not record an event", exc_info=True)


def render(version: str | None = None) -> str:
    """The current metrics as Prometheus text. `version` fills `myrtia_build_info`."""
    if version:
        METRICS.set("myrtia_build_info", {"version": version}, 1)
    return METRICS.render()


def reset() -> None:
    """Forget everything (tests, and the meaning of a process restart)."""
    METRICS.clear()
    with _state_lock:
        _open_runs.clear()
        _run_series.clear()
