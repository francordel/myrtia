"""Optional plugin packs — install extra attack toolkits into Myrtia.

Myrtia's core runs standalone (see connectors/base.py). Extra attack toolkits ship as
*packs*: a curated, allowlisted set of known open-source projects (ARES/ares-council,
NVIDIA garak, Microsoft PyRIT, …). Installing a pack pip-installs a pinned package and
imports the module that registers its plugins, which then appear in the attack list.

Security: only ids in `PACKS` can be installed — the endpoint never runs an arbitrary
pip string. Installing a pack executes code (pip + import), so the UI confirms first.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

_VENDOR = Path(__file__).resolve().parent.parent / "vendor"

# Curated allowlist. `check` is the import name used to detect if it's installed;
# `pip` is the exact install spec; `modules` are re-imported after install so their
# plugins register; `adds` lists the attack ids the pack contributes.
PACKS: list[dict[str, Any]] = [
    {
        "id": "ares-council",
        "name": "ARES Council",
        "description": "IBM ARES CouncilAttack — the deliberating council of attacker "
                       "models (Borda vote + chairman). Adds the council and "
                       "council-crescendo attacks.",
        "check": "ares_council",
        "pip": ["-e", str(_VENDOR / "ares-council")],
        "modules": ["myrtia.plugins.council"],
        "adds": ["council", "council-crescendo"],
        "homepage": "https://github.com/IBM/ares",
        "adapter": True,
    },
    {
        "id": "garak",
        "name": "NVIDIA garak",
        "description": "garak — the LLM vulnerability scanner (100+ probes). Adds the "
                       "\"garak\" attack: run any garak probe's real corpus against the "
                       "target, graded 0-5 by the evaluator.",
        "check": "garak",
        "pip": ["garak"],
        "modules": ["myrtia.plugins.garak_adapter"],
        "adds": ["garak"],
        "homepage": "https://github.com/NVIDIA/garak",
        "adapter": True,
        "note": "Large download.",
    },
    {
        "id": "pyrit",
        "name": "Microsoft PyRIT",
        "description": "PyRIT — the Python Risk Identification Toolkit (Microsoft). Adds "
                       "the \"pyrit\" attack: transform each behaviour with a real PyRIT "
                       "converter (Base64, ROT13, leetspeak, ...), graded 0-5.",
        "check": "pyrit",
        "pip": ["pyrit"],
        "modules": ["myrtia.plugins.pyrit_adapter"],
        "adds": ["pyrit"],
        "homepage": "https://github.com/Azure/PyRIT",
        "adapter": True,
        "note": "Large download.",
    },
]


def _by_id(pid: str) -> dict | None:
    return next((p for p in PACKS if p["id"] == pid), None)


def _installed(pack: dict) -> bool:
    try:
        return importlib.util.find_spec(pack["check"]) is not None
    except Exception:  # noqa: BLE001
        return False


def list_packs() -> list[dict[str, Any]]:
    """Public view of the pack registry with per-pack installed state."""
    return [{
        "id": p["id"], "name": p["name"], "description": p["description"],
        "adds": p["adds"], "homepage": p["homepage"], "adapter": p["adapter"],
        "note": p.get("note", ""), "installed": _installed(p),
    } for p in PACKS]


def install_pack(pid: str) -> dict[str, Any]:
    """Install one allowlisted pack: pip install the pinned spec, then register its
    plugins. Returns {ok, installed?, adds?, log, error?}. Never raises."""
    pack = _by_id(pid)
    if pack is None:
        return {"ok": False, "error": f"unknown pack: {pid!r}"}
    if _installed(pack):
        _register(pack)
        return {"ok": True, "installed": True, "adds": pack["adds"], "log": "already installed"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", *pack["pip"]],
            capture_output=True, text=True, timeout=1800,
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"pip could not run: {e}"}
    log = ((proc.stdout or "")[-1500:] + "\n" + (proc.stderr or "")[-1500:]).strip()
    if proc.returncode != 0:
        return {"ok": False, "error": "pip install failed", "log": log}
    warn = _register(pack)
    return {"ok": True, "installed": True, "adds": pack["adds"], "log": log,
            **({"warning": warn} if warn else {})}


def _register(pack: dict) -> str | None:
    """(Re)import the pack's modules so their plugins register. Returns a warning str."""
    for m in pack.get("modules", []):
        try:
            mod = importlib.import_module(m)
            importlib.reload(mod)
        except Exception as e:  # noqa: BLE001
            return f"installed but registering {m} failed: {e}"
    return None
