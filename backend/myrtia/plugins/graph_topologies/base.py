"""Topology strategy base class and registry.

Each attacker topology (council, chairman, parallel, debate, pipeline, moa, custom,
single) is a `Topology` subclass living in its own module and registering itself with
`@register(...)`. The engine (`GraphAttack`) looks one up by `mode` via `get_topology`
and delegates each turn to it — a Strategy pattern behind an open/closed registry, so
adding a topology is "add a module + register", never an edit to the engine's dispatch.

Topologies are stateless: every per-turn value (proposals, winner, Borda tallies) lives
on the engine instance passed to `run_turn`. The engine is typed via a TYPE_CHECKING
forward reference so strategies get full type information without importing the engine at
runtime (which would create an import cycle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myrtia.plugins.graph import GraphAttack

#: Mode used both as the engine's default and as the fallback for unknown modes.
DEFAULT_MODE = "council"

#: Registered topologies, keyed by every mode string that should resolve to them.
REGISTRY: dict[str, type["Topology"]] = {}


class Topology(ABC):
    """One attacker topology: produce the strike prompt for a single attack turn.

    Implementations read the roster and shared services (propose/vote/synthesise/emit)
    off the engine and write this turn's `_turn_proposals` / `_turn_winner` back onto it,
    exactly as the engine's executor expects.
    """

    @abstractmethod
    def run_turn(self, eng: "GraphAttack", goal: str, turn: int, gi: int) -> str:
        """Run one turn for `goal` (index `gi`), returning the prompt to strike with."""
        raise NotImplementedError


def register(*modes: str):
    """Class decorator registering a `Topology` under one or more mode strings."""

    def decorator(cls: type[Topology]) -> type[Topology]:
        for mode in modes:
            REGISTRY[mode] = cls
        return cls

    return decorator


def get_topology(mode: str) -> Topology:
    """Return a fresh strategy instance for `mode`, falling back to the default."""
    cls = REGISTRY.get(mode) or REGISTRY[DEFAULT_MODE]
    return cls()


def known_modes() -> list[str]:
    """All registered mode strings, sorted — handy for diagnostics and docs."""
    return sorted(REGISTRY)
