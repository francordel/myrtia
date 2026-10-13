"""Curated goal datasets downloaded on demand from pinned upstream files.

Only allowlisted HTTPS URLs are fetched. Files are size-limited, SHA-256 checked,
parsed as CSV, and stored locally; importing a dataset never executes its code.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

_MAX_BYTES = 2_000_000
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / ".data" / "goal_datasets"

SOURCES: dict[str, dict[str, Any]] = {
    "jailbreakbench": {
        "name": "JailbreakBench · JBB-Behaviors",
        "description": "100 harmful goals across ten misuse categories. The benign and judge-comparison splits are excluded.",
        "homepage": "https://github.com/JailbreakBench/jailbreakbench",
        "license": "MIT",
        "revision": "886acc352a31533ffbcf4ef22c744658688086fc",
        "url": "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/886acc352a31533ffbcf4ef22c744658688086fc/data/harmful-behaviors.csv",
        "sha256": "4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1",
        "rows": 100,
        "goal_column": "Goal",
        "theme_column": "Category",
        "source_column": "Source",
        "id_column": "Index",
    },
    "advbench": {
        "name": "AdvBench · Harmful Behaviors",
        "description": "520 harmful goals used in adversarial attack research; this source has no category column.",
        "homepage": "https://github.com/llm-attacks/llm-attacks",
        "license": "MIT",
        "revision": "098262edf85f807224e70ecd87b9d83716bf6b73",
        "url": "https://raw.githubusercontent.com/llm-attacks/llm-attacks/098262edf85f807224e70ecd87b9d83716bf6b73/data/advbench/harmful_behaviors.csv",
        "sha256": "6cd1a5c63c07610d7eb67307772ee5606017ee950b5770ab288a2c487489d3e1",
        "rows": 520,
        "goal_column": "goal",
        "theme": "advbench",
    },
    "strongreject": {
        "name": "StrongREJECT · Small",
        "description": "60 curated forbidden questions across six categories from the original benchmark's small subset.",
        "homepage": "https://github.com/alexandrasouly/strongreject",
        "license": "MIT",
        "revision": "f7cad6c17e624e21d8df2278e918ae1dddb4cb56",
        "url": "https://raw.githubusercontent.com/alexandrasouly/strongreject/f7cad6c17e624e21d8df2278e918ae1dddb4cb56/strongreject_dataset/strongreject_small_dataset.csv",
        "sha256": "3051340e3e89a3598d764dde497d5fcda80e258ac05cc35e6bd87228ac3d467c",
        "rows": 60,
        "goal_column": "forbidden_prompt",
        "theme_column": "category",
        "source_column": "source",
    },
}


def _directory() -> Path:
    return Path(os.environ.get("MYRTIA_GOAL_DATA_DIR", _DEFAULT_DIR))


def _path(dataset_id: str) -> Path:
    if dataset_id not in SOURCES:
        raise ValueError(f"unknown goal dataset: {dataset_id!r}")
    return _directory() / f"{dataset_id}.csv"


def _verified_bytes(dataset_id: str) -> bytes | None:
    path = _path(dataset_id)
    try:
        if path.stat().st_size > _MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    return data if hashlib.sha256(data).hexdigest() == SOURCES[dataset_id]["sha256"] else None


def _parse(dataset_id: str, data: bytes) -> list[dict[str, str]]:
    spec = SOURCES[dataset_id]
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if spec["goal_column"] not in (reader.fieldnames or []):
        raise ValueError(f"{dataset_id}: missing goal column")
    if spec.get("theme_column") and spec["theme_column"] not in (reader.fieldnames or []):
        raise ValueError(f"{dataset_id}: missing category column")
    rows: list[dict[str, str]] = []
    for index, row in enumerate(reader):
        goal = (row.get(spec["goal_column"]) or "").strip()
        if not goal or len(goal) > 8000:
            raise ValueError(f"{dataset_id}: invalid goal in row {index + 1}")
        rows.append({
            "id": f"{dataset_id}:{row.get(spec.get('id_column')) or index + 1}",
            "goal": goal,
            "theme": (row.get(spec.get("theme_column")) or spec.get("theme") or "other").strip(),
            "context": "",
            "dataset": dataset_id,
            "source": (row.get(spec.get("source_column")) or "").strip(),
        })
    if len(rows) != spec["rows"]:
        raise ValueError(f"{dataset_id}: expected {spec['rows']} goals, found {len(rows)}")
    return rows


def catalog() -> list[dict[str, Any]]:
    """Public catalog, including the bundled default and verified downloads."""
    from myrtia.data.behaviors import load_behaviors

    out = [{
        "id": "harmbench", "name": "HarmBench", "description": "Bundled default goal library.",
        "homepage": "https://github.com/centerforaisafety/HarmBench", "license": "MIT",
        "installed": True, "installable": False, "rows": len(load_behaviors()),
    }]
    for dataset_id, spec in SOURCES.items():
        out.append({
            "id": dataset_id, "name": spec["name"], "description": spec["description"],
            "homepage": spec["homepage"], "license": spec["license"],
            "revision": spec["revision"], "installed": _verified_bytes(dataset_id) is not None,
            "installable": True, "rows": spec["rows"],
        })
    return out


def load_downloaded(dataset_id: str) -> list[dict[str, str]]:
    data = _verified_bytes(dataset_id)
    return _parse(dataset_id, data) if data is not None else []


def all_behaviors(dataset_id: str = "") -> list[dict[str, Any]]:
    from myrtia.data.behaviors import load_behaviors

    if dataset_id and dataset_id not in ("harmbench", "custom", *SOURCES):
        raise ValueError(f"unknown goal dataset: {dataset_id!r}")
    rows: list[dict[str, Any]] = list(load_behaviors()) if dataset_id in ("", "harmbench") else []
    for key in SOURCES:
        if dataset_id in ("", key):
            rows.extend(load_downloaded(key))
    return rows


def install(dataset_id: str) -> dict[str, Any]:
    """Download one pinned CSV, validate it, then atomically expose it."""
    spec = SOURCES.get(dataset_id)
    if spec is None:
        return {"ok": False, "error": f"unknown goal dataset: {dataset_id!r}"}
    if _verified_bytes(dataset_id) is not None:
        return {"ok": True, "installed": True, "count": spec["rows"], "log": "already downloaded"}
    try:
        request = urllib.request.Request(spec["url"], headers={"User-Agent": "Myrtia/0.0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            raise ValueError("dataset exceeds 2 MB limit")
        if hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise ValueError("source SHA-256 differs from the pinned version")
        rows = _parse(dataset_id, data)
        directory = _directory()
        directory.mkdir(parents=True, exist_ok=True)
        name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix=f".{dataset_id}-", suffix=".tmp", delete=False) as temp:
                name = temp.name
                temp.write(data)
            os.chmod(name, 0o600)
            os.replace(name, _path(dataset_id))
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        return {"ok": True, "installed": True, "count": len(rows), "log": "verified SHA-256 and saved locally"}
    except (OSError, ValueError, UnicodeError) as exc:
        return {"ok": False, "error": f"download failed: {exc}"}
