"""Focused tests for the graph engine's contextual-priming mode and the Phase 2 /
Phase 0c proposer preset. Offline (mocked connectors), no live model."""
from __future__ import annotations

import json

from myrtia.connectors.base import Response, Status
from myrtia.plugins.graph import GraphAttack


def test_contextual_priming_with_borda_sends_structured_template() -> None:
    """Contextual mode + Borda must still deliver the winning structured template
    (a role-labelled message list) to the target, not a flattened string."""
    template = {"template": [
        {"role": "user", "content": "Earlier fictional question"},
        {"role": "assistant", "content": "Earlier fictional answer"},
        {"role": "user", "content": "Final fictional question"},
    ]}

    class Aux:
        def generate(self, messages, **_kwargs):
            # The critic system prompt carries this stable marker; the proposer
            # prompt does not (even though it may contain the substring "critic").
            is_critic = "reviewing attack proposals" in messages[0]["content"].lower()
            text = '{"ranking": [1, 0]}' if is_critic else json.dumps(template)
            return Response(Status.SUCCESS, response=text)

    class Target:
        def __init__(self) -> None:
            self.calls: list = []

        def generate(self, messages, **_kwargs):
            self.calls.append(messages)
            return Response(Status.SUCCESS, response="safe response")

    target = Target()
    graph = GraphAttack({"contextual_mode": True, "max_turns": 1,
                         "agents": [{"role": "attacker", "model": "a1"},
                                    {"role": "attacker", "model": "a2"}],
                         "evaluator": {"model": "off"}}, target)
    for node in graph.agents:
        graph._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = Aux()
    graph.load_goals(["Test scenario"])
    graph.attack()

    assert target.calls == [template["template"]]


def test_contextual_prompt_preset_selects_phase() -> None:
    """The contextual_prompt config picks the proposer preset: phase2 (default, with
    the worked examples) vs phase0c (lean, no examples); 'custom' falls back to phase2."""
    def proposer(cfg: dict) -> str:
        return GraphAttack(dict(cfg, contextual_mode=True,
                                agents=[{"role": "attacker", "model": "a1"}]),
                           target_connector=None)._contextual_proposer

    default = proposer({})
    phase0c = proposer({"contextual_prompt": "phase0c"})
    custom = proposer({"contextual_prompt": "custom"})

    assert "--- Example:" in default            # phase2 is the default
    assert default.count("--- Example:") == 5
    assert "--- Example:" not in phase0c         # lean variant, no examples
    assert "Contextual Priming" in phase0c
    assert custom == default                     # custom falls back to phase2
