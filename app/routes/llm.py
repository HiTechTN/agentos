from typing import Any

from fastapi import APIRouter, Request

from app.utils.api_clients import LLMClient
from app.utils.llm_router import FREE_MODELS, smart_router
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter

router = APIRouter()
metrics = get_metrics()


@router.post("/api/v1/llm/cache/clear")
@limiter.limit("10/minute")  # type: ignore[untyped-decorator]
async def clear_llm_cache(request: Request) -> dict[str, str]:
    LLMClient().clear_cache()
    return {"status": "cache_cleared"}


@router.get("/api/v1/llm/router/status")
async def get_router_status() -> dict[str, Any]:
    """Return current free model usage stats."""
    return await smart_router.get_usage_report()


@router.get("/api/v1/llm/router/models")
async def list_router_models() -> dict[str, Any]:
    """List all free models organized by work type."""
    return {
        wt.value: [{"id": m.id, "name": m.name, "ctx": m.context_window} for m in models]
        for wt, models in FREE_MODELS.items()
    }
