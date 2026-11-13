"""Metrics router: `GET /metrics` in the Prometheus text format (spec 008).

The registry lives in `myrtia.telemetry`; this layer only serves it and applies the
access token. A collector sends the token as a bearer credential (or in the
`X-Myrtia-Token` header); it is not accepted as a query parameter here, so it never
ends up in a scrape URL.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import PlainTextResponse

from myrtia import telemetry
from myrtia.api import deps

router = APIRouter()

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
