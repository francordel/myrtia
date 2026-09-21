"""Event bus: a thread-safe, append-only per-run backlog.

Events are produced from two places: the orchestrator coroutine (run lifecycle) and
the attack strategy running in a worker thread (per-turn events). To make delivery
robust across both — and across ares-council's internal `asyncio.run()` per goal,
which spins up and tears down its own loop in the worker thread — the bus is a plain
synchronous structure guarded by a threading lock. No asyncio loop hops, no
per-subscriber queues: the WebSocket handler streams by polling `backlog()` and
replaying new entries in order, so every event is delivered regardless of when a
client connects (see api/app.py).
"""

from __future__ import annotations

import threading
from collections import defaultdict

from myrtia.events.schema import Event, EventType


class EventBus:
    def __init__(self) -> None:
        self._backlog: dict[str, list[Event]] = defaultdict(list)
        self._seq: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Restore event backlogs from SQLite so live-replay survives restarts."""
        from myrtia.store import db
        for run_id, evs in db.load_events().items():
            for e in evs:
                try:
                    et = EventType(e["type"])
                except ValueError:
                    et = EventType.LOG
                ev = Event(run_id=run_id, type=et, payload=e.get("payload", {}),
                           seq=e["seq"], ts=e.get("ts", 0.0), id=e.get("id", ""))
                self._backlog[run_id].append(ev)
                self._seq[run_id] = max(self._seq[run_id], e["seq"])

    def publish(self, event: Event) -> Event:
        """Assign the event its per-run sequence number, append it, persist it."""
        with self._lock:
            self._seq[event.run_id] += 1
            event.seq = self._seq[event.run_id]
            self._backlog[event.run_id].append(event)
        from myrtia.store import db
        db.append_event(event.run_id, event.seq, event.ts, event.type.value,
                        event.payload, event.id)
        return event

    def backlog(self, run_id: str) -> list[Event]:
        with self._lock:
            return list(self._backlog[run_id])


# Process-wide bus for the MVP (single-process backend).
BUS = EventBus()
