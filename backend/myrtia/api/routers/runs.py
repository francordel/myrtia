"""Runs router: the attack run lifecycle (create / list / detail / stop / purpose),
exports (JSON / CSV), the printable HTML report, target preflight and the per-run
WebSocket event stream. Rendering lives in the pure `myrtia.report` service."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse

from myrtia.api.deps import APP_VERSION, PreflightRequest, PurposeRequest, RunRequest, require_token
from myrtia.events.bus import BUS
from myrtia.events.schema import Event, EventType
from myrtia.orchestrator.runner import ORCHESTRATOR
from myrtia.plugins.base import REGISTRY as PLUGINS
from myrtia.store.runs import RunSpec, STORE

router = APIRouter()

_RUN_TASKS: set = set()  # live run tasks (avoid fire-and-forget GC)

# Cap concurrently-running runs so a burst of launches can't exhaust the box. Override
# with MYRTIA_MAX_CONCURRENT_RUNS. Terminal runs never count.
_MAX_CONCURRENT_RUNS = int(os.getenv("MYRTIA_MAX_CONCURRENT_RUNS", "8"))


@router.post("/runs", dependencies=[Depends(require_token)])
async def create_run(body: RunRequest) -> dict[str, Any]:
    body = body.model_dump()
    attack_id = body.get("attack_id")
    if not attack_id or attack_id not in PLUGINS:
        return JSONResponse({"error": f"unknown attack_id: {attack_id!r}"}, status_code=400)  # type: ignore[return-value]
    goals = body.get("goals") or []
    if not isinstance(goals, list) or not goals:
        return JSONResponse({"error": "goals must be a non-empty list"}, status_code=400)  # type: ignore[return-value]
    if len(goals) > 500:
        return JSONResponse({"error": "too many goals (max 500)"}, status_code=400)  # type: ignore[return-value]
    if any(not isinstance(g, str) or len(g) > 8000 for g in goals):
        return JSONResponse({"error": "each goal must be a string of at most 8000 chars"}, status_code=400)  # type: ignore[return-value]
    attack_config = body.get("attack_config") or {}
    if attack_id == "graph" and attack_config.get("contextual_mode") and attack_config.get("accumulate_target_context"):
        return JSONResponse({"error": "contextual priming and accumulated target context are mutually exclusive"}, status_code=400)  # type: ignore[return-value]
    title = body.get("title", "").strip()
    if len(title) > 120 or any(ord(c) < 32 or ord(c) == 127 for c in title):
        return JSONResponse({"error": "title must be at most 120 characters on one line"}, status_code=400)  # type: ignore[return-value]
    if body.get("purpose") not in ("security", "smoke", "unreviewed"):
        return JSONResponse({"error": "purpose must be security, smoke or unreviewed"}, status_code=400)  # type: ignore[return-value]
    datasets = body.get("goal_datasets") or []
    if datasets and (len(datasets) != len(goals) or any(not isinstance(d, str) or len(d) > 100 for d in datasets)):
        return JSONResponse({"error": "goal_datasets must match goals"}, status_code=400)  # type: ignore[return-value]
    from myrtia.store.runs import RunStatus as _RS
    active = sum(1 for r in STORE.list() if r.status in (_RS.PENDING, _RS.RUNNING, _RS.WAITING_APPROVAL))
    if active >= _MAX_CONCURRENT_RUNS:
        return JSONResponse({"error": f"too many concurrent runs (max {_MAX_CONCURRENT_RUNS}); wait for one to finish"}, status_code=429)  # type: ignore[return-value]
    from myrtia.security import url_block_reason
    tb = (body.get("target") or {}).get("base_url")
    if tb and url_block_reason(tb):
        return JSONResponse({"error": f"blocked target base_url: {url_block_reason(tb)}"}, status_code=400)  # type: ignore[return-value]
    spec = RunSpec(
        attack_id=attack_id,
        attack_config=body.get("attack_config", {}),
        target=body.get("target", {}),
        goals=goals,
        judge_id=body.get("judge_id"),
        theme=(body.get("theme") or "").strip(),
        title=title,
        defenses=body.get("defenses") or [],
        purpose=body.get("purpose", "unreviewed"),
        goal_datasets=datasets,
    )
    run = STORE.create(spec)
    # Fire-and-forget: the run drives itself and streams over the WebSocket.
    task = asyncio.create_task(ORCHESTRATOR.run(run))
    _RUN_TASKS.add(task)  # keep a reference so the task is not garbage-collected mid-run
    task.add_done_callback(_RUN_TASKS.discard)
    return {"run_id": run.id, "status": run.status.value}


@router.post("/runs/{run_id}/stop", dependencies=[Depends(require_token)])
async def stop_run(run_id: str) -> dict[str, Any]:
    """Request cooperative cancellation of a running attack (stops at the next turn)."""
    return {"stopping": ORCHESTRATOR.cancel(run_id)}


@router.patch("/runs/{run_id}/purpose", dependencies=[Depends(require_token)])
async def set_run_purpose(run_id: str, body: PurposeRequest) -> Any:
    if body.purpose not in ("security", "smoke", "unreviewed"):
        return JSONResponse({"error": "invalid purpose"}, status_code=400)
    run = STORE.get(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    run.spec.purpose = body.purpose
    STORE.persist(run)
    return {"run_id": run_id, "purpose": body.purpose}


@router.get("/runs")
async def list_runs(
    q: str = "",
    theme: str = "",
    attack: str = "",
    result: str = "",
    min_score: int = -1,
    outcome: str = "",
    dataset: str = "",
    purpose: str = "",
) -> dict[str, Any]:
    """Searchable/filterable run history.

    q         -> substring match on title, goal text, theme, attack or target model
    theme     -> exact theme match
    attack    -> exact attack id match
    result    -> run status ('running' | 'succeeded' | 'failed' | 'cancelled')
    min_score -> minimum graded evaluation score (best judge score across turns)
    """
    q = q.strip().lower()
    runs = [r.summary() for r in STORE.list()]
    out = []
    for s in runs:
        hay = ((s["title"] or "") + " " + " ".join(s["goals"]) + " " + (s["theme"] or "") + " "
               + s["attack_id"] + " " + (s["target_model"] or "")).lower()
        if q and q not in hay:
            continue
        if theme and s["theme"] != theme:
            continue
        if attack and s["attack_id"] != attack:
            continue
        if result and s["status"] != result:
            continue
        if min_score >= 0 and (s["best_score"] is None or s["best_score"] < min_score):
            continue
        if outcome == "resisted" and (s["best_score"] is None or s["best_score"] > 2):
            continue
        if outcome == "not_judged" and s["best_score"] is not None:
            continue
        if dataset and dataset not in s["goal_datasets"]:
            continue
        if purpose and s["purpose"] != purpose:
            continue
        out.append(s)
    themes = sorted({s["theme"] for s in runs if s["theme"]})
    attacks = sorted({s["attack_id"] for s in runs if s["attack_id"]})
    datasets = sorted({d for s in runs for d in s["goal_datasets"] if d})
    active_runs = [s for s in runs if s["status"] == "running"]
    return {"runs": out, "active_runs": active_runs,
            "themes": themes, "attacks": attacks, "datasets": datasets, "total": len(runs)}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    run = STORE.get(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(run.to_dict())


def _git_commit() -> str | None:
    """Best-effort short commit of the running code, for reproducibility."""
    try:
        import subprocess
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=str(Path(__file__).resolve().parents[4]),
                              capture_output=True, text=True, timeout=3).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _repro_meta(run: Any) -> dict[str, Any]:
    """Everything needed to reproduce a run: versions, code commit, and the exact
    knobs (attack, target, judge, defenses, goals). Secrets are already redacted in
    run.to_dict(); this reads only non-secret fields. Issue #21."""
    import datetime as _dt
    import platform as _pf
    cfg = run.spec.attack_config or {}
    tgt = run.spec.target or {}
    def iso(ts):
        return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).isoformat() if ts else None

    return {
        "myrtia_version": APP_VERSION,
        "git_commit": _git_commit(),
        "python": _pf.python_version(),
        "platform": _pf.platform(),
        "created_at_utc": iso(getattr(run, "created_at", None)),
        "exported_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "attack_id": run.spec.attack_id,
        "title": run.spec.title,
        "target": {"model": tgt.get("model"), "base_url": tgt.get("base_url"), "kind": tgt.get("kind")},
        "judge": {"model": cfg.get("judge_model"), "endpoint": cfg.get("judge_endpoint")},
        "defenses": [d.get("id") if isinstance(d, dict) else d for d in (run.spec.defenses or [])],
        "theme": run.spec.theme,
        "purpose": run.spec.purpose,
        "goal_datasets": run.spec.goal_datasets,
        "n_goals": len(run.spec.goals or []),
    }


