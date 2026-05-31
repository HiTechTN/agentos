from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config.settings import get_settings
from app.utils.auth import AdminUser
from app.utils.llm_models import FREE_MODELS, WorkType
from app.utils.llm_router import smart_router
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/api/v1/admin")
logger = get_logger("admin")
settings = get_settings()
metrics = get_metrics()

MASKED = "***MASKED***"
SENSITIVE_KEYS = {
    "postgres_password",
    "redis_password",
    "jwt_secret",
    "nextauth_secret",
    "google_client_secret",
    "github_client_secret",
    "openrouter_api_key",
    "stripe_api_key",
    "stripe_webhook_secret",
    "github_token",
    "replicate_api_token",
    "slack_webhook_url",
    "discord_webhook_url",
    "s3_access_key",
    "s3_secret_key",
    "database_url",
    "redis_url",
}

ENV_FILE = Path(".env")


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, str]


class TestModelRequest(BaseModel):
    model_id: str
    prompt: str = "Say hello in one word."


class TestModelResponse(BaseModel):
    success: bool
    latency_ms: float | None = None
    response: str | None = None
    error: str | None = None


class SelectModelRequest(BaseModel):
    work_type: str
    model_id: str


def _mask_settings(raw: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for k, v in raw.items():
        if k in SENSITIVE_KEYS and v:
            if isinstance(v, str) and len(v) > 4:
                masked[k] = v[:2] + "****" + v[-2:]
            else:
                masked[k] = MASKED
        else:
            masked[k] = v
    return masked


@router.get("/settings")
async def get_settings_endpoint(user: AdminUser) -> dict[str, Any]:
    raw = settings.model_dump()
    return {"settings": _mask_settings(raw)}


@router.put("/settings")
@limiter.limit("10/minute")
async def update_settings(
    body: SettingsUpdateRequest, request: Request, user: AdminUser
) -> dict[str, Any]:
    if not ENV_FILE.exists():
        raise HTTPException(status_code=500, detail=".env file not found")

    lines = ENV_FILE.read_text().splitlines()
    existing: dict[str, str] = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            existing[k.strip()] = v.strip().strip("\"'")

    for key, value in body.updates.items():
        existing[key] = value

    new_lines: list[str] = []
    written = set()
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in body.updates:
                new_lines.append(f"{k}={existing[k]}")
                written.add(k)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    for key, value in existing.items():
        if key not in written:
            new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n")

    import importlib

    importlib.reload(__import__("app.config.settings", fromlist=["Settings"]))

    metrics.inc("admin.settings.updated")
    logger.log_action("admin", "settings_update", "Settings updated by admin")

    return {"status": "updated", "keys": list(body.updates.keys())}


@router.get("/services")
async def check_services(user: AdminUser) -> dict[str, Any]:
    results: dict[str, Any] = {}

    try:
        from app.memory.session import get_session_manager

        sm = get_session_manager()
        await sm._init_db()
        async with sm._session_factory() as session:  # type: ignore[misc]
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        results["database"] = "ok"
    except Exception as e:
        results["database"] = f"error: {e}"

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.resolved_redis_url, socket_connect_timeout=3)  # type: ignore[no-untyped-call]
        await r.ping()
        await r.aclose()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"error: {e}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                results["ollama"] = {"status": "ok", "models": models}
            else:
                results["ollama"] = {"status": "error", "detail": resp.text[:200]}
    except Exception as e:
        results["ollama"] = {"status": "error", "detail": str(e)}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.openrouter_base_url}/models",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                results["openrouter"] = {
                    "status": "ok",
                    "models_count": len(data.get("data", [])),
                }
            else:
                results["openrouter"] = {"status": "error", "detail": resp.text[:200]}
    except Exception as e:
        results["openrouter"] = {"status": "error", "detail": str(e)}

    metrics.inc("admin.services.checked")
    return {"services": results}


