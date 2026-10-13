"""DirectRequests — the red-teaming baseline: send each goal straight to the target.

Self-contained (no ARES): the standard baseline. Adds the Myrtia seams
(`set_event_emitter`/`load_goals`) and a live `attack()` that emits
`goal.started`/`target.responded` per goal, then grades it with the default evaluator.
"""

from __future__ import annotations

from typing import Any

from myrtia.connectors.base import Status
from myrtia.judges.graded import JUDGE_SCHEMA, judge_and_emit, judge_from_config
from myrtia.plugins.base import PluginSpec, register


class DirectRequestsLive:
    def __init__(self, config: dict[str, Any], target_connector: Any) -> None:
        self.config = dict(config)
        self.target_connector = target_connector
        self.attack_goals: list[dict] | None = None
        self.attack_results: list[dict] | None = None
        self._on_event: Any = None
        self._judge = judge_from_config(config)

    def generate(self, **kwargs: Any) -> list[dict]:
        return self.attack_results or []

    def set_event_emitter(self, emit: Any) -> None:
        self._on_event = emit

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event_type, payload)
        except Exception:  # noqa: BLE001 — streaming must not break the attack
            pass

    def load_goals(self, goals: list[str]) -> None:
        # Build prompts inline (do NOT call generate(): ARES's base generate() loads
        # from a config["input_path"] file, which Myrtia does not use).
        rows = [{"goal": g, "label": 1} for g in goals]
        for r in rows:
            ctx = r.get("context", "")
            r["prompt"] = f"{ctx}\n\n{r['goal']}" if ctx else r["goal"]
        self.attack_goals = rows
        self.attack_results = rows

    def attack(self, **kwargs: Any) -> list[dict]:
        for a in self.attack_results or []:
            self._emit("goal.started", goal=a.get("goal"), has_context=bool(a.get("context")))
            resp = self.target_connector.generate(a["prompt"], **kwargs)
            a["response"] = resp
            text = resp.response if resp.status == Status.SUCCESS else f"[ERROR] {resp.error_message}"
            self._emit("target.responded", target_prompt=a["prompt"], target_response=text)
            score = judge_and_emit(self._judge, self._emit, a.get("goal", ""), text)
            if score is not None:
                a["score"] = score
            self._emit("goal.finished", goal=a.get("goal"), score=a.get("score"))
        return self.attack_results or []


def _factory(config: dict[str, Any], target_connector: Any):
    return DirectRequestsLive(dict(config), target_connector)


register(
    PluginSpec(
        plugin_id="direct",
        factory=_factory,
        config_schema=JUDGE_SCHEMA,
        description="DirectRequests: send each behaviour straight to the target "
        "(the baseline; graded 0-5 by the default evaluator).",
        how=[
            "Send — each behaviour is sent to the target model verbatim.",
            "Observe — the target's raw response is recorded and graded 0-5 by the default evaluator.",
            "Use as a baseline to compare against the council attacks.",
        ],
    )
)
