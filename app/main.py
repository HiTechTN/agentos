import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config.settings import get_settings
from app.orchestrator import get_orchestrator
from app.utils.hitl_gateway import get_hitl_gateway
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger("api")


class RunRequest(BaseModel):
    prompt: str
    project_id: str = "default"


class ApproveRequest(BaseModel):
    approval_id: str


class RejectRequest(BaseModel):
    approval_id: str
    reason: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_action("api", "startup", "started", details={"version": "1.0.0"})
    yield
    logger.log_action("api", "shutdown", "stopped")


app = FastAPI(
    title="AgentOS API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "environment": settings.environment}


@app.post("/api/v1/run")
async def run_workflow(req: RunRequest):
    orchestrator = get_orchestrator()
    result = await orchestrator.run(prompt=req.prompt, project_id=req.project_id)
    return result


@app.get("/api/v1/status/{session_id}")
async def get_status(session_id: str):
    from app.memory.session import get_session_manager
    sm = get_session_manager()
    session = await sm.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.post("/api/v1/hitl/approve")
async def approve_action(req: ApproveRequest):
    hitl = get_hitl_gateway()
    try:
        result = hitl.approve(req.approval_id)
        return {"status": "approved", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/hitl/reject")
async def reject_action(req: RejectRequest):
    hitl = get_hitl_gateway()
    try:
        result = hitl.reject(req.approval_id, req.reason)
        return {"status": "rejected", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/hitl/pending")
async def list_pending():
    hitl = get_hitl_gateway()
    return {"pending": hitl.get_pending()}


@app.get("/api/v1/logs")
async def get_logs(limit: int = 100):
    return {"logs": [], "note": "Full log retrieval requires log aggregation system (e.g., Loki)"}
