"""Shared base for single-shot template attacks (garak-style probes).

Many garak probes are the same shape: transform each goal into one or more
standalone prompts, send each to the target, record the response and grade it 0-5 with the default evaluator.
This module factors that loop out so each probe plugin only declares how it builds
its prompt variants. Plugins that need an auxiliary LLM or multi-turn state (TAP,
Crescendo, Council) do NOT use this and implement the seams themselves.

A builder is `build(goal: str, config: dict) -> list[dict]`, each dict carrying at
least `prompt`; `variant` (the probe sub-technique) is surfaced in events.
"""

from __future__ import annotations

from typing import Any, Callable

from myrtia.judges.graded import JUDGE_SCHEMA, judge_and_emit, judge_from_config
from myrtia.plugins.base import PluginSpec, register

Builder = Callable[[str, dict], list[dict]]


class TemplateAttack:
    """Self-contained single-shot template attack exposing the Myrtia seams."""

    def __init__(self, config: dict[str, Any], target_connector: Any,
                 build: Builder) -> None:
        self.config = dict(config)
        self.target_connector = target_connector
        self._build = build
        self._on_event: Any = None
        self._judge = judge_from_config(self.config)
        self.attack_goals: list[dict] | None = None
        self.attack_results: list[dict] | None = None

    def set_event_emitter(self, emit: Any) -> None:
        self._on_event = emit

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self._on_event is None:
            return
        try:
            self._on_event(event_type, payload)
        except Exception:  # noqa: BLE001 — streaming must never break the attack
            pass

    def load_goals(self, goals: list[str]) -> None:
        rows: list[dict] = []
        custom = self.config.get("custom_templates")
        for g in goals:
            if isinstance(custom, dict) and custom:
                # Researcher-edited templates win over the built-in variants.
                built = [{"variant": str(k), "prompt": str(v).replace("{goal}", g)}
                         for k, v in custom.items() if str(v).strip()]
            else:
                built = self._build(g, self.config)
            for row in built:
                row.setdefault("goal", g)
                row.setdefault("label", 1)
                rows.append(row)
        self.attack_goals = rows
        self.attack_results = rows

    def attack(self, **kwargs: Any) -> list[dict]:
        from myrtia.connectors.base import Status  # lazy: keeps module import dep-free

        for a in self.attack_results or []:
            self._emit("goal.started", goal=a.get("goal"), variant=a.get("variant"))
            resp = self.target_connector.generate(a["prompt"], **kwargs)
            a["response"] = resp
            text = resp.response if resp.status == Status.SUCCESS else f"[ERROR] {resp.error_message}"
            self._emit(
                "target.responded",
                variant=a.get("variant"),
                target_prompt=a["prompt"],
                target_response=text,
            )
            score = judge_and_emit(self._judge, self._emit, a.get("goal", ""), text,
                                   variant=a.get("variant"))
            if score is not None:
                a["score"] = score
        return self.attack_results or []

    def generate(self, **kwargs: Any) -> list[dict]:
        return self.attack_results or []


def register_template_attack(*, plugin_id: str, build: Builder, description: str,
                             type_path: str, how: list[str],
                             paper: str = "",
                             config_schema: list[dict] | None = None,
                             templates: dict[str, str] | None = None) -> None:
    """Register a single-shot template attack with minimal boilerplate."""

    def _factory(config: dict[str, Any], target_connector: Any):
        cfg = dict(config)
        cfg.setdefault("type", type_path)
        return TemplateAttack(cfg, target_connector, build)

    register(PluginSpec(
        plugin_id=plugin_id,
        factory=_factory,
        description=description,
        config_schema=(config_schema or []) + JUDGE_SCHEMA,
        paper=paper,
        how=how,
        templates=templates,
    ))
