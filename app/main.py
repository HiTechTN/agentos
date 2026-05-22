import json
import os
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config.settings import get_settings
from app.orchestrator import get_orchestrator
from app.utils.auth import get_current_user
from app.utils.hitl_gateway import get_hitl_gateway
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter
from app.utils.request_id import RequestIDMiddleware
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

app.add_middleware(RequestIDMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore


@app.middleware("http")
async def optional_auth_middleware(request: Request, call_next):
    """Optional JWT auth — populates request.state.user if valid token provided."""
    if request.url.path.startswith("/api/v1/") and request.url.path not in (
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
    ):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                credentials = type("HC", (), {"credentials": auth_header[7:]})()
                request.state.user = await get_current_user(credentials)
            except Exception:
                request.state.user = None
        else:
            request.state.user = None
    response = await call_next(request)
    return response


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
@limiter.limit(settings.rate_limit_run)
async def run_workflow(req: RunRequest, request: Request):
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
@limiter.limit("30/minute")
async def approve_action(req: ApproveRequest, request: Request):
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
@limiter.limit("30/minute")
async def reject_action(req: RejectRequest, request: Request):
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
@limiter.limit("30/minute")
async def export_project(req: ProjectExport, request: Request):
    from app.memory.session import get_session_manager

    sm = get_session_manager()
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
@limiter.limit("30/minute")
async def import_project(data: dict, request: Request):
    from app.memory.session import get_session_manager

    sm = get_session_manager()
    if not data.get("project_id"):
        raise HTTPException(status_code=400, detail="project_id required")
    for session in data.get("sessions", []):
        await sm.create(data["project_id"], session.get("workflow_id", ""))
    return {"status": "imported", "project_id": data["project_id"]}


@app.post("/api/v1/scheduler/create")
@limiter.limit("20/minute")
async def create_scheduled_task(task: SchedulerTask, request: Request):
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
@limiter.limit("30/minute")
async def create_workspace(data: dict, request: Request):
    from app.memory.workspace import get_workspace_manager

    wm = get_workspace_manager()
    wid = data.get("workspace_id", str(uuid.uuid4())[:8])
    wm.create_workspace(wid)
    return {"status": "created", "workspace_id": wid}


@app.post("/api/v1/llm/cache/clear")
@limiter.limit("10/minute")
async def clear_llm_cache(request: Request):
    from app.utils.api_clients import LLMClient

    LLMClient().clear_cache()
    return {"status": "cache_cleared"}


# ── Plan Mode ──────────────────────────────────────────────────────────────────


class PlanRequest(BaseModel):
    goal: str
    project_id: str = "default"
    context: dict = {}


@app.post("/api/v1/plan")
@limiter.limit(settings.rate_limit_plan)
async def create_plan(req: PlanRequest, request: Request):
    from app.agents.rules import get_rules
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent

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
@limiter.limit(settings.rate_limit_verify)
async def verify_work(req: VerifyRequest, request: Request):
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent

    sub = SubAgent(BUILTIN_SUB_AGENTS["verifier"])
    context = {
        "task": req.task,
        "code_changes": req.code_changes,
        "test_results": req.test_results,
        "lint_output": req.lint_output,
    }
    result = await sub.run(str(context))
    metrics.inc("verify_run")
    return {"verification": result}


# ── Sub-Agent Execution ────────────────────────────────────────────────────────


class SubAgentRequest(BaseModel):
    name: str
    task: str
    context: dict = {}


@app.post("/api/v1/sub-agent/run")
@limiter.limit("15/minute")
async def run_sub_agent(req: SubAgentRequest, request: Request):
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


# ── Debug Sub-Agent ────────────────────────────────────────────────────────────


class DebugRequest(BaseModel):
    error: str
    context: dict = {}


@app.post("/api/v1/sub-agent/debug")
@limiter.limit("15/minute")
async def debug_error(req: DebugRequest, request: Request):
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent

    sub = SubAgent(BUILTIN_SUB_AGENTS["debugger"])
    result = await sub.run(req.error, req.context)
    return {"debugger": result}


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
@limiter.limit("30/minute")
async def create_kanban_card(project_id: str, card: KanbanCardCreate, request: Request):
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
@limiter.limit("30/minute")
async def move_kanban_card(project_id: str, move: KanbanCardMove, request: Request):
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    if not board.move_card(move.card_id, move.column):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "moved"}


@app.delete("/api/v1/kanban/{project_id}/cards/{card_id}")
@limiter.limit("30/minute")
async def delete_kanban_card(project_id: str, card_id: str, request: Request):
    from app.kanban import get_kanban_board

    board = get_kanban_board(project_id)
    if not board.delete_card(card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "deleted"}


# ── Pulse Dashboard ────────────────────────────────────────────────────────────


