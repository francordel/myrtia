"""Parallel topology: several chairmen synthesise independently; the strongest is struck."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.council_prompts import critic_prompt
from myrtia.plugins.graph_common import (
    _CHAIRMAN_SYSTEM,
    _CONTEXTUAL_CHAIRMAN_SYSTEM,
    _parse_ranking,
)
from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("parallel")
class ParallelTopology(Topology):
    """Attackers propose + vote, then each chairman synthesises independently (best-of-N)."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        props = eng._propose_all(goal, turn, gi)
        winner = eng._borda_vote(goal, turn, gi, props)
        if not eng.chairmen:
            return winner["proposal"]
        listing = eng._proposal_listing(props, winner)
        cands: list[dict] = []
        for ci, ch in enumerate(eng.chairmen):
            if eng._is_cancelled():
                break
            raw = eng._agent_generate(
                ch, _CONTEXTUAL_CHAIRMAN_SYSTEM if eng.contextual_mode else _CHAIRMAN_SYSTEM,
                f"OBJECTIVE: {goal}{eng._turn_feedback}\n\nCandidates:\n{listing}\n\n"
                f"{eng._critique_summary()}Give your best final {'dialogue template' if eng.contextual_mode else 'prompt'} as JSON.",
                template_required=eng.contextual_mode)
            candidate = eng._candidate(raw)
            if not candidate and eng.contextual_mode:
                eng._emit("log", level="warning", turn=turn, goal_index=gi,
                          message="Chairman returned an invalid dialogue; using the valid council winner.")
            cands.append({"original_index": ci, "model": ch["model"], "proposal": candidate or winner["proposal"]})
        # pick the strongest synthesis (silent attacker tally; no extra vote event)
        best = 0
        if len(cands) > 1:
            tally = {c["original_index"]: 0 for c in cands}
            listing2 = "\n".join(f"[{c['original_index']}] {eng._candidate_text(c['proposal'])}" for c in cands)
            critic_system, critic_user = critic_prompt(len(cands), listing2, goal)
            for a in eng.attackers:
                if eng._is_cancelled():
                    break
                clean = _parse_ranking(eng._agent_generate(
                    a, critic_system, critic_user,
                    max_tokens=eng.critic_max_tokens, temperature=0.3),
                    set(tally))
                for pos, oi in enumerate(clean):
                    tally[oi] += max(0, len(cands) - 1 - pos)
            best = max(tally, key=lambda i: tally[i])
        for c in cands:
            eng._emit("chairman.synthesized", turn=turn, goal_index=gi, model=c["model"],
                      synthesized_prompt=eng._candidate_text(c["proposal"]), winner=(c["original_index"] == best),
                      contextual_priming=eng.contextual_mode)
        return cands[best]["proposal"] if cands else winner["proposal"]
