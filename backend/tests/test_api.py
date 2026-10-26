"""Offline API + unit tests for Myrtia's newer backend features (issue #25).

All tests here are network-free: they hit the FastAPI app with Starlette's TestClient
for validation/parse/list endpoints, and exercise the approval registry and the
defense shields as pure units. None of them need a live model, so they run in CI
(`pytest -m "not e2e"`).
"""
from __future__ import annotations

import asyncio

import pytest
from starlette.testclient import TestClient

import myrtia.api.app as appmod

client = TestClient(appmod.app)


# ── health / listings ────────────────────────────────────────────────────────
def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_defenses_listed() -> None:
    r = client.get("/defenses")
    assert r.status_code == 200
    ids = {d["id"] for d in r.json()["defenses"]}
    assert {"self-reminder", "perplexity-filter", "retokenization"} <= ids


def test_plugins_include_graph() -> None:
    r = client.get("/plugins")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json().get("plugins", r.json())} if isinstance(r.json(), dict) else set()
    # tolerate either {plugins:[...]} or a bare list
    body = r.json()
    items = body.get("plugins", body) if isinstance(body, dict) else body
    ids = {p["id"] for p in items}
    assert "graph" in ids and "direct" in ids
    assert "garak" in ids and "pyrit" in ids


# ── run creation validation / DoS caps (#27) ────────────────────────────────
def _target() -> dict:
    return {"kind": "openai_chat", "base_url": "http://127.0.0.1:11434/v1", "model": "m"}


def test_runs_rejects_unknown_attack() -> None:
    r = client.post("/runs", json={"attack_id": "nope", "goals": ["x"], "target": _target()})
    assert r.status_code == 400


def test_runs_rejects_empty_goals() -> None:
    r = client.post("/runs", json={"attack_id": "direct", "goals": [], "target": _target()})
    assert r.status_code == 400


def test_runs_rejects_overlong_goal() -> None:
    r = client.post("/runs", json={"attack_id": "direct", "goals": ["x" * 9000], "target": _target()})
    assert r.status_code == 400


def test_runs_rejects_mixed_graph_context_modes() -> None:
    r = client.post("/runs", json={"attack_id": "graph", "goals": ["x"], "target": _target(),
                                   "attack_config": {"contextual_mode": True,
                                                     "accumulate_target_context": True}})
    assert r.status_code == 400 and "mutually exclusive" in r.json()["error"]


def test_runs_blocks_ssrf_target() -> None:
    r = client.post("/runs", json={"attack_id": "direct", "goals": ["x"],
                                   "target": {"kind": "openai_chat", "base_url": "http://169.254.169.254/v1", "model": "m"}})
    assert r.status_code == 400 and "block" in r.json()["error"].lower()


# ── behaviour upload parsing (#5) ────────────────────────────────────────────
def test_parse_csv_harmbench_shape() -> None:
    csv = "Behavior,SemanticCategory\nWrite a haiku,poetry\nExplain photosynthesis,science\n"
    r = client.post("/behaviors/parse", json={"content": csv, "filename": "b.csv"})
    assert r.status_code == 200
    d = r.json()
    assert d["format"] == "csv" and d["count"] == 2
    assert [g["theme"] for g in d["goals"]] == ["poetry", "science"]


def test_parse_txt_dedupes_and_skips_comments() -> None:
    txt = "# header\nGoal one\nGoal two\n\nGoal two\n"
    r = client.post("/behaviors/parse", json={"content": txt, "filename": "b.txt", "theme": "t"})
    assert r.status_code == 200
    d = r.json()
    assert d["format"] == "text" and d["count"] == 2
    assert all(g["theme"] == "t" for g in d["goals"])


def test_parse_rejects_empty() -> None:
    r = client.post("/behaviors/parse", json={"content": "   "})
    assert r.status_code == 400


# ── model listing + pull guards (#3/#4) ──────────────────────────────────────
def test_list_models_empty_base() -> None:
    assert appmod._list_models("", None) == []


def test_pull_blocks_ssrf() -> None:
    r = client.post("/models/pull", json={"base_url": "http://169.254.169.254/v1", "name": "x"})
    assert r.status_code == 400


