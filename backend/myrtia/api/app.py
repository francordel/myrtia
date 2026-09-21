"""Myrtia backend API — FastAPI: REST run control + per-run WebSocket event stream.

Endpoints (MVP):
    GET  /health
    GET  /plugins                 -> available attacks
    POST /runs                    -> create + launch a run
    GET  /runs                    -> list runs
    GET  /runs/{id}               -> run detail (spec, status, results)
    WS   /runs/{id}/events        -> live event stream (backlog first, then live)
    GET  /approvals               -> pending HITL approvals
    POST /approvals/{id}          -> resolve one ({"decision": true|false})
"""

from __future__ import annotations

import asyncio
from typing import Any

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from myrtia.events.bus import BUS
from myrtia.events.schema import Event, EventType
from myrtia.hitl.approvals import REGISTRY as APPROVALS
from myrtia.orchestrator.runner import ORCHESTRATOR
from myrtia.plugins.base import REGISTRY as PLUGINS
from myrtia.store.runs import RunSpec, STORE

# Import side effect: register the bundled plugins.
import myrtia.plugins.council  # noqa: F401
import myrtia.plugins.direct  # noqa: F401

app = FastAPI(title="Myrtia", version="0.0.1")

# Local-dev convenience: allow the standalone viewer (any origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the zero-build viewer at / so it shares the backend origin (no CORS/WS issues).
_STANDALONE = Path(__file__).resolve().parents[3] / "frontend" / "standalone.html"


_FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
_ASSETS = {"icon.png", "icon-light.png", "icon-dark.png"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_STANDALONE)


@app.get("/assets/{name}")
async def asset(name: str) -> FileResponse:
    # Serve a small whitelist of brand images (no path traversal, no route shadowing).
    if name not in _ASSETS:
        return JSONResponse({"error": "not found"}, status_code=404)  # type: ignore[return-value]
    return FileResponse(_FRONTEND / name)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/behaviors")
async def behaviors(theme: str = "", q: str = "") -> dict[str, Any]:
    """Malicious-behaviour library, filterable by theme and text, for run config."""
    from myrtia.data.behaviors import load_behaviors, themes

    q = q.strip().lower()
    rows = load_behaviors()
    out = [
        b for b in rows
        if (not theme or b["theme"] == theme) and (not q or q in b["goal"].lower())
    ]
    return {"behaviors": out, "themes": themes(), "total": len(rows)}


@app.get("/plugins")
async def plugins() -> dict[str, Any]:
    return {
        "plugins": [
            {"id": s.id, "description": s.description, "config_schema": s.config_schema}
            for s in PLUGINS.values()
        ]
    }


@app.post("/runs")
async def create_run(body: dict[str, Any]) -> dict[str, Any]:
    spec = RunSpec(
        attack_id=body["attack_id"],
        attack_config=body.get("attack_config", {}),
        target=body.get("target", {}),
        goals=body.get("goals", []),
        judge_id=body.get("judge_id"),
        theme=(body.get("theme") or "").strip(),
    )
    run = STORE.create(spec)
    # Fire-and-forget: the run drives itself and streams over the WebSocket.
    asyncio.create_task(ORCHESTRATOR.run(run))
    return {"run_id": run.id, "status": run.status.value}


