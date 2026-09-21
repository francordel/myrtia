"""Human-in-the-loop approval gate.

PentAGI only offers conversational steering; Myrtia adds a real per-action gate
(see docs/architecture.md). The orchestrator calls `request()` before a sensitive
step and awaits the returned future; the API resolves it from the UI via `resolve()`.
Each request also surfaces as an APPROVAL_REQUESTED event so the UI can prompt.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Approval:
    id: str
    run_id: str
    action: str
    detail: dict[str, Any] = field(default_factory=dict)
    future: asyncio.Future[bool] = field(default_factory=asyncio.Future)


class ApprovalRegistry:
    def __init__(self) -> None:
        self._pending: dict[str, Approval] = {}

    def request(self, run_id: str, action: str, detail: dict[str, Any] | None = None) -> Approval:
        approval = Approval(
            id=uuid.uuid4().hex, run_id=run_id, action=action, detail=detail or {}
        )
        self._pending[approval.id] = approval
        return approval

    def resolve(self, approval_id: str, decision: bool) -> bool:
        approval = self._pending.pop(approval_id, None)
        if approval is None or approval.future.done():
            return False
        approval.future.set_result(decision)
        return True

    def pending(self, run_id: str | None = None) -> list[Approval]:
        return [
            a for a in self._pending.values() if run_id is None or a.run_id == run_id
        ]


REGISTRY = ApprovalRegistry()