@router.get("/llm/providers")
async def list_llm_providers(user: AdminUser) -> dict[str, Any]:
    models_by_type: dict[str, list[dict[str, Any]]] = {}
    for wt in WorkType:
        type_models = FREE_MODELS.get(wt, FREE_MODELS[WorkType.GENERAL])
        models_by_type[wt.value] = [
            {
                "id": m.id,
                "name": m.name,
                "context_window": m.context_window,
                "supports_tools": m.supports_tools,
                "supports_vision": m.supports_vision,
                "req_per_min": m.req_per_min,
                "req_per_day": m.req_per_day,
            }
            for m in type_models[:6]
        ]

    all_providers = list(
        dict.fromkeys(
            p.split("/")[0] if "/" in p else "openai"
            for models in FREE_MODELS.values()
            for m in models
            for p in [m.id]
        )
    )

    usage = smart_router.get_usage_report()

    return {
        "providers": all_providers,
        "models_by_type": models_by_type,
        "current_selections": {
            wt.value: settings.model_for_code
            if wt == WorkType.CODE_GEN
            else settings.model_for_content
            if wt == WorkType.CONTENT
            else settings.model_for_analysis
            if wt in (WorkType.REASONING, WorkType.DEBUG)
            else settings.model_for_commerce
            if wt == WorkType.FAST
            else settings.model_for_default
            for wt in WorkType
        },
        "usage": usage,
    }


@router.post("/llm/test", response_model=TestModelResponse)
@limiter.limit("30/minute")
async def test_llm_model(
    body: TestModelRequest, request: Request, user: AdminUser
) -> TestModelResponse:
    import time

    from app.utils.api_clients import llm_complete

    start = time.monotonic()
    try:
        result = await llm_complete(
            prompt=body.prompt,
            agent_name="admin-test",
            work_type=WorkType.GENERAL,
        )
        elapsed = (time.monotonic() - start) * 1000
        return TestModelResponse(
            success=True,
            latency_ms=round(elapsed, 1),
            response=str(result.get("content", ""))[:500],
        )
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        return TestModelResponse(
            success=False,
            latency_ms=round(elapsed, 1),
            error=str(e),
        )


@router.put("/llm/select-model")
@limiter.limit("20/minute")
async def select_llm_model(
    body: SelectModelRequest, request: Request, user: AdminUser
) -> dict[str, Any]:
    valid_types = {wt.value for wt in WorkType}
    if body.work_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid work_type. Valid: {sorted(valid_types)}",
        )

    model_exists = any(m.id == body.model_id for models in FREE_MODELS.values() for m in models)
    if not model_exists:
        raise HTTPException(status_code=400, detail=f"Model '{body.model_id}' not found in catalog")

    settings_map = {
        "code_gen": "model_for_code",
        "code_agent": "model_for_default",
        "reasoning": "model_for_analysis",
        "content": "model_for_content",
        "fast": "model_for_commerce",
        "multimodal": "model_for_default",
        "debug": "model_for_analysis",
        "general": "model_for_default",
    }

    config_key = settings_map.get(body.work_type.lower())
    if not config_key:
        config_key = "model_for_default"

    if not ENV_FILE.exists():
        raise HTTPException(status_code=500, detail=".env file not found")

    lines = ENV_FILE.read_text().splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{config_key}=") and not line.strip().startswith("#"):
            lines[i] = f"{config_key}={body.model_id}"
            updated = True
            break

    if not updated:
        lines.append(f"{config_key}={body.model_id}")

    ENV_FILE.write_text("\n".join(lines) + "\n")

    import importlib

    importlib.reload(__import__("app.config.settings", fromlist=["Settings"]))

    metrics.inc("admin.llm.model_selected")
    logger.log_action("admin", "select_model", f"Model {body.model_id} for {body.work_type}")

    return {"status": "updated", "key": config_key, "value": body.model_id}


@router.get("/users")
async def list_users(user: AdminUser) -> dict[str, Any]:
    from sqlalchemy import text

    from app.routes.auth import _get_session

    async with await _get_session() as session:
        rows = await session.execute(
            text(
                "SELECT id, email, name, avatar_url, role, email_verified, created_at"
                " FROM users ORDER BY created_at DESC"
            )
        )
        users_list = [
            {
                "id": str(r.id),
                "email": r.email,
                "name": r.name,
                "avatar_url": r.avatar_url,
                "role": r.role,
                "email_verified": r.email_verified,
                "created_at": (
                    r.created_at.isoformat()
                    if hasattr(r.created_at, "isoformat")
                    else str(r.created_at)
                ),
            }
            for r in rows.fetchall()
        ]

    return {"users": users_list, "total": len(users_list)}