@app.get("/stats")
async def stats() -> dict[str, Any]:
    """Aggregated analytics across all runs, per-goal.

    Breakdowns by theme, target model, attack, per-behaviour, plus council-specific
    per-member metrics (proposals, Borda-vote wins, avg Borda score).
    """
    runs = STORE.list()

    by_theme: dict[str, dict] = {}
    by_target: dict[str, dict] = {}
    by_attack: dict[str, dict] = {}
    by_behavior: list[dict] = []
    score_dist = [0, 0, 0, 0, 0, 0]
    members: dict[str, dict] = {}   # council-member stats

    def bump(d: dict, key: str, success: bool, best: int | None) -> None:
        key = key or "(none)"
        e = d.setdefault(key, {"goals": 0, "jailbroken": 0, "score_sum": 0, "scored": 0})
        e["goals"] += 1
        if success:
            e["jailbroken"] += 1
        if best is not None:
            e["score_sum"] += best
            e["scored"] += 1

    for run in runs:
        theme = run.spec.theme
        target = (run.spec.target or {}).get("model") or "(unknown)"
        attack = run.spec.attack_id
        for r in run.results:
            turns = r.get("council_turns", []) or []
            scores = [t.get("judge_score") for t in turns if isinstance(t.get("judge_score"), int)]
            best = max(scores) if scores else None
            success = bool(r.get("success"))
            bump(by_theme, theme, success, best)
            bump(by_target, target, success, best)
            bump(by_attack, attack, success, best)
            if best is not None and 0 <= best <= 5:
                score_dist[best] += 1
            by_behavior.append({
                "goal": r.get("goal", "")[:120], "theme": theme, "attack": attack,
                "target": target, "best": best, "success": success,
                "turns": r.get("turns_used"),
            })
            # council-member metrics
            for t in turns:
                props = t.get("proposals", []) or []
                winner_idx = t.get("winner_original_index")
                for p in props:
                    m = p.get("model") or "?"
                    me = members.setdefault(m, {"proposals": 0, "wins": 0, "borda_sum": 0, "borda_n": 0})
                    me["proposals"] += 1
                    if isinstance(p.get("borda_score"), int):
                        me["borda_sum"] += p["borda_score"]; me["borda_n"] += 1
                    if winner_idx is not None and p.get("original_index") == winner_idx:
                        me["wins"] += 1

    def finalize(d: dict) -> list[dict]:
        out = []
        for k, e in d.items():
            asr = round(100 * e["jailbroken"] / e["goals"]) if e["goals"] else 0
            avg = round(e["score_sum"] / e["scored"], 2) if e["scored"] else None
            out.append({"key": k, "goals": e["goals"], "jailbroken": e["jailbroken"],
                        "asr": asr, "avg_score": avg})
        return sorted(out, key=lambda x: (-x["asr"], -x["goals"]))

    member_rows = []
    for m, e in members.items():
        member_rows.append({
            "model": m, "proposals": e["proposals"], "wins": e["wins"],
            "win_rate": round(100 * e["wins"] / e["proposals"]) if e["proposals"] else 0,
            "avg_borda": round(e["borda_sum"] / e["borda_n"], 2) if e["borda_n"] else None,
        })
    member_rows.sort(key=lambda x: -x["win_rate"])

    total_goals = sum(len(r.results) for r in runs)
    jb = sum(1 for run in runs for r in run.results if r.get("success"))
    return {
        "total_runs": len(runs), "total_goals": total_goals, "jailbroken": jb,
        "asr": round(100 * jb / total_goals) if total_goals else 0,
        "score_distribution": score_dist,
        "by_theme": finalize(by_theme),
        "by_target": finalize(by_target),
        "by_attack": finalize(by_attack),
        "council_members": member_rows,
        "by_behavior": sorted(by_behavior, key=lambda x: -(x["best"] or 0))[:50],
    }


@app.get("/runs")
async def list_runs(
    q: str = "",
    theme: str = "",
    result: str = "",
    min_score: int = -1,
) -> dict[str, Any]:
    """Searchable/filterable run history.

    q         -> substring match on goal text or theme
    theme     -> exact theme match
    result    -> 'succeeded' | 'failed' (run status)
    min_score -> minimum graded evaluation score (best judge score across turns)
    """
    q = q.strip().lower()
    runs = [r.summary() for r in STORE.list()]
    out = []
    for s in runs:
        hay = (" ".join(s["goals"]) + " " + (s["theme"] or "")).lower()
        if q and q not in hay:
            continue
        if theme and s["theme"] != theme:
            continue
        if result and s["status"] != result:
            continue
        if min_score >= 0 and (s["best_score"] is None or s["best_score"] < min_score):
            continue
        out.append(s)
    themes = sorted({s["theme"] for s in runs if s["theme"]})
    return {"runs": out, "themes": themes, "total": len(runs)}


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    run = STORE.get(run_id)
    if run is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(run.to_dict())


@app.websocket("/runs/{run_id}/events")
async def run_events(ws: WebSocket, run_id: str) -> None:
    # Stream by replaying the run's backlog in order and polling for new entries.
    # The backlog is the single source of truth, so this delivers every event
    # regardless of when the client connects — no subscribe-timing races.
    await ws.accept()
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
            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass


@app.get("/approvals")
async def approvals() -> dict[str, Any]:
    return {
        "approvals": [
            {"id": a.id, "run_id": a.run_id, "action": a.action, "detail": a.detail}
            for a in APPROVALS.pending()
        ]
    }


@app.post("/approvals/{approval_id}")
async def resolve_approval(approval_id: str, body: dict[str, Any]) -> dict[str, Any]:
    ok = APPROVALS.resolve(approval_id, bool(body.get("decision", False)))
    return {"resolved": ok}
