"""Analytics router: the dashboard stats payload and the exportable aggregate audit
(HTML / Markdown / CSV / JSON / xlsx). The aggregation itself lives in the pure
`myrtia.stats` service; this layer only wires the run store and event backlog in."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from myrtia.api.deps import APP_VERSION
from myrtia.events.bus import BUS
from myrtia.store.runs import STORE

router = APIRouter()


async def _stats_payload(attack: str = "", target: str = "", full: bool = False,
                         purpose: str = "security", dataset: str = "") -> dict[str, Any]:
    """Aggregated analytics for the dashboard. Thin wrapper over the stats service
    (myrtia.stats.compute_stats), passing the run store and the event backlog in."""
    from myrtia.stats import compute_stats
    return compute_stats(STORE.list(), BUS.backlog, attack=attack, target=target,
                         full=full, purpose=purpose, dataset=dataset)


def _dt_now_slug() -> str:
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y%m%d-%H%M")


@router.get("/stats")
async def stats(attack: str = "", target: str = "", purpose: str = "security", dataset: str = "") -> dict[str, Any]:
    """Aggregated analytics for the dashboard (per-goal ASR, severity, OWASP, strategies)."""
    return await _stats_payload(attack, target, full=False, purpose=purpose, dataset=dataset)


@router.get("/audit")
async def audit(format: str = "html", attack: str = "", target: str = "",
                purpose: str = "security", dataset: str = "") -> Any:
    """Export the aggregate red-team audit in a portable format (issue: audit report).

    format = html (print-to-PDF) | md | csv | json | xlsx. The audit reuses the full
    statistics and adds a severity distribution, OWASP LLM Top 10 coverage and a
    findings table — the same organisation promptfoo / PentAGI reports use."""
    from myrtia import audit as _audit
    data = await _stats_payload(attack, target, full=True, purpose=purpose, dataset=dataset)
    meta = {"myrtia_version": APP_VERSION}
    obj = _audit.build_audit(data, {"attack": attack, "target": target, "purpose": purpose, "dataset": dataset}, meta)
    fname = "myrtia-audit-" + (purpose if purpose in ("security", "smoke", "unreviewed", "all") else "scope") + "-" + _dt_now_slug()
    fmt = (format or "html").lower()
    if fmt in ("md", "markdown"):
        return PlainTextResponse(_audit.to_markdown(obj), headers={"Content-Disposition": f'attachment; filename="{fname}.md"'}, media_type="text/markdown")
    if fmt == "csv":
        return PlainTextResponse(_audit.to_csv(obj), headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'}, media_type="text/csv")
    if fmt == "json":
        return JSONResponse(obj, headers={"Content-Disposition": f'attachment; filename="{fname}.json"'})
    if fmt in ("xlsx", "excel"):
        try:
            blob = _audit.to_xlsx(obj)
        except Exception as exc:  # noqa: BLE001 - openpyxl missing / render error
            return JSONResponse({"error": f"xlsx export unavailable: {exc}"}, status_code=501)
        from fastapi.responses import Response as _Resp
        return _Resp(content=blob, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     headers={"Content-Disposition": f'attachment; filename="{fname}.xlsx"'})
    return HTMLResponse(_audit.to_html(obj), headers={"Content-Disposition": f'inline; filename="{fname}.html"'})
