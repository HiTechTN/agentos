"""Intelligence Engine API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.learning.reflection import SelfReflectionEngine
from app.memory.episodic import EpisodicMemory
from app.memory.knowledge import KnowledgeBase
from app.schemas.responses import APIResponse
from app.skills.registry import SkillsRegistry
from app.utils.auth import CurrentUser

router = APIRouter(prefix="/api/v1/intelligence", tags=["Intelligence"])

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


@router.get("/memories/{workspace_id}")
async def get_memories(
    user: CurrentUser,
    workspace_id: str,
    task_type: str | None = None,
    limit: int = 20,
) -> APIResponse[list[dict[str, Any]]]:
    """List episodic memories for a workspace."""
    async with await _get_session() as db:
        memory = EpisodicMemory(db)
        results = await memory.recall_similar(
            task_type=task_type or "",
            workspace_id=workspace_id,
            limit=limit,
            outcome_filter=None,
        )
    return APIResponse(data=results)


@router.get("/memories/{workspace_id}/stats")
async def get_memory_stats(
    user: CurrentUser,
    workspace_id: str,
    days: int = 7,
) -> APIResponse[dict[str, Any]]:
    """Get performance statistics from episodic memory."""
    async with await _get_session() as db:
        memory = EpisodicMemory(db)
        stats = await memory.get_stats(workspace_id, days=days)
    return APIResponse(data=stats)


@router.get("/skills/{workspace_id}")
async def list_skills(
    user: CurrentUser,
    workspace_id: str,
    category: str | None = None,
) -> APIResponse[list[dict[str, Any]]]:
    """List all skills in the registry."""
    async with await _get_session() as db:
        registry = SkillsRegistry(db)
        results = await registry.get_all(workspace_id, category=category)
    return APIResponse(data=results)


@router.get("/knowledge/{workspace_id}")
async def list_knowledge(
    user: CurrentUser,
    workspace_id: str,
    kind: str | None = None,
) -> APIResponse[list[dict[str, Any]]]:
    """List knowledge entries."""
    async with await _get_session() as db:
        kb = KnowledgeBase(db)
        results = await kb.query(workspace_id, keywords=[""], kind=kind, limit=100)
    return APIResponse(data=results)


@router.post("/knowledge/{workspace_id}")
async def add_knowledge(
    workspace_id: str,
    body: dict[str, Any],
    user: CurrentUser,
) -> APIResponse[dict[str, str]]:
    """Manually add a knowledge entry."""
    async with await _get_session() as db:
        kb = KnowledgeBase(db)
        entry_id = await kb.add(
            workspace_id=workspace_id,
            kind=body.get("kind", "domain_fact"),
            title=body["title"],
            content=body["content"],
            source_type=body.get("source_type", "manual"),
            confidence=float(body.get("confidence", 0.7)),
        )
    return APIResponse(data={"id": entry_id})


@router.post("/reflect/{workspace_id}")
async def trigger_reflection(
    user: CurrentUser,
    workspace_id: str,
    force: bool = False,
) -> APIResponse[dict[str, Any] | None]:
    """Manually trigger the self-reflection engine."""
    async with await _get_session() as db:
        engine = SelfReflectionEngine(db_session=db, workspace_id=workspace_id)
        report = await engine.run(force=force)
    return APIResponse(data=report)


@router.get("/reflect/{workspace_id}/reports")
async def list_reflection_reports(
    user: CurrentUser,
    workspace_id: str,
    limit: int = 10,
) -> APIResponse[list[dict[str, Any]]]:
    """List past reflection reports."""
    async with await _get_session() as db:
        rows = await db.execute(
            sa_text("""
                SELECT id, period_start, period_end, tasks_analyzed,
                       new_skills_discovered, knowledge_entries_added,
                       avg_quality_score, summary
                FROM reflection_reports
                WHERE workspace_id = :w
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"w": workspace_id, "limit": limit},
        )
        results = [dict(r._mapping) for r in rows.fetchall()]
    return APIResponse(data=results)


@router.get("/evolutions/{workspace_id}")
async def list_evolutions(
    user: CurrentUser,
    workspace_id: str,
    agent_name: str | None = None,
) -> APIResponse[list[dict[str, Any]]]:
    """List agent evolution history."""
    params: dict[str, Any] = {"w": workspace_id}
    q = "SELECT * FROM agent_evolutions WHERE workspace_id=:w"
    if agent_name:
        q += " AND agent_name=:agent"
        params["agent"] = agent_name
    q += " ORDER BY applied_at DESC LIMIT 50"
    async with await _get_session() as db:
        rows = await db.execute(sa_text(q), params)
        results = [dict(r._mapping) for r in rows.fetchall()]
    return APIResponse(data=results)
