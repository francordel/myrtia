"""Orchestrator — drives one attack run and turns it into a live event stream.

The orchestrator is the only place that knows how to instantiate and drive an
ARES-style attack strategy. The strategy call (`attack()`) is synchronous and
blocking, so it runs in a thread; events are bridged back to the asyncio event
bus thread-safely.

Live tap (see docs/architecture.md): if the plugin supports the `on_event` seam
(`set_event_emitter`), the orchestrator wires it and gets per-turn events. Until a
plugin does, it still emits run/goal-level events around the call, so the UI always
has something to render.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from copy import deepcopy
from typing import Any

from myrtia.events.bus import EventBus, BUS
from myrtia.events.schema import Event, EventType
from myrtia.plugins.base import REGISTRY, EventEmittingStrategy
from myrtia.hitl.approvals import REGISTRY as APPROVALS
from myrtia.store.runs import Run, RunStatus, RunStore, STORE, _redact_secrets

logger = logging.getLogger(__name__)


import threading as _threading


class Orchestrator:
    def __init__(self, bus: EventBus = BUS, store: RunStore = STORE) -> None:
        self._bus = bus
        self._store = store
        self._cancels: dict[str, _threading.Event] = {}

    def cancel(self, run_id: str) -> bool:
        """Request cooperative cancellation of a running attack."""
        ev = self._cancels.get(run_id)
        if ev is None:
            return False
        ev.set()
        return True

    async def run(self, run: Run) -> None:
        loop = asyncio.get_running_loop()
        cancel_ev = _threading.Event()
        self._cancels[run.id] = cancel_ev

        def emit_sync(event_type: str, payload: dict[str, Any]) -> None:
            # Called from the worker thread with primitive (type, payload). The bus is
            # thread-safe and synchronous, so we publish directly — no loop hop (which
            # was unreliable across ares-council's per-goal asyncio.run()). Unknown
            # types degrade to a LOG event rather than crashing the run.
            try:
                etype = EventType(event_type)
            except ValueError:
                etype = EventType.LOG
                payload = {"event_type": event_type, **payload}
            self._bus.publish(Event(run_id=run.id, type=etype, payload=payload))

        def emit(type_: EventType, payload: dict[str, Any] | None = None) -> None:
            self._bus.publish(Event(run_id=run.id, type=type_, payload=payload or {}))

        run.status = RunStatus.RUNNING
        self._store.persist(run)
        # Redact secrets before putting the spec on the (client-facing) event bus —
        # api_key lives in attack_config/target and must never reach a WS client.
        emit(EventType.RUN_STARTED, {"spec": _redact_secrets(deepcopy(run.spec.__dict__))})

        # Human-in-the-loop gate (issues #12/#17): when the run opts in, pause before
        # launching and wait for an operator decision. The future is created on THIS
        # loop (the one awaiting it) so a resolve from the API handler lands correctly.
        ac0 = run.spec.attack_config if isinstance(run.spec.attack_config, dict) else {}
        if ac0.get("require_approval"):
            approval = APPROVALS.request(
                run.id, "launch",
                {"target": (run.spec.target or {}).get("model"),
                 "attack": run.spec.attack_id, "n_goals": len(run.spec.goals or [])},
                loop=loop)
            run.status = RunStatus.WAITING_APPROVAL
            self._store.persist(run)
            emit(EventType.APPROVAL_REQUESTED,
                 {"approval_id": approval.id, "action": approval.action, "detail": approval.detail})
            try:
                approved = await approval.future
            except asyncio.CancelledError:
                approved = False
            emit(EventType.LOG, {"event_type": "approval.resolved",
                                 "approval_id": approval.id, "approved": bool(approved)})
            if not approved:
                run.status = RunStatus.CANCELLED
                run.error = "denied at the approval gate"
                self._store.persist(run)
                emit(EventType.RUN_FINISHED, {"status": run.status.value, "error": run.error})
                self._cancels.pop(run.id, None)
                return
            run.status = RunStatus.RUNNING
            self._store.persist(run)

        try:
            spec = REGISTRY.get(run.spec.attack_id)
            if spec is None:
                raise ValueError(f"Unknown attack plugin: {run.spec.attack_id!r}")

            # Lazy: connector import pulls in ARES only when a run actually launches.
            from myrtia.connectors.factory import build_target_connector

            # Surface the target model to the plugin so it can label events.
            if isinstance(run.spec.attack_config, dict):
                run.spec.attack_config.setdefault(
                    "target_model", (run.spec.target or {}).get("model"))

            target = build_target_connector(run.spec.target)
            # Optional shield pipeline in front of the target (defense evaluation).
            defenses = getattr(run.spec, "defenses", None)
            if defenses:
                from myrtia.defenses import DefendedConnector
                ac = run.spec.attack_config if isinstance(run.spec.attack_config, dict) else {}
                target = DefendedConnector(
                    target, defenses, emit_sync,
                    aux_model=ac.get("judge_model") or ac.get("defense_model"),
                    aux_endpoint=ac.get("judge_endpoint") or ac.get("defense_endpoint"),
                    aux_key=ac.get("api_key"),
                )
            strategy = spec.factory(run.spec.attack_config, target)

            if hasattr(strategy, "set_event_emitter"):
                strategy.set_event_emitter(emit_sync)
            if hasattr(strategy, "set_cancel_check"):
                strategy.set_cancel_check(cancel_ev.is_set)

            # Feed goals from the run spec. Plugins expose `load_goals` (Myrtia's
            # goal-ingestion seam) rather than each having a bespoke input file.
            if run.spec.goals and hasattr(strategy, "load_goals"):
                strategy.load_goals(run.spec.goals)

            # Blocking strategy call off the event loop.
            results = await loop.run_in_executor(None, strategy.attack)
            run.results = results or []
            tk = getattr(target, "tokens", None)
            if isinstance(tk, dict) and tk.get("total"):
                run.token_usage = {"target": dict(tk)}
            run.status = RunStatus.CANCELLED if cancel_ev.is_set() else RunStatus.SUCCEEDED
            self._store.persist(run)
            emit(
                EventType.RUN_FINISHED,
                {"status": run.status.value, "n_results": len(run.results)},
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            run.status = RunStatus.FAILED
            run.error = f"{type(exc).__name__}: {exc}"
            self._store.persist(run)
            # Full traceback stays server-side (logs); the client gets a clean message,
            # never a raw stack trace (which can carry endpoints/paths).
            logger.error("Run %s failed:\n%s", run.id, traceback.format_exc())
            emit(
                EventType.RUN_FINISHED,
                {"status": run.status.value, "error": run.error},
            )


ORCHESTRATOR = Orchestrator()