@app.get("/api/v1/pulse/{project_id}")
async def get_pulse(project_id: str):
    from app.kanban import get_kanban_board
    from app.orchestrator import get_orchestrator
    from app.pulse import get_pulse

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
@limiter.limit("20/minute")
async def register_mcp_server(server: MCPServerRegister, request: Request):
    from app.mcp.server import get_mcp_registry

    registry = get_mcp_registry()
    registry.register(server.name, server.endpoint, server.api_key)
    return {"status": "registered", "name": server.name}


@app.get("/api/v1/mcp/servers")
async def list_mcp_servers():
    from app.mcp.server import get_mcp_registry

    return {"servers": get_mcp_registry().list_servers()}


@app.post("/api/v1/mcp/{server_name}/call/{tool_name}")
@limiter.limit("30/minute")
async def call_mcp_tool(
    server_name: str, tool_name: str, params: dict = {}, request: Request = None
):
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
@limiter.limit("10/minute")
async def init_rules(request: Request):
    from app.agents.rules import get_rules

    rules = get_rules()
    rules.create_default_agents_md()
    return {"status": "created", "path": "AGENTS.md"}


# ── Git Worktree ───────────────────────────────────────────────────────────────


class WorktreeCreate(BaseModel):
    branch_name: str
    base_branch: str = "main"


@app.post("/api/v1/worktree")
@limiter.limit("10/minute")
async def create_worktree(req: WorktreeCreate, request: Request):
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
@limiter.limit("10/minute")
async def rebase_worktree(branch_name: str, request: Request):
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        await wm.rebase_to_main(branch_name)
        return {"status": "rebased", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/worktree/{branch_name}")
@limiter.limit("10/minute")
async def remove_worktree(branch_name: str, request: Request):
    from app.git_worktree import get_worktree_manager

    wm = get_worktree_manager()
    try:
        await wm.remove_worktree(branch_name)
        return {"status": "removed", "branch": branch_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Deployment Assistant ─────────────────────────────────────────────────────


DEPLOY_HTML_PATH = Path(__file__).resolve().parent / "templates" / "deploy.html"


class DeployConfig(BaseModel):
    host: str
    user: str = "deploy"
    key: str = ""
    openrouter_api_key: str = ""
    jwt_secret: str = ""
    openai_api_key: str = ""
    database_url: str = ""
    redis_url: str = ""


@app.get("/deploy", response_class=HTMLResponse)
async def deploy_assistant():
    if DEPLOY_HTML_PATH.exists():
        return HTMLResponse(DEPLOY_HTML_PATH.read_text())
    return HTMLResponse("<h1>Deploy assistant not found</h1>", status_code=404)


@app.post("/api/v1/deploy/configure")
async def configure_deploy(cfg: DeployConfig, request: Request):
    secrets: dict[str, str] = {}
    if cfg.host:
        secrets["DEPLOY_HOST"] = cfg.host
    if cfg.user:
        secrets["DEPLOY_USER"] = cfg.user
    if cfg.key:
        secrets["DEPLOY_KEY"] = cfg.key
    if cfg.openrouter_api_key:
        secrets["OPENROUTER_API_KEY"] = cfg.openrouter_api_key
    if cfg.openai_api_key:
        secrets["OPENAI_API_KEY"] = cfg.openai_api_key
    if cfg.database_url:
        secrets["DATABASE_URL"] = cfg.database_url
    if cfg.redis_url:
        secrets["REDIS_URL"] = cfg.redis_url

    if cfg.jwt_secret:
        secrets["JWT_SECRET"] = cfg.jwt_secret
    else:
        import secrets as sec

        secrets["JWT_SECRET"] = sec.token_hex(32)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    commands: list[str] = []
    errors: list[str] = []

    if not repo:
        repo = "HiTechTN/agentos"
        for name, value in secrets.items():
            _run = f'gh secret set {name} --repo "{repo}" --body "***"'
            commands.append(_run)
    else:
        for name, value in secrets.items():
            try:
                result = subprocess.run(
                    ["gh", "secret", "set", name, "--repo", repo, "--body", value],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    commands.append(f"✓ {name} configured")
                else:
                    errors.append(f"{name}: {result.stderr.strip()}")
            except Exception as e:
                errors.append(f"{name}: {e}")

    if not errors:
        try:
            subprocess.run(
                ["gh", "workflow", "run", "CI/CD Pipeline", "--repo", repo, "--ref", "main"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            commands.append("✓ Deployment workflow triggered")
        except Exception as e:
            errors.append(f"workflow trigger: {e}")

    return {
        "status": "ok" if not errors else "partial",
        "repo": repo,
        "commands": commands,
        "errors": errors if errors else None,
        "message": "Configuration terminée. Le pipeline CI/CD va démarrer automatiquement."
        if not errors
        else "Certains secrets n'ont pas pu être configurés.",
    }
