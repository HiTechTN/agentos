import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config.settings import get_settings
from app.orchestrator import get_orchestrator
from app.utils.hitl_gateway import get_hitl_gateway
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter
from app.utils.telemetry import get_telemetry

router = APIRouter()
settings = get_settings()
metrics = get_metrics()


class RunRequest(BaseModel):
    prompt: str
    project_id: str = "default"
    workflow_id: str = ""


class ApproveRequest(BaseModel):
    approval_id: str


class RejectRequest(BaseModel):
    approval_id: str
    reason: str = ""


@router.post("/api/v1/run")
@limiter.limit(settings.rate_limit_run)  # type: ignore[untyped-decorator]
async def run_workflow(req: RunRequest, request: Request) -> dict[str, Any]:
    start = time.time()
    orchestrator = get_orchestrator()
    result = await orchestrator.run(prompt=req.prompt, project_id=req.project_id)
    duration = time.time() - start
    metrics.timing("workflow_duration", duration)
    metrics.inc("workflow_runs")
    return result


@router.get("/api/v1/status/{session_id}")
async def get_status(session_id: str) -> dict[str, Any]:
    from app.memory.session import get_session_manager

    sm = get_session_manager()
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/api/v1/hitl/approve")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def approve_action(req: ApproveRequest, request: Request) -> dict[str, Any]:
    hitl = get_hitl_gateway()
    try:
        result = hitl.approve(req.approval_id)
        metrics.inc("hitl_approved")
        from app.utils.notifications import get_notifications

        await get_notifications().notify_all(
            "HITL Approved", f"Approval {req.approval_id[:8]} was approved"
        )
        return {"status": "approved", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/v1/hitl/reject")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def reject_action(req: RejectRequest, request: Request) -> dict[str, Any]:
    hitl = get_hitl_gateway()
    try:
        result = hitl.reject(req.approval_id, req.reason)
        metrics.inc("hitl_rejected")
        return {"status": "rejected", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/v1/hitl/pending")
async def list_pending() -> dict[str, Any]:
    hitl = get_hitl_gateway()
    return {"pending": hitl.get_pending()}


@router.get("/api/v1/logs")
async def get_logs(limit: int = 100, trace_id: str = "") -> dict[str, Any]:
    telemetry = get_telemetry()
    spans = telemetry.get_spans(trace_id) if trace_id else telemetry.get_spans()
    return {"logs": spans[-limit:]}
