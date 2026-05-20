import json
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.config.settings import get_settings
from app.orchestrator import get_orchestrator
from app.utils.hitl_gateway import get_hitl_gateway
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.telemetry import get_telemetry

settings = get_settings()
logger = get_logger("api")
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


class ProjectExport(BaseModel):
    project_id: str


class SchedulerTask(BaseModel):
    name: str
    cron: str
    prompt: str
    project_id: str = "default"
    channel: str = "console"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.log_action("api", "startup", "started", details={"version": settings.version})
    from app.scheduler import get_scheduler
    if settings.scheduler_enabled:
        scheduler = get_scheduler()
        await scheduler.start()
    yield
    logger.log_action("api", "shutdown", "stopped")


app = FastAPI(
    title="AgentOS API",
    version=settings.version,
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
    import asyncpg
    statuses = {"api": "ok", "version": settings.version}
    try:
        conn = await asyncpg.connect(settings.resolved_database_url.replace("+asyncpg", ""))
        await conn.execute("SELECT 1")
        await conn.close()
        statuses["database"] = "ok"
    except Exception:
        statuses["database"] = "error"
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.resolved_redis_url)
        await r.ping()
        await r.aclose()
        statuses["redis"] = "ok"
    except Exception:
        statuses["redis"] = "error"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                statuses["ollama"] = "ok"
            else:
                statuses["ollama"] = "error"
    except Exception:
        statuses["ollama"] = "error"
    return statuses


@app.get("/metrics")
async def metrics_endpoint():
    return PlainTextResponse(metrics.render_prometheus())


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    logger.log_action("ws", "client_connected", "completed")

    async def send_log(record: dict):
        try:
            await websocket.send_json(record)
        except Exception:
            pass

    from app.utils.logging import get_broadcaster
    broadcaster = get_broadcaster()
    broadcaster.subscribe(send_log)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unsubscribe(send_log)


@app.post("/api/v1/run")
async def run_workflow(req: RunRequest):
    start = time.time()
    orchestrator = get_orchestrator()
    result = await orchestrator.run(prompt=req.prompt, project_id=req.project_id)
    duration = time.time() - start
    metrics.timing("workflow_duration", duration)
    metrics.inc("workflow_runs")
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
        metrics.inc("hitl_approved")
        from app.utils.notifications import get_notifications
        await get_notifications().notify_all(
            "HITL Approved", f"Approval {req.approval_id[:8]} was approved"
        )
        return {"status": "approved", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/hitl/reject")
async def reject_action(req: RejectRequest):
    hitl = get_hitl_gateway()
    try:
        result = hitl.reject(req.approval_id, req.reason)
        metrics.inc("hitl_rejected")
        return {"status": "rejected", "details": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/hitl/pending")
async def list_pending():
    hitl = get_hitl_gateway()
    return {"pending": hitl.get_pending()}


@app.get("/api/v1/logs")
async def get_logs(limit: int = 100, trace_id: str = ""):
    telemetry = get_telemetry()
    spans = telemetry.get_spans(trace_id) if trace_id else telemetry.get_spans()
    return {"logs": spans[-limit:]}


@app.post("/api/v1/project/export")
async def export_project(req: ProjectExport):
    from app.memory.session import get_session_manager
    from app.memory.vector_store import get_vector_store
    sm = get_session_manager()
    vs = get_vector_store()
    export_data = {
        "project_id": req.project_id,
        "version": settings.version,
        "exported_at": time.time(),
        "sessions": [],
        "embeddings": [],
    }
    try:
        sessions = await sm.list_by_project(req.project_id)
        export_data["sessions"] = sessions
    except Exception:
        pass
    return export_data


@app.post("/api/v1/project/import")
async def import_project(data: dict):
    from app.memory.session import get_session_manager
    sm = get_session_manager()
    if not data.get("project_id"):
        raise HTTPException(status_code=400, detail="project_id required")
    for session in data.get("sessions", []):
        await sm.create(data["project_id"], session.get("workflow_id", ""))
    return {"status": "imported", "project_id": data["project_id"]}


@app.post("/api/v1/scheduler/create")
async def create_scheduled_task(task: SchedulerTask):
    from app.scheduler import get_scheduler
    scheduler = get_scheduler()
    task_id = await scheduler.add_task(
        name=task.name,
        cron=task.cron,
        prompt=task.prompt,
        project_id=task.project_id,
        channel=task.channel,
    )
    return {"status": "created", "task_id": task_id}


@app.get("/api/v1/scheduler/tasks")
async def list_scheduled_tasks():
    from app.scheduler import get_scheduler
    tasks = get_scheduler().list_tasks()
    return {"tasks": tasks}


@app.get("/api/v1/workspaces")
async def list_workspaces():
    from app.memory.workspace import get_workspace_manager
    wm = get_workspace_manager()
    return {"workspaces": wm.list_workspaces()}


@app.post("/api/v1/workspaces")
async def create_workspace(data: dict):
    from app.memory.workspace import get_workspace_manager
    wm = get_workspace_manager()
    wid = data.get("workspace_id", str(uuid.uuid4())[:8])
    wm.create_workspace(wid)
    return {"status": "created", "workspace_id": wid}


@app.post("/api/v1/llm/cache/clear")
async def clear_llm_cache():
    from app.utils.api_clients import LLMClient
    LLMClient().clear_cache()
    return {"status": "cache_cleared"}
