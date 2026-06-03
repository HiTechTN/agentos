"""Episodic memory — records every task execution for future learning.

AgentOS learns from experience by storing what happened, how well it
went, and what patterns led to success or failure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskOutcome:
    """Result of a completed agent task, ready to be memorised."""

    workspace_id: str
    task_type: str
    prompt_summary: str
    outcome: str  # "success" | "failure" | "partial"
    quality_score: float | None = None  # 0.0-1.0, None if unscored
    duration_ms: int | None = None
    agent_used: str = ""
    model_used: str = ""
    work_type: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    strategy_used: str = ""
    what_worked: str = ""
    what_failed: str = ""
    context_tags: list[str] = field(default_factory=list)
    session_id: str | None = None


class EpisodicMemory:
    """Persistent store of task execution memories.

    Every completed task creates a memory record. Over time, the system
    can query "what similar tasks have I done? what worked?" to guide
    future decisions without re-learning from scratch.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    async def record(self, outcome: TaskOutcome) -> str:
        """Persist a task outcome as an episodic memory.

        Returns:
            The UUID of the created memory record.
        """
        memory_id = str(uuid.uuid4())
        await self._db.execute(
            sa.text("""
                INSERT INTO episodic_memories (
                    id, workspace_id, session_id, task_type, prompt_summary,
                    outcome, quality_score, duration_ms, agent_used,
                    model_used, work_type, input_tokens, output_tokens,
                    strategy_used, what_worked, what_failed, context_tags
                ) VALUES (
                    :id, :workspace_id, :session_id, :task_type,
                    :prompt_summary, :outcome, :quality_score, :duration_ms,
                    :agent_used, :model_used, :work_type, :input_tokens,
                    :output_tokens, :strategy_used, :what_worked,
                    :what_failed, CAST(:context_tags AS jsonb)
                )
            """),
            {
                "id": memory_id,
                "workspace_id": outcome.workspace_id,
                "session_id": outcome.session_id,
                "task_type": outcome.task_type,
                "prompt_summary": outcome.prompt_summary[:500],
                "outcome": outcome.outcome,
                "quality_score": outcome.quality_score,
                "duration_ms": outcome.duration_ms,
                "agent_used": outcome.agent_used,
                "model_used": outcome.model_used,
                "work_type": outcome.work_type,
                "input_tokens": outcome.input_tokens,
                "output_tokens": outcome.output_tokens,
                "strategy_used": outcome.strategy_used,
                "what_worked": outcome.what_worked,
                "what_failed": outcome.what_failed,
                "context_tags": str(outcome.context_tags),
            },
        )
        await self._db.commit()
        logger.log_action(
            agent_id="memory",
            action="memory_recorded",
            status="completed",
            details={
                "memory_id": memory_id,
                "task_type": outcome.task_type,
                "outcome": outcome.outcome,
            },
        )
        return memory_id

    async def recall_similar(
        self,
        task_type: str,
        workspace_id: str,
        limit: int = 5,
        outcome_filter: str | None = "success",
    ) -> list[dict[str, Any]]:
        """Recall past experiences similar to the current task.

        Args:
            task_type: Type of task to match.
            workspace_id: Workspace scope.
            limit: Max memories to return.
            outcome_filter: Filter by outcome ("success", "failure", None).

        Returns:
            List of memory records ordered by quality_score desc.
        """
        params: dict[str, Any] = {
            "workspace_id": workspace_id,
            "limit": limit,
        }
        conditions = ["workspace_id = :workspace_id"]
        if task_type:
            conditions.append("task_type = :task_type")
            params["task_type"] = task_type
        if outcome_filter:
            conditions.append("outcome = :outcome")
            params["outcome"] = outcome_filter

        _parts = [
            "SELECT id, task_type, prompt_summary, outcome, quality_score, "
            "strategy_used, what_worked, what_failed, model_used, work_type, created_at",
            "FROM episodic_memories",
            "WHERE " + " AND ".join(conditions),
            "ORDER BY quality_score DESC NULLS LAST, created_at DESC",
            "LIMIT :limit",
        ]
        query = " ".join(_parts)  # nosec
        rows = await self._db.execute(sa.text(query), params)
        return [dict(row._mapping) for row in rows.fetchall()]

    async def get_best_strategy(self, task_type: str, workspace_id: str) -> str | None:
        """Return the strategy that achieved the highest quality for this task type."""
        memories = await self.recall_similar(
            task_type, workspace_id, limit=3, outcome_filter="success"
        )
        if not memories:
            return None
        best = max(memories, key=lambda m: m.get("quality_score") or 0.0)
        return best.get("strategy_used")

    async def get_stats(self, workspace_id: str, days: int = 7) -> dict[str, Any]:
        """Return task performance statistics for the last N days."""
        result = await self._db.execute(
            sa.text("""
                SELECT
                    task_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) as successes,
                    AVG(quality_score) as avg_quality,
                    AVG(duration_ms) as avg_duration_ms
                FROM episodic_memories
                WHERE workspace_id = :workspace_id
                  AND created_at > NOW() - make_interval(days => :days)
                GROUP BY task_type
                ORDER BY total DESC
            """),
            {"workspace_id": workspace_id, "days": days},
        )
        return {
            "days": days,
            "by_task_type": [dict(r._mapping) for r in result.fetchall()],
        }