def _sanitize_csv_cell(val: Any) -> Any:
    """Neutralize formula injection (CWE-1236) in spreadsheet exports."""
    if val is None:
        return ""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


@router.get("/runs/{run_id}/export")
async def export_run(run_id: str, format: str = "json") -> Any:
    """Download a run as JSON (full, redacted) or CSV (one row per turn/goal). Issue #11."""
    run = STORE.get(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    d = run.to_dict()  # already secret-redacted
    d["reproducibility"] = _repro_meta(run)
    fname = f"myrtia-{run.spec.attack_id}-{run_id[:8]}"
    if format == "csv":
        import csv
        import io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["experiment_title", "goal", "dataset", "purpose", "turn", "winner_model", "score", "success", "prompt", "response"])
        for i, r in enumerate(run.results or []):
            goal = r.get("goal", "")
            source = run.spec.goal_datasets[i] if i < len(run.spec.goal_datasets) else ""
            turns = r.get("council_turns") or []
            if turns:
                for t in turns:
                    w.writerow([_sanitize_csv_cell(c) for c in [
                        run.spec.title, goal, source, run.spec.purpose, t.get("turn", ""), t.get("winner_model", ""),
                        t.get("judge_score", ""), r.get("success", ""),
                        (t.get("prompt") or "")[:2000], (t.get("response") or "")[:2000]
                    ]])
            else:
                resp = r.get("response")
                resp = resp.get("response") if isinstance(resp, dict) else resp
                w.writerow([_sanitize_csv_cell(c) for c in [
                    run.spec.title, goal, source, run.spec.purpose, "", "", r.get("score", ""), r.get("success", ""),
                    (r.get("prompt") or "")[:2000], str(resp or "")[:2000]
                ]])
        return StreamingResponse(
            iter([buf.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    return JSONResponse(
        d, headers={"Content-Disposition": f'attachment; filename="{fname}.json"'})


@router.get("/runs/{run_id}/report")
async def run_report(run_id: str) -> Any:
    """A self-contained, printable HTML narrative of a run (issue #20).

    One page: header (attack, target, status, ASR), a reproducibility block, then a
    section per goal with each turn's winning prompt, the target response and the
    judge score + rationale. No external assets, so it prints straight to PDF.
    """
    run = STORE.get(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    from myrtia.report import render_report
    doc = render_report(run, _repro_meta(run))
    fname = f"myrtia-report-{run.spec.attack_id}-{run_id[:8]}.html"
    return HTMLResponse(doc, headers={"Content-Disposition": f'inline; filename="{fname}"'})


@router.post("/preflight", dependencies=[Depends(require_token)])
async def preflight(body: PreflightRequest) -> dict[str, Any]:
    """Test a target endpoint before launching a run (connectivity + latency). Issue #19."""
    body = body.model_dump()
    import time as _t
    target = body.get("target") or {}
    tb = target.get("base_url")
    from myrtia.security import url_block_reason
    if tb and url_block_reason(tb):
        return {"ok": False, "error": f"blocked base_url: {url_block_reason(tb)}"}
    try:
        from myrtia.connectors.factory import build_target_connector
        conn = build_target_connector(target)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    loop = asyncio.get_running_loop()
    t0 = _t.perf_counter()
    resp = await loop.run_in_executor(None, lambda: conn.generate("Reply with the single word: ok"))
    ms = int((_t.perf_counter() - t0) * 1000)
    from myrtia.connectors.base import Status
    models = await loop.run_in_executor(None, lambda: _list_models(tb, target.get("api_key"), target.get("auth_header")))
    if getattr(resp, "status", None) == Status.SUCCESS:
        return {"ok": True, "latency_ms": ms, "sample": (getattr(resp, "response", "") or "")[:80], "models": models}
    return {"ok": False, "error": getattr(resp, "error_message", "no response"), "latency_ms": ms, "models": models}


def _list_models(base_url: str, api_key: str | None, auth_header: str | None = None) -> list[str]:
    """Best-effort dynamic model list from an endpoint (OpenAI /models + Ollama /api/tags). Issue #3."""
    import requests
    base = (base_url or "").rstrip("/")
    if not base:
        return []
    headers = {}
    if api_key:
        headers[auth_header or "Authorization"] = api_key if auth_header else f"Bearer {api_key}"
    out: list[str] = []
    try:
        r = requests.get(base + "/models", headers=headers, timeout=8, allow_redirects=False)
        if r.ok:
            out += [m.get("id") for m in (r.json().get("data") or []) if m.get("id")]
    except Exception:  # noqa: BLE001
        pass
    if not out:
        try:  # Ollama native (strip a trailing /v1)
            root = base[:-3] if base.endswith("/v1") else base
            r = requests.get(root + "/api/tags", timeout=8, allow_redirects=False)
            if r.ok:
                out += [m.get("name") for m in (r.json().get("models") or []) if m.get("name")]
        except Exception:  # noqa: BLE001
            pass
    return sorted({m for m in out if m})


@router.websocket("/runs/{run_id}/events")
async def run_events(ws: WebSocket, run_id: str) -> None:
    # Stream by replaying the run's backlog in order and polling for new entries.
    # The backlog is the single source of truth, so this delivers every event
    # regardless of when the client connects — no subscribe-timing races.
    await ws.accept()
    from myrtia.store.runs import RunStatus
    _terminal = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
    sent = 0
    try:
        while True:
            backlog = BUS.backlog(run_id)
            finished = False
            while sent < len(backlog):
                event: Event = backlog[sent]
                sent += 1
                await ws.send_json(event.to_dict())
                if event.type == EventType.RUN_FINISHED:
                    finished = True
            if finished:
                break
            # Stop (never spin forever) when the run is unknown or already in a
            # terminal state without a RUN_FINISHED event — e.g. a bogus run_id, or
            # an orphan marked FAILED on restart whose backlog has no finish event.
            run = STORE.get(run_id)
            if run is None or run.status in _terminal:
                break
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
