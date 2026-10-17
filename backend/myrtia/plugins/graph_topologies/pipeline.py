"""Pipeline / relay topology: attackers in sequence, each refines the previous draft."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("pipeline", "relay")
class PipelineTopology(Topology):
    """A refinement chain: the first agent drafts, each next refines, the last strikes."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        eng._turn_proposals = []
        draft = ""
        for i, a in enumerate(eng.attackers):
            if eng._is_cancelled():
                break
            if i == 0 or not draft:
                draft = eng._draft(a, goal) or draft
            else:
                refined = eng._synthesize(
                    a, goal, f"Current {eng._instr()}:\n{eng._candidate_text(draft)}", "Improve it into")
                draft = refined or draft
            if draft:
                eng._turn_proposals.append({"original_index": i, "model": a["model"],
                                            "proposal": eng._candidate_text(draft)})
                eng._emit("proposal.created", turn=turn, goal_index=gi, original_index=i,
                          model=a["model"], mutator=f"{a['id']}·relay",
                          proposal=eng._candidate_text(draft))
        eng._turn_winner = (len(eng.attackers) - 1, eng.attackers[-1]["model"])
        if not draft:
            raise ValueError("Pipeline produced no valid prompt")
        return draft