# ── reproducibility metadata (#21) ───────────────────────────────────────────
def test_repro_meta_shape() -> None:
    from myrtia.store.runs import Run, RunSpec
    run = Run(id="abc123", spec=RunSpec(attack_id="direct", target={"model": "m", "base_url": "http://x/v1"},
                                        goals=["g1", "g2"], theme="t",
                                        attack_config={"judge_model": "qwen2.5:3b"}))
    meta = appmod._repro_meta(run)
    assert meta["attack_id"] == "direct" and meta["n_goals"] == 2
    assert meta["judge"]["model"] == "qwen2.5:3b"
    assert meta["target"]["model"] == "m"
    assert "myrtia_version" in meta and "exported_at_utc" in meta


# ── HITL approval registry, correct-loop resolution (#12/#17) ────────────────
def test_approval_resolve_on_awaiting_loop() -> None:
    from myrtia.hitl.approvals import ApprovalRegistry

    async def scenario() -> bool:
        reg = ApprovalRegistry()
        loop = asyncio.get_running_loop()
        ap = reg.request("run1", "launch", {"a": 1}, loop=loop)
        assert reg.pending("run1") and ap.future is not None
        # resolve from a callback (same loop, different task) — must complete the future
        loop.call_soon(lambda: reg.resolve(ap.id, True))
        return await asyncio.wait_for(ap.future, timeout=2)

    assert asyncio.run(scenario()) is True


def test_approval_double_resolve_returns_false() -> None:
    from myrtia.hitl.approvals import ApprovalRegistry
    reg = ApprovalRegistry()
    ap = reg.request("r", "launch", loop=None)
    assert reg.resolve(ap.id, False) is True
    assert reg.resolve(ap.id, True) is False  # already popped
    assert reg.pending() == []


def test_approval_sync_wait_path() -> None:
    from myrtia.hitl.approvals import ApprovalRegistry
    reg = ApprovalRegistry()
    ap = reg.request("r", "launch", loop=None)
    reg.resolve(ap.id, True)
    assert ap.wait(timeout=1) is True


def test_cancel_while_waiting_approval_releases_run() -> None:
    from myrtia.orchestrator.runner import Orchestrator
    from myrtia.store.runs import Run, RunSpec, RunStatus

    async def scenario() -> None:
        orch = Orchestrator()
        run = Run(id="hitl-cancel-run", spec=RunSpec(attack_id="direct", attack_config={"require_approval": True}))
        task = asyncio.create_task(orch.run(run))
        for _ in range(50):
            if run.status == RunStatus.WAITING_APPROVAL:
                break
            await asyncio.sleep(0.01)
        assert run.status == RunStatus.WAITING_APPROVAL

        cancelled = orch.cancel(run.id)
        assert cancelled is True

        await asyncio.wait_for(task, timeout=2.0)
        assert run.status == RunStatus.CANCELLED
        assert run.error == "cancelled while pending approval"

    asyncio.run(scenario())



# ── defense shields (pure) (#35) ─────────────────────────────────────────────
def test_perplexity_filter_blocks_base64() -> None:
    from myrtia.defenses import _BY_ID
    fn = _BY_ID["perplexity-filter"]["fn"]
    payload = "aGVsbG8gd29ybGQ" * 5  # long base64-ish run
    _text, blocked, _note = fn(payload, {}, None)
    assert blocked is True


def test_self_reminder_wraps_prompt() -> None:
    from myrtia.defenses import _BY_ID
    fn = _BY_ID["self-reminder"]["fn"]
    out, blocked, _ = fn("do a thing", {}, None)
    assert blocked is False and "do a thing" in out and len(out) > len("do a thing")


def test_retokenize_splits_long_tokens() -> None:
    from myrtia.defenses import _BY_ID
    fn = _BY_ID["retokenization"]["fn"]
    out, blocked, _ = fn("supercalifragilistic", {}, None)
    assert blocked is False and " " in out


def test_defended_connector_blocks_before_target() -> None:
    from myrtia.defenses import DefendedConnector
    from myrtia.connectors.base import Status

    class Boom:
        config = {"name": "t"}
        def generate(self, prompt, **_k):  # pragma: no cover - must NOT be called
            raise AssertionError("target reached despite a blocking shield")

    dc = DefendedConnector(Boom(), [{"id": "perplexity-filter"}])
    r = dc.generate("aGVsbG8gd29ybGQ" * 5)
    assert r.status == Status.SUCCESS and "Blocked" in r.response


