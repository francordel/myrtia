"""Attacker topology strategies for the GraphAttack engine.

Importing this package registers every bundled topology (the modules below each call
`@register(...)` at import time, so they must be imported for the registry to fill — the
classic registry/plugin import gotcha). The engine uses `get_topology(mode)` to resolve
one; third parties can add a topology by importing a module that registers its own class,
with no edit to the engine.
"""

from __future__ import annotations

from myrtia.plugins.graph_topologies.base import (
    DEFAULT_MODE,
    REGISTRY,
    Topology,
    get_topology,
    known_modes,
    register,
)

# Import side effect: register the bundled topologies.
from myrtia.plugins.graph_topologies import (  # noqa: E402,F401
    council,
    custom,
    debate,
    moa,
    parallel,
    pipeline,
    single,
)

__all__ = [
    "DEFAULT_MODE",
    "REGISTRY",
    "Topology",
    "get_topology",
    "known_modes",
    "register",
]
