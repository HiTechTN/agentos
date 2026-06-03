"""Model Discovery & Rotation API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.schemas.responses import APIResponse
from app.utils.auth import AdminUser, CurrentUser
from app.utils.llm_router import smart_router

router = APIRouter()

_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def _get_session() -> AsyncSession:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.resolved_database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    assert _session_factory is not None
    return _session_factory()


@router.get("/api/v1/llm/models/catalog")
async def get_model_catalog(
    user: CurrentUser,
    work_type: str | None = None,
    active_only: bool = True,
) -> APIResponse[list[dict[str, Any]]]:
    """Return the full model catalog with performance stats."""
    from app.utils.rotation_engine import RotationEngine

    async with await _get_session() as db:
        engine = RotationEngine(db_session=db)
        models = await engine.get_catalog(work_type=work_type, active_only=active_only)
    return APIResponse(data=models)


@router.post("/api/v1/llm/models/sync")
async def sync_models(
    user: AdminUser,
    run_benchmark: bool = False,
) -> APIResponse[dict[str, Any]]:
    """Manually trigger model discovery sync."""
    from app.utils.model_discovery import ModelDiscoveryEngine

    async with await _get_session() as db:
        disc = ModelDiscoveryEngine(db_session=db, run_benchmark=run_benchmark)
        snapshot = await disc.sync(source="manual_api")
    await smart_router._reload_dynamic_models()
    return APIResponse(
        data={
            "models_found": snapshot.models_found,
            "models_new": snapshot.models_new,
            "models_removed": snapshot.models_removed,
            "models_updated": snapshot.models_updated,
            "duration_ms": snapshot.duration_ms,
            "error": snapshot.error,
        }
    )


@router.get("/api/v1/llm/models/health")
async def get_model_health(
    user: CurrentUser,
) -> APIResponse[list[dict[str, Any]]]:
    """Quick health check of the top model per WorkType."""
    from app.utils.model_discovery import ModelBenchmark
    from app.utils.rotation_engine import RotationEngine

    work_types = [
        "code_gen",
        "code_agent",
        "reasoning",
        "content",
        "fast",
        "debug",
        "multimodal",
        "general",
    ]
    results: list[dict[str, Any]] = []
    bench = ModelBenchmark()

    async with await _get_session() as db:
        engine = RotationEngine(db_session=db)
        for wt in work_types:
            model = await engine.select_model(wt)
            if not model:
                results.append(
                    {"work_type": wt, "model_id": None, "status": "no_model", "latency_ms": None}
                )
                continue
            ok, latency = await bench.test(model["id"])
            results.append(
                {
                    "work_type": wt,
                    "model_id": model["id"],
                    "status": "ok" if ok else "fail",
                    "latency_ms": round(latency, 1) if ok else None,
                }
            )

    await bench.close()
    return APIResponse(data=results)


@router.post("/api/v1/llm/models/{model_id:path}/disable")
async def disable_model(
    user: AdminUser,
    model_id: str,
) -> APIResponse[dict[str, str]]:
    """Manually disable a specific model."""
    from app.utils.rotation_engine import RotationEngine

    async with await _get_session() as db:
        engine = RotationEngine(db_session=db)
        await engine.disable_model(model_id, reason="manual_api")
    return APIResponse(data={"status": "disabled", "model_id": model_id})


@router.get("/api/v1/llm/models/rotation/status")
async def get_rotation_status(
    user: CurrentUser,
    limit: int = 50,
) -> APIResponse[list[dict[str, Any]]]:
    """Return recent rotation log entries."""
    from app.utils.rotation_engine import RotationEngine

    async with await _get_session() as db:
        engine = RotationEngine(db_session=db)
        stats = await engine.get_rotation_stats(limit=limit)
    return APIResponse(data=stats)
