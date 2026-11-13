"""Metrics router (spec 008): `GET /metrics` in the Prometheus text format, and
`GET /observability`, which tells the console where the dashboard is.

The registry lives in `myrtia.telemetry`; this layer only serves it and applies the
access token. A collector sends the token as a bearer credential (or in the
`X-Myrtia-Token` header); it is not accepted as a query parameter here, so it never
ends up in a scrape URL.
"""

from __future__ import annotations

import asyncio
import hmac
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse
import requests

from myrtia import telemetry, tracing
from myrtia.api import deps

router = APIRouter()

# Where the console's "Dashboard" control leads. `off` hides the control.
GRAFANA_URL = (os.getenv("MYRTIA_GRAFANA_URL") or "http://localhost:3000").strip().rstrip("/")
_DASHBOARD_PATH = "/d/myrtia-overview/myrtia-overview"
_START_COMMAND = "docker compose -f compose.observability.yaml up -d"

_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _require_metrics_token(authorization: str | None = Header(default=None),
                           x_myrtia_token: str | None = Header(default=None)) -> None:
    expected = deps._ACCESS_TOKEN
    if not expected:
        return
    offered = x_myrtia_token or ""
    if authorization and authorization.lower().startswith("bearer "):
        offered = authorization[7:].strip()
    if not hmac.compare_digest(offered.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="missing or invalid access token")


@router.get("/metrics", dependencies=[Depends(_require_metrics_token)])
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(telemetry.render(deps.APP_VERSION), media_type=_CONTENT_TYPE)


def _dashboard_answers(base: str) -> bool:
    """One short, guarded request to the dashboard's health address."""
    from myrtia.security import url_block_reason
    if url_block_reason(base):
        return False
    try:
        r = requests.get(base + "/api/health", timeout=1.5, allow_redirects=False)
    except requests.RequestException:
        return False
    return r.status_code == 200


@router.get("/observability")
async def observability() -> dict[str, Any]:
    """Where the dashboard is and whether it answers, for the console's control. The
    page cannot check this itself: its content policy only lets it talk to Myrtia."""
    base = GRAFANA_URL
    if not base or base.lower() in ("off", "false", "0", "none"):
        return {"enabled": False}
    reachable = await asyncio.get_running_loop().run_in_executor(None, _dashboard_answers, base)
    traces = tracing.status()
    return {"enabled": True, "url": base, "dashboard_url": base + _DASHBOARD_PATH,
            "reachable": reachable, "start_command": _START_COMMAND,
            "tracing": {"enabled": traces["enabled"], "reason": traces["reason"]}}
