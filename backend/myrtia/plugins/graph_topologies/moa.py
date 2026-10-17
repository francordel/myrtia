"""Mixture-of-Agents topology: `rounds` layers of proposals, aggregated layer by layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("moa")
class MoaTopology(Topology):
    """Each layer, every attacker proposes seeing the previous layer's aggregate; an
    aggregator combines the layer. The final aggregate strikes."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        aggregator = eng.chairmen[0] if eng.chairmen else eng.attackers[0]
        agg, last_props, idx = "", [], 0
        for layer in range(eng.rounds):
            if eng._is_cancelled():
                break
            layer_props: list[dict] = []
            for a in eng.attackers:
                if eng._is_cancelled():
                    break
                if agg:
                    p = eng._synthesize(
                        a, goal, f"Reference {eng._instr()} so far:\n{eng._candidate_text(agg)}",
                        "Propose an improved")
                else:
                    p = eng._draft(a, goal)
                if not p:
                    continue
                layer_props.append({"original_index": idx, "model": a["model"], "proposal": p})
                eng._emit("proposal.created", turn=turn, goal_index=gi, original_index=idx,
                          model=a["model"], mutator=f"{a['id']}·moa-L{layer + 1}",
                          proposal=eng._candidate_text(p))
                idx += 1
            if not layer_props:
                continue
            last_props = layer_props
            listing = "Candidates from this layer:\n" + "\n\n".join(
                f"[{i}] {eng._candidate_text(pp['proposal'])}" for i, pp in enumerate(layer_props))
            agg = eng._synthesize(aggregator, goal, listing, "Synthesise") or layer_props[0]["proposal"]
            eng._emit("chairman.synthesized", turn=turn, goal_index=gi, model=aggregator["model"],
                      synthesized_prompt=eng._candidate_text(agg), contextual_priming=eng.contextual_mode)
        eng._turn_proposals = last_props
        eng._turn_winner = (0, aggregator["model"])
        if not agg:
            raise ValueError("Mixture-of-Agents produced no valid prompt")
        return agg
