"""Human-in-the-loop router: list pending approvals and resolve one."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from myrtia.api.deps import ApprovalDecision, require_token
from myrtia.hitl.approvals import REGISTRY as APPROVALS

router = APIRouter()


@router.get("/approvals")
async def approvals() -> dict[str, Any]:
    return {
        "approvals": [
            {"id": a.id, "run_id": a.run_id, "action": a.action, "detail": a.detail}
            for a in APPROVALS.pending()
        ]
    }


@router.post("/approvals/{approval_id}", dependencies=[Depends(require_token)])
async def resolve_approval(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
    body = body.model_dump()
    ok = APPROVALS.resolve(approval_id, bool(body.get("decision", False)))
    return {"resolved": ok}
