import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config.settings import get_settings
from app.utils.rate_limit import limiter

router = APIRouter()
settings = get_settings()


class ProjectExport(BaseModel):
    project_id: str


@router.post("/api/v1/project/export")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def export_project(req: ProjectExport, request: Request) -> dict[str, Any]:
    from app.memory.session import get_session_manager

    sm = get_session_manager()
    export_data = {
        "project_id": req.project_id,
        "version": settings.version,
        "exported_at": time.time(),
        "sessions": [],
        "embeddings": [],
    }
    sessions: list[dict[str, Any]] = []
    try:
        session_data = await sm.get(req.project_id)
        if session_data:
            sessions = [session_data]
    except Exception:
        pass
    export_data["sessions"] = sessions
    return export_data


@router.post("/api/v1/project/import")
@limiter.limit("30/minute")  # type: ignore[untyped-decorator]
async def import_project(data: dict[str, Any], request: Request) -> dict[str, Any]:
    from app.memory.session import get_session_manager

    sm = get_session_manager()
    if not data.get("project_id"):
        raise HTTPException(status_code=400, detail="project_id required")
    for session in data.get("sessions", []):
        await sm.create(data["project_id"], session.get("workflow_id", ""))
    return {"status": "imported", "project_id": data["project_id"]}
