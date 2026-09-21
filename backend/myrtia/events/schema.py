"""Myrtia event schema — the live-view contract.

Every meaningful step of an attack run is one typed event. The orchestrator puts
these on the bus; the API fans them out over a per-run WebSocket; the React UI
renders the deliberation from them. Kept dependency-free (stdlib only) on purpose.

See docs/architecture.md ("Event schema") for the rationale.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class EventType(str, Enum):
    # run lifecycle
    RUN_STARTED = "run.started"
    RUN_FINISHED = "run.finished"
    # per-behaviour / per-turn
    GOAL_STARTED = "goal.started"
    TURN_STARTED = "turn.started"
    # CouncilAttack deliberation
    PROPOSAL_CREATED = "proposal.created"      # {model, mutator, proposal, template}
    CRITIQUE_CREATED = "critique.created"      # {critic, rankings, reasons}
    VOTE_AGGREGATED = "vote.aggregated"        # {borda_scores, top1_votes, winner}
    CHAIRMAN_SYNTHESIZED = "chairman.synthesized"  # {synthesized_prompt}
    TARGET_RESPONDED = "target.responded"      # {target_prompt, target_response}
    JUDGE_SCORED = "judge.scored"              # {score: 0-5, rationale}
    # human-in-the-loop
    APPROVAL_REQUESTED = "approval.requested"  # {approval_id, action, detail}
    APPROVAL_RESOLVED = "approval.resolved"    # {approval_id, decision}
    # catch-all
    LOG = "log"                                # {level, message}


@dataclass
class Event:
    """One event on a run's stream.

    `seq` is a per-run monotonic counter the orchestrator assigns so the UI can
    order/deduplicate; `ts` is wall-clock for display.
    """

    run_id: str
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    ts: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d
