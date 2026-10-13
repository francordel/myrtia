"""Human-in-the-loop approval gate.

PentAGI only offers conversational steering; Myrtia adds a real per-action gate
(see docs/architecture.md). The orchestrator calls `request()` before a sensitive
step and awaits the returned future; the API resolves it from the UI via `resolve()`.
Each request also surfaces as an APPROVAL_REQUESTED event so the UI can prompt.

Issue #17: the future must be bound to the event loop that will await it. Creating a
bare ``asyncio.Future()`` binds it to whatever loop happens to be current at
construction time (or none), so resolving it from the API request handler — a
different task on the same loop, or via a threadsafe hop from a worker thread — could
target the wrong loop. We therefore create the future from the loop passed by the
orchestrator (``loop.create_future()``) and resolve it through ``call_soon_threadsafe``
so a resolve is safe from any thread.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Approval:
    id: str
    run_id: str
    action: str
    detail: dict[str, Any] = field(default_factory=dict)
    future: Optional[asyncio.Future] = None            # bound to the awaiting loop
    loop: Optional[asyncio.AbstractEventLoop] = None
    event: threading.Event = field(default_factory=threading.Event)  # sync-wait path
    decision: bool = False

    def wait(self, timeout: float | None = None) -> bool:
        """Block the calling (worker) thread until resolved; returns the decision."""
        self.event.wait(timeout)
        return self.decision


class ApprovalRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, Approval] = {}
        self._lock = threading.Lock()

    def request(self, run_id: str, action: str, detail: dict[str, Any] | None = None,
                loop: asyncio.AbstractEventLoop | None = None) -> Approval:
        """Create a pending approval. Pass the loop that will await it so the future is
        bound to the correct loop (issue #17). If no loop is given, fall back to the
        running loop when there is one; otherwise leave the future unset (sync-wait only).
        """
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
        approval = Approval(id=uuid.uuid4().hex, run_id=run_id, action=action, detail=detail or {}, loop=loop)
        if loop is not None:
            approval.future = loop.create_future()
        with self._lock:
            self._pending[approval.id] = approval
        return approval

    def resolve(self, approval_id: str, decision: bool) -> bool:
        with self._lock:
            approval = self._pending.pop(approval_id, None)
        if approval is None:
            return False
        approval.decision = bool(decision)
        approval.event.set()  # release any sync waiter
        fut, loop = approval.future, approval.loop
        if fut is not None and loop is not None:
            # Resolve on the future's own loop, safe from any thread.
            loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(bool(decision)))
        return True

    def pending(self, run_id: str | None = None) -> list[Approval]:
        with self._lock:
            return [a for a in self._pending.values() if run_id is None or a.run_id == run_id]


REGISTRY = ApprovalRegistry()
