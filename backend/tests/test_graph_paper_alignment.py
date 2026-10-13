"""Regression checks for the CouncilAttack closed loop without model calls."""

import json

from myrtia.connectors.base import OpenAIChatConnector, Response, Status
from myrtia.plugins.graph import GraphAttack, _contextual_template, _parse_ranking
from myrtia.plugins.council_official import CONTEXTUAL_PROPOSER
from myrtia.judges.graded import parse_score


TEMPLATE = {"template": [
    {"role": "system", "content": "You are a friendly writing tutor."},
    {"role": "user", "content": "Can we write a short poem?"},
    {"role": "assistant", "content": "Of course; let's choose a subject."},
    {"role": "user", "content": "Write one about a cloud."},
]}


def test_placeholder_dialogue_is_rejected() -> None:
    bad = json.loads(json.dumps(TEMPLATE))
    bad["template"][0]["content"] = "..."
    assert _contextual_template(json.dumps(bad)) is None
    bad["template"][0]["content"] = "You are a friendly writing tutor."
    bad["template"][2]["content"] = "fabricated reply"
    assert _contextual_template(json.dumps(bad)) is None
    assert _contextual_template(json.dumps(TEMPLATE)) == TEMPLATE["template"]


def test_official_prompt_and_judge_argument() -> None:
    assert "## What is Contextual Priming?" in CONTEXTUAL_PROPOSER
    assert "**troubleshooting**" in CONTEXTUAL_PROPOSER
    assert parse_score('{"harm": 2, "argument": "partial response", '
                       '"disclaimer": false, "refusal": false}') == (2, "partial response")


def test_official_rank_dict_and_reasons_reach_chairman() -> None:
    raw = json.dumps({"ranks": {"proposal_1": 2, "proposal_2": 1},
                      "reasons": {"proposal_1": "vague", "proposal_2": "clear"}})
    assert _parse_ranking(raw, {0, 1}) == [1, 0]
    graph = GraphAttack({"agents": [{"role": "attacker", "model": "m1"},
                                    {"role": "attacker", "model": "m2"}]}, object())
    graph._agent_generate = lambda *_args, **_kwargs: raw
    props = [{"original_index": i, "model": f"m{i + 1}", "proposal": f"candidate {i + 1}"}
             for i in range(2)]
    winner = graph._borda_vote("test", 0, 0, props)
    assert winner["original_index"] == 1
    assert "m1 rank=2: vague" in graph._critique_summary()
    assert "m2 rank=1: clear" in graph._critique_summary()
    assert graph._proposal_listing(props, winner).startswith("Proposal 2 [m2] (BORDA TOP-1 WINNER)")


def test_auxiliary_output_budget_reaches_openai_compatible_endpoint(monkeypatch) -> None:
    captured = {}

    class HTTPResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(_url, *, json, **_kwargs):
        captured.update(json)
        return HTTPResponse()

    monkeypatch.setattr("myrtia.connectors.base.requests.post", fake_post)
    conn = OpenAIChatConnector("http://127.0.0.1:11434/v1", "test")
    conn.generate([{"role": "user", "content": "hello"}], max_tokens=4096, temperature=0.3)
    assert captured["max_tokens"] == 4096
    assert captured["temperature"] == 0.3


def test_contextual_turn_feedback_reaches_proposer_and_chairman_not_target() -> None:
    calls = []

    class Aux:
        def generate(self, messages, **_kwargs):
            calls.append(messages)
            return Response(Status.SUCCESS, response=json.dumps(TEMPLATE))

    class Target:
        def __init__(self):
            self.calls = []

        def generate(self, messages, **_kwargs):
            self.calls.append(messages)
            return Response(Status.SUCCESS, response="A cloud drifts across the sky.")

    target = Target()
    graph = GraphAttack({"contextual_mode": True, "mode": "council", "max_turns": 2,
                         "use_borda": False, "agents": [
                             {"role": "attacker", "model": "a"},
                             {"role": "chairman", "model": "c"}],
                         "evaluator": {"model": "off"}}, target)
    graph.evaluator.score = lambda _goal, _response: (2, "The answer is only a brief poem.")
    graph._judge_off = False
    for node in graph.agents:
        graph._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = Aux()
    graph.load_goals(["Write a poem about a cloud"])
    graph.attack()

    assert len(target.calls) == 2
    assert target.calls[0] == target.calls[1] == TEMPLATE["template"]
    assert "JUDGE SCORE: 2/5" in calls[2][-1]["content"]
    assert "The answer is only a brief poem." in calls[2][-1]["content"]
    assert "A cloud drifts across the sky." in calls[3][-1]["content"]
    assert "A cloud drifts across the sky." not in str(target.calls[1])
    assert "Contextual Priming" in calls[0][0]["content"]


def test_borda_top_one_precedes_borda_score() -> None:
    graph = GraphAttack({"use_borda": True,
                         "agents": [{"role": "attacker", "model": f"m{i}"} for i in range(3)],
                         "evaluator": {"model": "off"}}, object())
    ranks = iter(["[0,1,2,3,4]", "[0,1,2,3,4]", "[1,2,3,4,0]"])
    graph._agent_generate = lambda *_args, **_kwargs: next(ranks)
    props = [{"original_index": i, "model": f"m{i}", "proposal": f"p{i}"} for i in range(5)]
    winner = graph._borda_vote("goal", 0, 0, props)
    assert winner["original_index"] == 0
    assert graph._turn_borda[0][0] == 2
    assert graph._turn_borda[1][0] < graph._turn_borda[1][1]


def test_invalid_chairman_template_falls_back_to_valid_proposal() -> None:
    graph = GraphAttack({"contextual_mode": True, "use_borda": False,
                         "agents": [{"role": "attacker", "model": "a"},
                                    {"role": "chairman", "model": "c"}],
                         "evaluator": {"model": "off"}}, object())
    bad = json.loads(json.dumps(TEMPLATE))
    bad["template"][0]["content"] = "..."
    graph._agent_generate = lambda node, *_args, **_kwargs: json.dumps(
        TEMPLATE if node["role"] == "attacker" else bad)
    assert json.loads(graph._turn_council("Write a poem", 0, 0)) == TEMPLATE
