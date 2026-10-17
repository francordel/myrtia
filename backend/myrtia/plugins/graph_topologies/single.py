"""Single-attacker topology: one agent drafts the strike, no vote, no chairman."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_common import _tool_prompt
from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("single")
class SingleTopology(Topology):
    """One attacker drafts the prompt directly (optionally via its first granted tool)."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        a = eng.attackers[0]
        tools = a.get("tools") or []
        base = (_tool_prompt(tools[0], goal, (a.get("tool_cfg") or {}).get(tools[0])) or goal) if tools else ""
        prompt = eng._draft(a, goal, base)
        if not prompt:
            raise ValueError("Attacker did not produce a valid contextual-priming dialogue")
        eng._emit("proposal.created", turn=turn, goal_index=gi, original_index=0,
                  model=a["model"], mutator=a["id"], proposal=eng._candidate_text(prompt))
        eng._turn_proposals = [{"original_index": 0, "model": a["model"], "proposal": eng._candidate_text(prompt)}]
        eng._turn_winner = (0, a["model"])
        return prompt