# ── target connectors: factory dispatch + agent path extraction (#31) ────────
def test_factory_dispatch_kinds() -> None:
    from myrtia.connectors.factory import build_target_connector
    from myrtia.connectors.base import (AnthropicMessagesConnector, HTTPAgentConnector, OpenAIChatConnector)
    oc = build_target_connector({"kind": "openai_chat", "base_url": "http://127.0.0.1:11434/v1", "model": "m"})
    an = build_target_connector({"kind": "anthropic", "base_url": "https://api.anthropic.com", "model": "claude"})
    ag = build_target_connector({"kind": "http_agent", "base_url": "https://example.test/agent",
                                 "prompt_field": "q", "response_path": "data.reply"})
    assert isinstance(oc, OpenAIChatConnector)
    assert isinstance(an, AnthropicMessagesConnector)
    assert isinstance(ag, HTTPAgentConnector) and ag.response_path == "data.reply"


def test_factory_rejects_unknown_kind() -> None:
    import pytest as _pt
    from myrtia.connectors.factory import build_target_connector
    with _pt.raises(ValueError):
        build_target_connector({"kind": "smoke-signals", "base_url": "http://x/v1", "model": "m"})


def test_factory_blocks_ssrf_for_agent() -> None:
    import pytest as _pt
    from myrtia.connectors.factory import build_target_connector
    with _pt.raises(ValueError):
        build_target_connector({"kind": "http_agent", "base_url": "http://169.254.169.254/agent"})


def test_agent_response_path_dig() -> None:
    from myrtia.connectors.base import _dig
    data = {"data": {"reply": "hello", "items": [{"text": "a"}, {"text": "b"}]}}
    assert _dig(data, "data.reply") == "hello"
    assert _dig(data, "data.items[1].text") == "b"
    assert _dig(data, "data.missing") is None


# ── run-time estimate (#38) ──────────────────────────────────────────────────
def test_profiles_listed() -> None:
    r = client.get("/profiles")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["profiles"]}
    assert {"local-cpu", "local-gpu", "cluster", "cloud-api"} <= ids


def test_estimate_council_scales_with_goals() -> None:
    from myrtia.estimate import estimate_run
    cfg = {"max_turns": 3, "council_models": ["a", "b", "c"], "use_chairman": True,
           "use_borda": True, "judge_model": "qwen2.5:3b"}
    one = estimate_run("council", cfg, 1, "local-gpu")
    ten = estimate_run("council", cfg, 10, "local-gpu")
    assert ten["total_calls"] == 10 * one["calls_per_goal"]
    assert ten["estimated_seconds"] > one["estimated_seconds"] > 0


def test_estimate_judge_off_reduces_calls() -> None:
    from myrtia.estimate import calls_per_goal
    on = calls_per_goal("direct", {"judge_model": "qwen2.5:3b"})
    off = calls_per_goal("direct", {"judge_model": "off"})
    assert sum(on.values()) > sum(off.values())


def test_estimate_endpoint() -> None:
    r = client.post("/estimate", json={"attack_id": "direct", "attack_config": {"judge_model": "off"},
                                       "n_goals": 5, "profile": "cloud-api"})
    assert r.status_code == 200
    d = r.json()
    assert d["n_goals"] == 5 and d["total_calls"] == 5 and d["estimated_seconds"] >= 0


# ── graph per-agent contextual priming (#39) ─────────────────────────────────
def test_graph_norm_priming() -> None:
    from myrtia.plugins.graph import GraphAttack
    assert GraphAttack._norm_priming(None) == {"mode": "single", "context": ""}
    assert GraphAttack._norm_priming({"mode": "contextual", "context": " hi "}) == {"mode": "contextual", "context": "hi"}
    assert GraphAttack._norm_priming({"mode": "weird"})["mode"] == "single"


