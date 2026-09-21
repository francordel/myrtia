"""DirectRequests plugin adapter (ARES core baseline attack).

Sends each goal straight to the target — the standard red-teaming baseline. We add
the Myrtia seams (`set_event_emitter`/`load_goals`) and a live `attack()` that emits
`goal.started`/`target.responded` per goal, since ARES's base attack() is silent.
No judge (direct elicitation), so no `judge.scored` events.
"""

from __future__ import annotations

from typing import Any

from ares.strategies.direct_requests import DirectRequests
from ares.utils import Status

from myrtia.plugins.base import PluginSpec, register


class DirectRequestsLive(DirectRequests):
    def __init__(self, config: dict[str, Any], target_connector: Any) -> None:
        super().__init__(config, target_connector)
        self._on_event: Any = None

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
        return self.attack_results or []


def _factory(config: dict[str, Any], target_connector: Any):
    cfg = dict(config)
    cfg.setdefault("type", "ares.strategies.direct_requests.DirectRequests")
    return DirectRequestsLive(cfg, target_connector)


register(
    PluginSpec(
        plugin_id="direct",
        factory=_factory,
        description="DirectRequests: send each behaviour straight to the target "
        "(ARES core baseline, no judge).",
    )
)
