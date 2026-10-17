"""Debate topology: attackers exchange messages across rounds, then a synthesiser distils."""

from __future__ import annotations

from typing import TYPE_CHECKING

from myrtia.plugins.graph_common import (
    _CHAIRMAN_SYSTEM,
    _CONTEXTUAL_CHAIRMAN_SYSTEM,
    _DEBATE_SYSTEM,
    _strip_fences,
)
from myrtia.plugins.graph_topologies.base import Topology, register

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack


@register("debate")
class DebateTopology(Topology):
    """Attackers debate over `rounds` passes on a shared transcript; one synthesiser strikes."""

    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        transcript: list[tuple[str, str]] = []
        eng._turn_proposals = []
        for r in range(eng.rounds):
            for a in eng.attackers:
                if eng._is_cancelled():
                    break
                convo = "\n".join(f"{m}: {t}" for m, t in transcript) or "(you open the debate)"
                raw = eng._agent_generate(
                    a, _DEBATE_SYSTEM,
                    f"OBJECTIVE: {goal}{eng._turn_feedback}\n\nDebate so far:\n{convo}\n\nYour contribution:")
                msg = _strip_fences(raw)[:600] or "(no contribution)"
                transcript.append((a["model"], msg))
                eng._emit("agent.message", turn=turn, goal_index=gi, round=r,
                          model=a["model"], sender=a["id"], message=msg)
        synth = eng.chairmen[0] if eng.chairmen else eng.attackers[0]
        convo = "\n".join(f"{m}: {t}" for m, t in transcript)
        raw = eng._agent_generate(
            synth, _CONTEXTUAL_CHAIRMAN_SYSTEM if eng.contextual_mode else _CHAIRMAN_SYSTEM,
            f"OBJECTIVE: {goal}{eng._turn_feedback}\n\nDebate transcript:\n{convo}\n\nSynthesise ONE final {'dialogue template' if eng.contextual_mode else 'prompt'} as JSON.",
            template_required=eng.contextual_mode)
        strike = eng._candidate(raw, goal if not eng.contextual_mode else "")
        if not strike:
            raise ValueError("Synthesiser did not produce a valid contextual-priming dialogue")
        eng._emit("chairman.synthesized", turn=turn, goal_index=gi,
                  model=synth["model"], synthesized_prompt=eng._candidate_text(strike),
                  contextual_priming=eng.contextual_mode)
        eng._turn_winner = (0, synth["model"])
        return strike
