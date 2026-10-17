"""Council topology (and its chairman variant).

Propose -> cross-critique + Borda Top-1 -> optional chairman chain -> strike. This is
also the engine's default and the fallback for unknown modes. The `chairman` mode maps
here too: it is the same handler, distinguished only by whether chairman agents are
present and `use_chairman` is set (the frontend sends that for the chairman topology).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_common import _CHAIRMAN_SYSTEM, _CONTEXTUAL_CHAIRMAN_SYSTEM
from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("council", "chairman")
class CouncilTopology(Topology):
    """N equal attackers propose and Borda-vote; chairmen (if any) refine the winner in a chain."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        props = eng._propose_all(goal, turn, gi)
        winner = eng._borda_vote(goal, turn, gi, props)
        # chairman(s) synthesise in a CHAIN — each refines the previous draft.
        strike = winner["proposal"]
        if eng.use_chairman and eng.chairmen:
            listing = eng._proposal_listing(props, winner)
            for ch in eng.chairmen:
                if eng._is_cancelled():
                    break
                instruction = "dialogue template" if eng.contextual_mode else "prompt"
                user = (f"OBJECTIVE: {goal}{eng._turn_feedback}\n\nCandidates:\n{listing}\n\n"
                        f"{eng._critique_summary()}"
                        f"Current draft:\n{eng._candidate_text(strike)}\n\n"
                        f"Give the final {instruction} as JSON.")
                raw = eng._agent_generate(
                    ch, _CONTEXTUAL_CHAIRMAN_SYSTEM if eng.contextual_mode else _CHAIRMAN_SYSTEM,
                    user,
                    template_required=eng.contextual_mode)
                candidate = eng._candidate(raw)
                if not candidate and eng.contextual_mode:
                    eng._emit("log", level="warning", turn=turn, goal_index=gi,
                              message="Chairman returned an invalid dialogue; using the valid council winner.")
                strike = candidate or strike
                eng._emit("chairman.synthesized", turn=turn, goal_index=gi,
                          model=ch["model"], synthesized_prompt=eng._candidate_text(strike),
                          contextual_priming=eng.contextual_mode)
        return strike
