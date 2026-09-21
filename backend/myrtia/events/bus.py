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

from myrtia.events.schema import Event


class EventBus:
    def __init__(self) -> None:
        self._backlog: dict[str, list[Event]] = defaultdict(list)
        self._seq: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def publish(self, event: Event) -> Event:
        """Assign the event its per-run sequence number and append it. Thread-safe."""
        with self._lock:
            self._seq[event.run_id] += 1
            event.seq = self._seq[event.run_id]
            self._backlog[event.run_id].append(event)
        return event

    def backlog(self, run_id: str) -> list[Event]:
        with self._lock:
            return list(self._backlog[run_id])


# Process-wide bus for the MVP (single-process backend).
BUS = EventBus()
