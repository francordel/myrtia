"""Myrtia backend API — FastAPI composition root.

This module wires the application together and nothing more: it discovers and
registers the bundled attack plugins, creates the FastAPI app, installs the
security middleware (CORS, headers, body-size cap) and mounts one router per
domain. The endpoints themselves live in ``myrtia.api.routers.*`` and the shared
request models / access gate in ``myrtia.api.deps``.

Routers:
    meta       -> app shell + assets, /health, /system, /plugins, /profiles,
                  /estimate, /defenses, /packs
    chat       -> /chat, /chat/stream (OpenAI-compatible proxy)
    datasets   -> /behaviors, /datasets, /models/pull, /behaviors/parse
    runs       -> /runs lifecycle, /runs/{id}/export|report, /preflight, WS events
    stats      -> /stats, /audit
    approvals  -> /approvals (human-in-the-loop)

Run with: ``uvicorn myrtia.api.app:app``.
"""

from __future__ import annotations

import importlib as _importlib
import os
import pkgutil as _pkgutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from myrtia.api.deps import APP_VERSION
from myrtia.api.routers import (
    approvals as _approvals,
    chat as _chat,
    datasets as _datasets,
    meta as _meta,
    runs as _runs,
    stats as _stats,
)
import myrtia.plugins as _plugins_pkg

_PLUGIN_SKIP = {"base", "council_prompts", "council_official"}
for _m in _pkgutil.iter_modules(_plugins_pkg.__path__):
    if _m.name.startswith("_") or _m.name in _PLUGIN_SKIP:
        continue
    _importlib.import_module(f"myrtia.plugins.{_m.name}")  # noqa: F401 (registers on import)

app = FastAPI(title="Myrtia", version=APP_VERSION)

# --- security middleware --------------------------------------------------------
# The UI is served same-origin, so CORS only needs to cover the local origins the
# operator uses. Restricting it (vs "*") blocks drive-by pages from reading the API
# cross-origin. Extra origins can be added via MYRTIA_ALLOW_ORIGINS (comma-separated).
_allowed = ["http://localhost:8000", "http://127.0.0.1:8000"]
_allowed += [o.strip() for o in os.getenv("MYRTIA_ALLOW_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    # Clickjacking + defense-in-depth. Inline styles/scripts are used by the single-file
    # UI, so script/style allow 'unsafe-inline'; framing is denied; connections are same-origin.
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return resp


# DoS caps (issue #27). Reject oversized request bodies early (by Content-Length),
# before FastAPI buffers/parses them. The attack payloads and goal lists are small;
# 4 MB is generous. Override with MYRTIA_MAX_BODY (bytes).
_MAX_BODY = int(os.getenv("MYRTIA_MAX_BODY", str(4 * 1024 * 1024)))


@app.middleware("http")
async def limit_body_size(request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > _MAX_BODY:
            return JSONResponse({"error": f"request body too large (max {_MAX_BODY} bytes)"}, status_code=413)
    return await call_next(request)


# --- routers --------------------------------------------------------------------
app.include_router(_meta.router)
app.include_router(_chat.router)
app.include_router(_datasets.router)
app.include_router(_runs.router)
app.include_router(_stats.router)
app.include_router(_approvals.router)


# --- compatibility re-exports ---------------------------------------------------
# Tests and tooling monkeypatch the shared singletons and call these helpers via
# ``myrtia.api.app`` (the historical home). The monkeypatches mutate the singleton
# objects in place, so importing them here binds the very same objects the routers
# use — patching ``appmod.STORE.list`` is seen by every router.
from myrtia.events.bus import BUS  # noqa: E402,F401
from myrtia.orchestrator.runner import ORCHESTRATOR  # noqa: E402,F401
from myrtia.store.runs import STORE  # noqa: E402,F401
from myrtia.api.routers.runs import _list_models, _repro_meta  # noqa: E402,F401
