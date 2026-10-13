"""Offline tests for the new graph topologies: pipeline, mixture-of-agents, and the
free-form edge-DAG executor. Mocked connectors, no live model."""
from __future__ import annotations

from myrtia.connectors.base import Response, Status
from myrtia.plugins.graph import GraphAttack


def _aux(prompt_text):
    class Aux:
        def generate(self, messages, **_kwargs):
            return Response(Status.SUCCESS, response='{"prompt": "%s"}' % prompt_text)
    return Aux()


class Target:
    def __init__(self) -> None:
        self.calls: list = []

    def generate(self, prompt, **_kwargs):
        self.calls.append(prompt)
        return Response(Status.SUCCESS, response="safe response")


def _seed(graph, by_model):
    for node in graph.agents:
        graph._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = \
            _aux(by_model.get(node["model"], "X"))


def test_pipeline_relays_and_strikes_once() -> None:
    t = Target()
    g = GraphAttack({"mode": "pipeline", "max_turns": 1,
                     "agents": [{"role": "attacker", "model": "atk"},
                                {"role": "attacker", "model": "atk"}],
                     "evaluator": {"model": "off"}}, t)
    _seed(g, {"atk": "P"})
    g.load_goals(["goal"])
    res = g.attack()
    assert t.calls == ["P"]                       # one strike with the relayed prompt
    assert res and res[0].get("prompt")           # the run produced a result


def test_moa_layers_aggregate_and_strike() -> None:
    t = Target()
    g = GraphAttack({"mode": "moa", "max_turns": 1, "rounds": 2,
                     "agents": [{"role": "attacker", "model": "atk"},
                                {"role": "attacker", "model": "atk"},
                                {"role": "chairman", "model": "chair"}],
                     "evaluator": {"model": "off"}}, t)
    _seed(g, {"atk": "ATK", "chair": "SYNTH"})
    g.load_goals(["goal"])
    g.attack()
    assert t.calls == ["SYNTH"]                   # the aggregator's synthesis strikes


def test_custom_edge_dag_executes_in_order_and_strikes_synthesis() -> None:
    t = Target()
    g = GraphAttack({"mode": "custom", "max_turns": 1,
                     "agents": [{"id": "a1", "role": "attacker", "model": "atk"},
                                {"id": "a2", "role": "attacker", "model": "atk"},
                                {"id": "c1", "role": "chairman", "model": "chair"}],
                     "edges": [{"from": "a1", "to": "c1"},
                               {"from": "a2", "to": "c1"},
                               {"from": "c1", "to": "target"}],
                     "evaluator": {"model": "off"}}, t)
    _seed(g, {"atk": "ATK", "chair": "SYNTH"})
    g.load_goals(["goal"])
    g.attack()
    assert t.calls == ["SYNTH"]                   # c1 (wired to target) produces the strike


def test_custom_without_edges_falls_back_to_council() -> None:
    t = Target()
    g = GraphAttack({"mode": "custom", "max_turns": 1, "use_borda": False, "use_chairman": False,
                     "agents": [{"role": "attacker", "model": "atk"}],
                     "evaluator": {"model": "off"}}, t)
    _seed(g, {"atk": "P"})
    g.load_goals(["goal"])
    g.attack()
    assert t.calls == ["P"]                       # no edges -> council fallback still strikes
