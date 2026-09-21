"""Attack-plugin contract for Myrtia.

Myrtia's plugin contract is deliberately the **ARES** one: an attack is a class
subclassing `ares.strategies.attack_strategy.AttackStrategy`, constructed as
`Strategy(config, target_connector)`, exposing `attack()/generate()` and a
`template()` descriptor. This lets us host existing ARES plugins — CouncilAttack
first — without reimplementing them.

This module defines the thin Myrtia-side view of that contract plus the optional
`on_event` seam we want plugins to support for live streaming (see
docs/architecture.md, "The key MVP risk"). It does NOT vendor any plugin code:
CouncilAttack is depended on via the `ares-council` package (Apache-2.0) and wrapped
by an adapter in `plugins/council.py`.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

# A plugin surfaces a live event as (event_type, payload) primitives — it never
# imports Myrtia's Event type, so plugins stay decoupled/reusable. The orchestrator
# supplies the emitter and turns each call into a Myrtia Event on the bus.
EventEmitter = Callable[[str, dict], None]


@runtime_checkable
class AttackStrategyLike(Protocol):
    """Structural view of an ARES AttackStrategy, as Myrtia drives it."""

    def __init__(self, config: dict[str, Any], target_connector: Any) -> None: ...

    def attack(self, **kwargs: Any) -> list[dict]: ...

    def generate(self, **kwargs: Any) -> list[dict]: ...


@runtime_checkable
class EventEmittingStrategy(Protocol):
    """Plugins that support the live seam accept an emitter `(event_type, payload)`.

    The vendored CouncilAttack implements this (`set_event_emitter` + internal
    `_emit`), pushing proposal/critique/vote/chairman/target/judge events per turn.
    """

    def set_event_emitter(self, emit: EventEmitter) -> None: ...


class PluginSpec:
    """What the registry stores about an available attack.

    `config_schema` describes the plugin's advanced knobs so the UI can render an
    "Advanced configuration" panel. Each field is a dict:
        {"key", "label", "type": "text"|"number"|"bool", "default", "help"?}
    Field values (when set by the operator) are merged into the run's attack_config.
    """

    def __init__(self, plugin_id: str, factory: Callable[..., AttackStrategyLike],
                 description: str = "",
                 config_schema: list[dict] | None = None,
                 paper: str = "", how: list[str] | None = None) -> None:
        self.id = plugin_id
        self.factory = factory
        self.description = description
        self.config_schema = config_schema or []
        self.paper = paper            # URL to the paper/reference, if any
        self.how = how or []          # ordered "how it works" steps for the info panel


# Populated by plugin modules at import time (e.g. plugins/council.py).
REGISTRY: dict[str, PluginSpec] = {}


def register(spec: PluginSpec) -> None:
    REGISTRY[spec.id] = spec
