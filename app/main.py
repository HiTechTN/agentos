import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response

from app.config.settings import get_settings
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.content import router as content_router
from app.routes.kanban import router as kanban_router
from app.routes.llm import router as llm_router
from app.routes.management import router as management_router
from app.routes.mcp import router as mcp_router
from app.routes.workflow import router as workflow_router
from app.routes.worktree import router as worktree_router
from app.utils.auth import create_access_token, get_current_user
from app.utils.llm_cache import llm_cache
from app.utils.llm_router import smart_router
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter
from app.utils.request_id import RequestIDMiddleware

settings = get_settings()
logger = get_logger("api")
metrics = get_metrics()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    logger.log_action("api", "startup", "started", details={"version": settings.version})
    app.state.limiter = limiter
    await llm_cache.connect()
    from app.scheduler import get_scheduler

    if settings.scheduler_enabled:
        scheduler = get_scheduler()
        await scheduler.start()
    yield
    await llm_cache.close()
    await smart_router.close()
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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def optional_auth_middleware(request: Request, call_next: Any) -> Response:
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
    response: Response = await call_next(request)
    return response


@app.post("/api/v1/auth/token")
async def get_token(sub: str = "demo", workspace: str = "default") -> dict[str, str]:
    token = create_access_token(sub=sub, workspace=workspace)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health")
async def health() -> dict[str, str]:
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

        r = aioredis.from_url(settings.resolved_redis_url)  # type: ignore[no-untyped-call]
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
async def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(metrics.render_prometheus())


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.log_action("ws", "client_connected", "completed")

    async def send_log(record: dict[str, Any]) -> None:
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


# ── Guide & Deployment Pages ────────────────────────────────────────────────


GUIDE_HTML_PATH = Path(__file__).resolve().parent / "templates" / "guide.html"
DEPLOY_HTML_PATH = Path(__file__).resolve().parent / "templates" / "deploy.html"


@app.get("/guide", response_class=HTMLResponse)
async def guide_page() -> HTMLResponse:
    if GUIDE_HTML_PATH.exists():
        return HTMLResponse(GUIDE_HTML_PATH.read_text())
    return HTMLResponse("<h1>Guide not found</h1>", status_code=404)


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
async def deploy_assistant() -> HTMLResponse:
    if DEPLOY_HTML_PATH.exists():
        return HTMLResponse(DEPLOY_HTML_PATH.read_text())
    return HTMLResponse("<h1>Deploy assistant not found</h1>", status_code=404)


@app.post("/api/v1/deploy/configure")
async def configure_deploy(cfg: DeployConfig, request: Request) -> dict[str, Any]:
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


# ── Route Modules ──────────────────────────────────────────────────────────

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(llm_router)
app.include_router(content_router)
app.include_router(management_router)
app.include_router(kanban_router)
app.include_router(mcp_router)
app.include_router(worktree_router)
