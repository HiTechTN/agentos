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


# ── Plan Mode ──────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    goal: str
    project_id: str = "default"
    context: dict = {}


@app.post("/api/v1/plan")
async def create_plan(req: PlanRequest):
    from app.agents.sub_agent import SubAgent, BUILTIN_SUB_AGENTS
    from app.agents.rules import get_rules
    import json
    rules = get_rules()
    sub = SubAgent(BUILTIN_SUB_AGENTS["planner"])
    ctx = {"goal": req.goal, "rules": rules.get_all_rules(), "project_context": req.context}
    result = await sub.run(json.dumps(ctx))
    metrics.inc("plan_created")
    return {"plan": result, "project_id": req.project_id}


# ── Verify Mode ────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    task: str
    code_changes: list[dict] = []
    test_results: str = ""
    lint_output: str = ""


@app.post("/api/v1/verify")
async def verify_work(req: VerifyRequest):
    from app.agents.sub_agent import SubAgent, BUILTIN_SUB_AGENTS
    sub = SubAgent(BUILTIN_SUB_AGENTS["verifier"])
    context = {"task": req.task, "code_changes": req.code_changes,
               "test_results": req.test_results, "lint_output": req.lint_output}
    result = await sub.run(str(context))
    metrics.inc("verify_run")
    return {"verification": result}


# ── Sub-Agent Execution ────────────────────────────────────────────────────────

class SubAgentRequest(BaseModel):
    name: str
    task: str
    context: dict = {}


@app.post("/api/v1/sub-agent/run")
async def run_sub_agent(req: SubAgentRequest):
    from app.agents.sub_agent import get_or_create_sub_agent, route_to_sub_agent
    agent_name = req.name
    if agent_name == "auto":
        agent_name = route_to_sub_agent(req.task)
    agent = get_or_create_sub_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Sub-agent '{agent_name}' not found")
    result = await agent.run(req.task, req.context)
    return {"agent": agent_name, "result": result}


@app.get("/api/v1/sub-agents")
async def list_sub_agents():
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS
    return {"sub_agents": list(BUILTIN_SUB_AGENTS.keys())}


# ── Kanban Board ───────────────────────────────────────────────────────────────

class KanbanCardCreate(BaseModel):
    title: str
    description: str = ""
    column: str = "backlog"
    task_id: str = ""
    agent: str = ""


class KanbanCardMove(BaseModel):
    card_id: str
    column: str


@app.post("/api/v1/kanban/{project_id}/cards")
async def create_kanban_card(project_id: str, card: KanbanCardCreate):
    from app.kanban import get_kanban_board
    board = get_kanban_board(project_id)
    created = board.add_card(card.title, card.description, card.column, card.task_id, card.agent)
    metrics.inc("kanban_card_created")
    return {"card": created.to_dict()}


@app.get("/api/v1/kanban/{project_id}")
async def get_kanban_board_endpoint(project_id: str):
    from app.kanban import get_kanban_board
    board = get_kanban_board(project_id)
    return {"columns": board.get_all()}


@app.put("/api/v1/kanban/{project_id}/move")
async def move_kanban_card(project_id: str, move: KanbanCardMove):
    from app.kanban import get_kanban_board
    board = get_kanban_board(project_id)
    if not board.move_card(move.card_id, move.column):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "moved"}


@app.delete("/api/v1/kanban/{project_id}/cards/{card_id}")
async def delete_kanban_card(project_id: str, card_id: str):
    from app.kanban import get_kanban_board
    board = get_kanban_board(project_id)
    if not board.delete_card(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "deleted"}


# ── Pulse Dashboard ────────────────────────────────────────────────────────────

@app.get("/api/v1/pulse/{project_id}")
async def get_pulse(project_id: str):
    from app.kanban import get_kanban_board
    from app.pulse import get_pulse
    from app.orchestrator import get_orchestrator
    board = get_kanban_board(project_id)
    pulse = get_pulse()
    orch = get_orchestrator()
    agent_statuses = {name: "idle" for name in orch.agents}
    snapshot = await pulse.snapshot(board.get_all(), agent_statuses)
    return snapshot.to_dict()


@app.get("/api/v1/pulse/{project_id}/timeline")
async def get_pulse_timeline(project_id: str, limit: int = 60):
    from app.pulse import get_pulse
    return {"timeline": get_pulse().get_timeline(limit)}


# ── MCP Integration ────────────────────────────────────────────────────────────

class MCPServerRegister(BaseModel):
    name: str
    endpoint: str
    api_key: str = ""


@app.post("/api/v1/mcp/register")
async def register_mcp_server(server: MCPServerRegister):
    from app.mcp.server import get_mcp_registry
    registry = get_mcp_registry()
    registry.register(server.name, server.endpoint, server.api_key)
    return {"status": "registered", "name": server.name}


@app.get("/api/v1/mcp/servers")
async def list_mcp_servers():
    from app.mcp.server import get_mcp_registry
    return {"servers": get_mcp_registry().list_servers()}


@app.post("/api/v1/mcp/{server_name}/call/{tool_name}")
async def call_mcp_tool(server_name: str, tool_name: str, params: dict = {}):
    from app.mcp.server import get_mcp_registry
    result = await get_mcp_registry().call_tool(server_name, tool_name, params)
    return result


# ── Rules Management ───────────────────────────────────────────────────────────

@app.get("/api/v1/rules")
async def get_rules_endpoint():
    from app.agents.rules import get_rules
    rules = get_rules()
    return {
        "project_rules": rules.get_project_rules(),
        "global_rules": rules.get_global_rules(),
        "plan_rules": rules.get_plan_rules(),
    }


@app.post("/api/v1/rules/init")
async def init_rules():
    from app.agents.rules import get_rules
    rules = get_rules()
    rules.create_default_agents_md()
    return {"status": "created", "path": "AGENTS.md"}


# ── Git Worktree ───────────────────────────────────────────────────────────────

class WorktreeCreate(BaseModel):
    branch_name: str
    base_branch: str = "main"


@app.post("/api/v1/worktree")
async def create_worktree(req: WorktreeCreate):
    from app.git_worktree import get_worktree_manager
    wm = get_worktree_manager()
    try:
        path = await wm.create_worktree(req.branch_name, req.base_branch)
        return {"status": "created", "branch": req.branch_name, "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/worktree")
async def list_worktrees():
    from app.git_worktree import get_worktree_manager
    wm = get_worktree_manager()
    try:
        trees = await wm.list_worktrees()
        return {"worktrees": trees}
    except Exception as e:
        return {"worktrees": [], "error": str(e)}


@app.post("/api/v1/worktree/rebase")
async def rebase_worktree(branch_name: str):
    from app.git_worktree import get_worktree_manager
    wm = get_worktree_manager()
    try:
        await wm.rebase_to_main(branch_name)
        return {"status": "rebased", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/worktree/{branch_name}")
async def remove_worktree(branch_name: str):
    from app.git_worktree import get_worktree_manager
    wm = get_worktree_manager()
    try:
        await wm.remove_worktree(branch_name)
        return {"status": "removed", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