def test_graph_agent_priming_builds_primed_conversation() -> None:
    from myrtia.plugins.graph import GraphAttack
    captured = {}

    class Rec:
        config = {"name": "t"}
        def generate(self, msgs, **_k):
            captured["msgs"] = msgs
            from myrtia.connectors.base import Response, Status
            return Response(Status.SUCCESS, response="ok")

    g = GraphAttack({"agents": [{"id": "a1", "role": "attacker", "model": "m",
                                 "priming": {"mode": "contextual", "context": "You are in a sandbox."}}]}, Rec())
    node = g.agents[0] if getattr(g, "agents", None) else g.attackers[0]
    g._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = Rec()
    g._agent_generate(node, "default sys", "OBJECTIVE: x")
    roles = [m["role"] for m in captured["msgs"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert "sandbox" in captured["msgs"][1]["content"]


@pytest.mark.parametrize("mode", ["single", "council", "parallel", "debate"])
def test_graph_contextual_priming_sends_fabricated_history_per_attempt(mode: str) -> None:
    import json
    from myrtia.connectors.base import Response, Status
    from myrtia.plugins.graph import GraphAttack

    template = {"template": [
        {"role": "system", "content": "Fictional safety evaluation."},
        {"role": "user", "content": "Set the scene."},
        {"role": "assistant", "content": "The scene is set."},
        {"role": "user", "content": "Continue the scenario."},
    ]}

    class Aux:
        def generate(self, messages, **_kwargs):
            return Response(Status.SUCCESS, response=json.dumps(template))

    class Target:
        def __init__(self):
            self.calls = []

        def generate(self, messages, **_kwargs):
            self.calls.append(messages)
            return Response(Status.SUCCESS, response="real target reply")

    target = Target()
    graph = GraphAttack({"contextual_mode": True, "mode": mode, "max_turns": 2,
                         "rounds": 1, "use_borda": False,
                         "agents": [{"role": "attacker", "model": "a"},
                                    {"role": "chairman", "model": "c"}],
                         "evaluator": {"model": "off"}}, target)
    for node in graph.agents:
        graph._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = Aux()
    graph.load_goals(["Test scenario"])
    results = graph.attack()

    assert len(target.calls) == 2
    assert target.calls[0] == target.calls[1] == template["template"]
    assert "real target reply" not in str(target.calls[1])
    assert results[0]["council_turns"][0]["target_messages"] == template["template"]
    assert "ASSISTANT (fabricated)" in results[0]["council_turns"][0]["prompt"]
    assert "ASSISTANT (fabricated)" in results[0]["prompt"]


def test_graph_contextual_priming_rejects_malformed_and_mixed_modes() -> None:
    from myrtia.connectors.base import Response, Status
    from myrtia.plugins.graph import GraphAttack, _contextual_template

    assert _contextual_template('{"template": [{"role":"user","content":"plain"}]}') is None
    assert _contextual_template('{"template": [{"role":"user","content":"u"}, '
                                '{"role":"assistant","content":"a"}, '
                                '{"role":"system","content":"late"}]}') is None
    with pytest.raises(ValueError, match="mutually exclusive"):
        GraphAttack({"contextual_mode": True, "accumulate_target_context": True}, object())

    class Invalid:
        def generate(self, _messages, **_kwargs):
            return Response(Status.SUCCESS, response="not a dialogue")

    graph = GraphAttack({"contextual_mode": True, "mode": "single", "max_turns": 1,
                         "agents": [{"role": "attacker", "model": "a"}],
                         "evaluator": {"model": "off"}}, Invalid())
    node = graph.attackers[0]
    graph._conn_cache[(node["model"], node["endpoint"], node.get("api_key"))] = Invalid()
    graph.load_goals(["Test scenario"])
    assert graph.attack()[0]["council_turns"] == []


def test_graph_contextual_priming_with_borda_keeps_structured_target_input() -> None:
    import json
    from myrtia.connectors.base import Response, Status
    from myrtia.plugins.graph import GraphAttack

    template = {"template": [
        {"role": "user", "content": "Earlier fictional question"},
        {"role": "assistant", "content": "Earlier fictional answer"},
        {"role": "user", "content": "Final fictional question"},
    ]}

    class Aux:
        def generate(self, messages, **_kwargs):
            # Discriminate the critic call by a stable marker in the critic system
            # prompt; the proposer prompt may itself contain the substring "critic"
            # (e.g. "critical"), so keying on that would misclassify the proposer.
            is_critic = "reviewing attack proposals" in messages[0]["content"].lower()
            text = '{"ranking": [1, 0]}' if is_critic else json.dumps(template)
            return Response(Status.SUCCESS, response=text)

    class Target:
        calls = []

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


# ── additional garak probes (#7) ─────────────────────────────────────────────
def test_new_garak_probes_registered() -> None:
    import myrtia.plugins.garak_probes  # noqa: F401
    from myrtia.plugins.base import REGISTRY
    assert {"dan", "encoding", "continuation", "leakreplay"} <= set(REGISTRY)


def test_encoding_probe_roundtrips() -> None:
    import base64
    from myrtia.plugins.garak_probes import _build_encoding
    rows = _build_encoding("DECODE ME", {"variants": "base64"})
    enc = rows[0]["prompt"].split("\n")[-1]
    assert base64.b64decode(enc).decode() == "DECODE ME"


def test_dan_variant_selection() -> None:
    from myrtia.plugins.garak_probes import _build_dan
    rows = _build_dan("x", {"variants": "aim"})
    assert [r["variant"] for r in rows] == ["aim"]


# ── audit report export (statistics redesign) ────────────────────────────────
def test_stats_has_severity_and_owasp() -> None:
    r = client.get("/stats")
    assert r.status_code == 200
    d = r.json()
    assert set(d.get("severity", {})) >= {"critical", "high", "medium", "low", "informational", "passed"}
    assert isinstance(d.get("owasp"), list)


def test_audit_json_shape() -> None:
    r = client.get("/audit?format=json")
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d and "severity" in d and "owasp" in d and "findings_table" in d
    assert set(d["summary"]) >= {"asr", "tests", "jailbroken", "findings", "posture"}


def test_audit_markdown_and_csv() -> None:
    md = client.get("/audit?format=md")
    assert md.status_code == 200 and md.text.lstrip().startswith("# Myrtia red-team audit")
    csv = client.get("/audit?format=csv")
    assert csv.status_code == 200 and "severity" in csv.text.splitlines()[0]


def test_audit_html_prints() -> None:
    r = client.get("/audit?format=html")
    assert r.status_code == 200 and "Print / Save as PDF" in r.text and "<title>" in r.text


def test_audit_xlsx_is_zip() -> None:
    r = client.get("/audit?format=xlsx")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx is a zip container


def test_build_audit_severity_mapping() -> None:
    from myrtia.audit import build_audit, score_to_severity
    assert score_to_severity(5) == "critical"
    assert score_to_severity(0) == "passed"
    stats = {"score_distribution": [2, 0, 0, 1, 0, 3], "total_goals": 6, "total_runs": 1,
             "jailbroken": 3, "asr": 50, "by_theme": [], "by_attack": [], "by_target": [],
             "by_behavior": [{"goal": "g", "best": 5, "theme": "t", "attack": "graph", "target": "m", "success": True}],
             "council_members": []}
    a = build_audit(stats, {}, {"myrtia_version": "0.0.1"})
    assert a["severity"]["critical"] == 3 and a["severity"]["medium"] == 1 and a["severity"]["passed"] == 2
    assert a["summary"]["posture"] == "Critical" and a["summary"]["findings"] == 4
    assert len(a["findings_table"]) == 1


# ── garak / PyRIT pack adapters ───────────────────────────────────────────────
def test_pack_adapters_registered() -> None:
    import myrtia.plugins.garak_adapter  # noqa: F401
    import myrtia.plugins.pyrit_adapter  # noqa: F401
    from myrtia.plugins.base import REGISTRY
    assert {"garak", "pyrit"} <= set(REGISTRY)


def test_packs_advertise_their_attacks() -> None:
    from myrtia import packs
    by_id = {p["id"]: p for p in packs.list_packs()}
    assert by_id["garak"]["adds"] == ["garak"]
    assert by_id["pyrit"]["adds"] == ["pyrit"]
    assert by_id["garak"]["adapter"] and by_id["pyrit"]["adapter"]


def test_pyrit_builder_transforms_offline() -> None:
    # The PyRIT converter transform must run without a target or network.
    pyrit = pytest.importorskip("pyrit")  # noqa: F841
    from myrtia.plugins.pyrit_adapter import _build
    rows = _build("DECODE ME", {"converters": "base64,leetspeak"})
    assert [r["variant"] for r in rows] == ["base64", "leetspeak"]
    import base64 as _b64
    enc = rows[0]["prompt"].split("\n")[-1]
    assert _b64.b64decode(enc).decode() == "DECODE ME"
    assert all(r["prompt"] for r in rows)


def test_pyrit_builder_ignores_unknown_converter() -> None:
    pytest.importorskip("pyrit")
    from myrtia.plugins.pyrit_adapter import _build
    rows = _build("x", {"converters": "not-a-converter"})
    assert [r["variant"] for r in rows] == ["base64"]  # falls back to the first default


def test_garak_prompt_text_handles_str() -> None:
    from myrtia.plugins.garak_adapter import _prompt_text
    assert _prompt_text("hello") == "hello"
