import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config.settings import get_settings
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter

router = APIRouter()
settings = get_settings()
metrics = get_metrics()


class SchedulerTask(BaseModel):
    name: str
    cron: str
    prompt: str
    project_id: str = "default"
    channel: str = "console"


class PlanRequest(BaseModel):
    goal: str
    project_id: str = "default"
    context: dict[str, Any] = {}


class VerifyRequest(BaseModel):
    task: str
    code_changes: list[dict[str, Any]] = []
    test_results: str = ""
    lint_output: str = ""


class SubAgentRequest(BaseModel):
    name: str
    task: str
    context: dict[str, Any] = {}


class DebugRequest(BaseModel):
    error: str
    context: dict[str, Any] = {}


@router.post("/api/v1/scheduler/create")
@limiter.limit("20/minute")  # type: ignore[untyped-decorator]
async def create_scheduled_task(task: SchedulerTask, request: Request) -> dict[str, Any]:
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


@router.get("/api/v1/scheduler/tasks")
async def list_scheduled_tasks() -> dict[str, Any]:
    from app.scheduler import get_scheduler

    tasks = get_scheduler().list_tasks()
    return {"tasks": tasks}


@router.get("/api/v1/workspaces")
async def list_workspaces() -> dict[str, Any]:
    from app.memory.workspace import get_workspace_manager

    wm = get_workspace_manager()
    return {"workspaces": wm.list_workspaces()}


@router.post("/api/v1/workspaces")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def create_workspace(data: dict[str, Any], request: Request) -> dict[str, Any]:
    from app.memory.workspace import get_workspace_manager

    wm = get_workspace_manager()
    import uuid

    wid = data.get("workspace_id", str(uuid.uuid4())[:8])
    wm.create_workspace(wid)
    return {"status": "created", "workspace_id": wid}


@router.post("/api/v1/plan")
@limiter.limit(settings.rate_limit_plan)  # type: ignore[untyped-decorator]
async def create_plan(req: PlanRequest, request: Request) -> dict[str, Any]:
    from app.agents.rules import get_rules
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent

    rules = get_rules()
    sub = SubAgent(BUILTIN_SUB_AGENTS["planner"])
    ctx = {"goal": req.goal, "rules": rules.get_all_rules(), "project_context": req.context}
    result = await sub.run(json.dumps(ctx))
    metrics.inc("plan_created")
    return {"plan": result, "project_id": req.project_id}


@router.post("/api/v1/verify")
@limiter.limit(settings.rate_limit_verify)  # type: ignore[untyped-decorator]
async def verify_work(req: VerifyRequest, request: Request) -> dict[str, Any]:
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


@router.post("/api/v1/sub-agent/run")
@limiter.limit("15/minute")  # type: ignore[untyped-decorator]
async def run_sub_agent(req: SubAgentRequest, request: Request) -> dict[str, Any]:
    from app.agents.sub_agent import get_or_create_sub_agent, route_to_sub_agent

    agent_name = req.name
    if agent_name == "auto":
        agent_name = route_to_sub_agent(req.task)
    agent = get_or_create_sub_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Sub-agent '{agent_name}' not found")
    result = await agent.run(req.task, req.context)
    return {"agent": agent_name, "result": result}


@router.get("/api/v1/sub-agents")
async def list_sub_agents() -> dict[str, Any]:
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS

    return {"sub_agents": list(BUILTIN_SUB_AGENTS.keys())}


@router.post("/api/v1/sub-agent/debug")
@limiter.limit("15/minute")  # type: ignore[untyped-decorator]
async def debug_error(req: DebugRequest, request: Request) -> dict[str, Any]:
    from app.agents.sub_agent import BUILTIN_SUB_AGENTS, SubAgent

    sub = SubAgent(BUILTIN_SUB_AGENTS["debugger"])
    result = await sub.run(req.error, req.context)
    return {"debugger": result}


@router.get("/api/v1/rules")
async def get_rules_endpoint() -> dict[str, Any]:
    from app.agents.rules import get_rules

    rules = get_rules()
    return {
        "project_rules": rules.get_project_rules(),
        "global_rules": rules.get_global_rules(),
        "plan_rules": rules.get_plan_rules(),
    }


@router.get("/api/v1/pulse/{project_id}")
async def get_pulse_endpoint(project_id: str) -> dict[str, Any]:
    from app.kanban import get_kanban_board
    from app.orchestrator import get_orchestrator
    from app.pulse import get_pulse

    board = get_kanban_board(project_id)
    pulse = get_pulse()
    orch = get_orchestrator()
    agent_statuses = {name: "idle" for name in orch.agents}
    snapshot = await pulse.snapshot(board.get_all(), agent_statuses)
    return snapshot.to_dict()


@router.get("/api/v1/pulse/{project_id}/timeline")
async def get_pulse_timeline_endpoint(project_id: str, limit: int = 60) -> dict[str, Any]:
    from app.pulse import get_pulse

    return {"timeline": get_pulse().get_timeline(limit)}
