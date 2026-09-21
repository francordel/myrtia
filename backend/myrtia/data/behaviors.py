"""Malicious-behaviour library (HarmBench) for run configuration.

Loads the vendored HarmBench behaviours (filtered set, Apache/MIT test corpus) and
exposes them grouped by theme (SemanticCategory) so the UI can let the operator
select which behaviours to attack — all, by theme, or an arbitrary subset.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

_CSV = Path(__file__).with_name("harmbench_behaviors.csv")


@lru_cache(maxsize=1)
def load_behaviors() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            beh = (r.get("Behavior") or "").strip()
            if not beh:
                continue
            rows.append({
                "id": r.get("BehaviorID") or beh[:40],
                "goal": beh,
                "theme": r.get("SemanticCategory") or "other",
                "context": (r.get("ContextString") or "").strip(),
            })
    return rows


def themes() -> list[str]:
    return sorted({b["theme"] for b in load_behaviors()})
