"""CouncilAttack plugin adapter.

Registers the vendored `ares-council` (Apache-2.0) attack under the id "council".
We do NOT copy its 2141 lines — the factory imports the real class lazily so this
module (and the registry) load even where `ares-council` is not installed; the
import only fires when a run is actually launched.

Live streaming: once the plugin gains the optional `on_event` seam, wrap the class
here so `set_event_emitter` maps the plugin's per-turn callbacks to Myrtia Events.
Until then the orchestrator emits run/goal-level events on its own.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any

from myrtia.plugins.base import PluginSpec, register


def _build(config: dict[str, Any], target_connector: Any, *, crescendo: bool):
    from ares_council import CouncilAttack

    def _prefix(m: str) -> str:
        # Council/chairman/judge route to Ollama unless an explicit provider prefix
        # (openai/, ollama/) is given.
        return m if "/" in m else f"ollama/{m}"

    cfg = dict(config)
    # Sensible defaults so a minimal attack_config just works.
    cfg.setdefault("type", "ares_council.CouncilAttack")
    council = [_prefix(m) for m in (cfg.get("council_models") or ["qwen2.5:1.5b"])]
    cfg["council_models"] = council
    first = council[0]
    cfg["chairman_model"] = _prefix(cfg.get("chairman_model", first))
    cfg["judge_model"] = _prefix(cfg.get("judge_model", first))
    cfg.setdefault("ollama_endpoint", "http://127.0.0.1:11434")
    cfg.setdefault("max_turns", 3)
    cfg.setdefault("use_borda", True)
    cfg.setdefault("use_chairman", True)
    # Crescendo = accumulate the target conversation across turns; isolated = each
    # turn is a fresh standalone prompt. Explicit config wins over the flavor default.
    cfg.setdefault("accumulate_target_context", crescendo)
    # Unique per-run checkpoint. CouncilAttack RESUMES from an existing
    # council_attacks.json (reusing completed goals and skipping the whole
    # deliberation), which would suppress all live events on any re-run with the
    # same goal. A fresh path per run guarantees every run actually attacks.
    if not cfg.get("output_path"):
        cfg["output_path"] = str(
            Path(tempfile.gettempdir()) / f"myrtia_council_{uuid.uuid4().hex}.json"
        )
    return CouncilAttack(cfg, target_connector)


_COUNCIL_SCHEMA = [
    {"key": "max_turns", "label": "Max turns", "type": "number", "default": 3,
     "help": "Attack turns per behaviour before giving up."},
    {"key": "use_borda", "label": "Borda cross-critique", "type": "bool", "default": True,
     "help": "Members rank each other's proposals; Borda picks the winner."},
    {"key": "use_chairman", "label": "Chairman synthesis", "type": "bool", "default": True,
     "help": "A chairman refines the winning proposal before sending."},
    {"key": "chairman_model", "label": "Chairman model", "type": "text", "default": "",
     "help": "Blank = first council model."},
    {"key": "judge_model", "label": "Judge model", "type": "text", "default": "",
     "help": "Blank = first council model."},
    {"key": "ollama_endpoint", "label": "Council/judge endpoint", "type": "text",
     "default": "http://127.0.0.1:11434",
     "help": "Ollama endpoint for council, chairman and judge models."},
    {"key": "council_max_tokens", "label": "Council max tokens", "type": "number",
     "default": 2048, "help": "Token cap per council/chairman/judge call."},
]

register(
    PluginSpec(
        plugin_id="council",
        factory=lambda c, t: _build(c, t, crescendo=False),
        description="CouncilAttack (isolated): N-proposer council, cross-critique, "
        "Borda Top-1, chairman synthesis, in-loop graded 0-5 judge. Each turn is a "
        "fresh standalone prompt (ares-council, Apache-2.0).",
        config_schema=_COUNCIL_SCHEMA,
    )
)

register(
    PluginSpec(
        plugin_id="council-crescendo",
        factory=lambda c, t: _build(c, t, crescendo=True),
        description="CouncilAttack (crescendo): same council pipeline, but the target "
        "conversation accumulates across turns — a gradual multi-turn escalation.",
        config_schema=_COUNCIL_SCHEMA,
    )
)
