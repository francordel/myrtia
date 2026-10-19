"""Goal-data router: installed behaviour libraries, curated goal datasets and their
verified download, local model pulls (Ollama) and parsing an uploaded goals file."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from myrtia.api.deps import BehaviorParseRequest, ModelPullRequest, require_token

router = APIRouter()


@router.get("/behaviors")
async def behaviors(theme: str = "", q: str = "", dataset: str = "") -> dict[str, Any]:
    """Installed goal libraries, filterable by dataset, theme and text."""
    from myrtia.data.goal_datasets import all_behaviors, catalog

    q = q.strip().lower()
    try:
        rows = all_behaviors(dataset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out = [
        b for b in rows
        if (not theme or b["theme"] == theme) and (not q or q in b["goal"].lower())
    ]
    return {"behaviors": out, "themes": sorted({b["theme"] for b in rows}),
            "datasets": [d for d in catalog() if d["installed"]], "total": len(rows)}


@router.get("/datasets")
async def goal_datasets() -> dict[str, Any]:
    """Curated goal data packs and their verified local download state."""
    from myrtia.data.goal_datasets import catalog
    return {"datasets": catalog()}


@router.post("/datasets/{dataset_id}/install", dependencies=[Depends(require_token)])
async def install_goal_dataset(dataset_id: str) -> dict[str, Any]:
    """Fetch a pinned CSV from its allowlisted source; no package installation."""
    import asyncio as _asyncio
    from myrtia.data.goal_datasets import install
    return await _asyncio.get_running_loop().run_in_executor(None, install, dataset_id)


@router.post("/models/pull", dependencies=[Depends(require_token)])
def pull_model(body: ModelPullRequest) -> Any:
    """Pull a local model via Ollama's native API, streaming progress (issue #4).

    Body: {base_url, name}. The base_url is the same OpenAI-compatible endpoint used
    for a target; the Ollama root is it with a trailing /v1 stripped. Streams the
    raw NDJSON progress lines from Ollama straight through to the caller. SSRF-guarded.
    """
    body = body.model_dump()
    import json as _j
    import requests
    base = str(body.get("base_url") or "").rstrip("/")
    name = str(body.get("name") or "").strip()
    if not base or not name:
        return JSONResponse({"error": "base_url and name are required"}, status_code=400)
    from myrtia.security import url_block_reason
    blocked = url_block_reason(base)
    if blocked:
        return JSONResponse({"error": f"blocked base_url: {blocked}"}, status_code=400)
    root = base[:-3] if base.endswith("/v1") else base

    def stream():
        try:
            with requests.post(root + "/api/pull", json={"name": name, "stream": True},
                               stream=True, timeout=(10, 600), allow_redirects=False) as r:
                if r.status_code >= 400:
                    yield _j.dumps({"error": f"HTTP {r.status_code}: {r.text[:200]}"}) + "\n"
                    return
                for raw in r.iter_lines():
                    if raw:
                        line = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
                        yield line + "\n"
        except requests.RequestException as e:  # noqa: BLE001
            yield _j.dumps({"error": f"pull failed: {e}"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/behaviors/parse", dependencies=[Depends(require_token)])
async def parse_behaviors(body: BehaviorParseRequest) -> dict[str, Any]:
    """Parse an uploaded goals file into behaviours (issue #5).

    Accepts either a HarmBench-shaped CSV (a ``Behavior`` column, optional
    ``SemanticCategory`` and ``ContextString``) or a plain-text file with one goal
    per line. Validates and caps; never stores anything — the parsed goals go
    straight into the run as a custom theme. Body: {content, filename?, theme?}.
    """
    body = body.model_dump()
    import csv as _csv
    import io as _io
    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        return JSONResponse({"error": "empty file"}, status_code=400)  # type: ignore[return-value]
    if len(content) > 2_000_000:
        return JSONResponse({"error": "file too large (max 2 MB)"}, status_code=413)  # type: ignore[return-value]
    fname = (body.get("filename") or "").lower()
    theme = (body.get("theme") or "").strip() or "custom"
    _MAX_ROWS = 2000
    goals: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    fmt = "text"
    # Detect CSV: a .csv name, or a header line that contains a Behavior column.
    head = content.splitlines()[0] if content.splitlines() else ""
    looks_csv = fname.endswith(".csv") or ("," in head and "behavior" in head.lower())
    if looks_csv:
        fmt = "csv"
        try:
            reader = _csv.DictReader(_io.StringIO(content))
            cols = {(c or "").strip().lower(): c for c in (reader.fieldnames or [])}
            beh_col = cols.get("behavior") or cols.get("goal") or cols.get("prompt")
            if not beh_col:
                return JSONResponse({"error": "CSV needs a Behavior (or goal/prompt) column"}, status_code=400)  # type: ignore[return-value]
            cat_col = cols.get("semanticcategory") or cols.get("theme") or cols.get("category")
            ctx_col = cols.get("contextstring") or cols.get("context")
            for i, row in enumerate(reader):
                if len(goals) >= _MAX_ROWS:
                    errors.append(f"stopped at {_MAX_ROWS} rows")
                    break
                g = (row.get(beh_col) or "").strip()
                if not g:
                    continue
                if len(g) > 8000:
                    errors.append(f"row {i + 1}: goal too long, truncated")
                    g = g[:8000]
                if g in seen:
                    continue
                seen.add(g)
                goals.append({"goal": g, "theme": (row.get(cat_col) or theme).strip() if cat_col else theme,
                              "context": (row.get(ctx_col) or "").strip() if ctx_col else ""})
        except Exception as e:  # noqa: BLE001
            return JSONResponse({"error": f"could not parse CSV: {e}"}, status_code=400)  # type: ignore[return-value]
    else:
        for i, line in enumerate(content.splitlines()):
            g = line.strip()
            if not g or g.startswith("#"):
                continue
            if len(goals) >= _MAX_ROWS:
                errors.append(f"stopped at {_MAX_ROWS} rows")
                break
            if len(g) > 8000:
                errors.append(f"line {i + 1}: goal too long, truncated")
                g = g[:8000]
            if g in seen:
                continue
            seen.add(g)
            goals.append({"goal": g, "theme": theme, "context": ""})
    if not goals:
        return JSONResponse({"error": "no goals found in the file"}, status_code=400)  # type: ignore[return-value]
    return {"format": fmt, "count": len(goals), "theme": theme, "goals": goals, "errors": errors}
