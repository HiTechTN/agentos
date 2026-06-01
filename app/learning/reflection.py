"""Self-Reflection Engine — AgentOS analyzes its own performance.

After every N tasks (or on schedule), the engine:
  1. Reviews recent episodic memories
  2. Identifies patterns of success and failure
  3. Extracts new skills from successful patterns
  4. Adds domain knowledge from discoveries
  5. Generates recommendations for agent strategy updates
  6. Stores a reflection report
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.episodic import EpisodicMemory
from app.memory.knowledge import KnowledgeBase
from app.skills.registry import SkillsRegistry
from app.utils.llm_router import WorkType, smart_router
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REFLECTION_SYSTEM = """You are the Self-Reflection Engine of AgentOS.
You analyze agent performance data and generate actionable insights.

Given a summary of recent task executions, return ONLY a JSON object:
{
  "top_patterns": [
    {"pattern": "description", "frequency": 3, "outcome": "success|failure"}
  ],
  "recommendations": [
    {
      "target": "agent_name or global",
      "type": "prompt_update|strategy_shift|model_preference|new_skill",
      "description": "What to change and why",
      "priority": "high|medium|low"
    }
  ],
  "new_knowledge": [
    {
      "kind": "best_practice|constraint|api_pattern|failure_mode",
      "title": "Short title",
      "content": "Detailed content, max 300 chars"
    }
  ],
  "overall_health": "excellent|good|degraded|critical",
  "summary": "2-3 sentence overall assessment"
}
Return raw JSON only."""


class SelfReflectionEngine:
    """Periodic self-analysis engine that improves AgentOS over time.

    Triggered:
    - After every 10 task completions (task-based trigger)
    - On a daily schedule (time-based trigger)
    - Manually via POST /api/v1/intelligence/reflect

    Effect:
    - Creates new skills from successful patterns
    - Adds knowledge entries from discoveries
    - Records an evolution event if strategy should change
    - Generates a human-readable reflection report
    """

    TRIGGER_EVERY_N_TASKS = 10
    REFLECTION_WINDOW_HOURS = 24

    def __init__(
        self,
        db_session: AsyncSession,
        workspace_id: str,
    ) -> None:
        self._db = db_session
        self.workspace_id = workspace_id
        self.episodic = EpisodicMemory(db_session)
        self.skills = SkillsRegistry(db_session)
        self.knowledge = KnowledgeBase(db_session)

    async def should_reflect(self) -> bool:
        """Return True if enough new tasks have accumulated since last reflection."""
        result = await self._db.execute(
            sa.text("""
                SELECT COUNT(*) as c FROM episodic_memories
                WHERE workspace_id = :w
                  AND created_at > (
                    SELECT COALESCE(MAX(created_at), '2000-01-01')
                    FROM reflection_reports
                    WHERE workspace_id = :w
                  )
            """),
            {"w": self.workspace_id},
        )
        row = result.fetchone()
        count = row.c if row else 0
        return int(count) >= self.TRIGGER_EVERY_N_TASKS

    async def run(self, force: bool = False) -> dict[str, Any] | None:
        """Execute the self-reflection cycle.

        Args:
            force: Skip the should_reflect check.

        Returns:
            Reflection report dict, or None if skipped.
        """
        if not force and not await self.should_reflect():
            return None

        logger.info("reflection_started", workspace=self.workspace_id)
        period_start = datetime.now(timezone.utc) - timedelta(
            hours=self.REFLECTION_WINDOW_HOURS
        )
        period_end = datetime.now(timezone.utc)

        # 1. Collect recent memories
        memories = await self._collect_recent_memories(period_start)
        if not memories:
            return None

        # 2. Generate LLM reflection
        summary_text = self._summarize_memories(memories)
        reflection = await self._llm_reflect(summary_text)

        # 3. Apply recommendations
        new_skills = 0
        new_knowledge = 0

        for knowledge_item in reflection.get("new_knowledge", []):
            await self.knowledge.add(
                workspace_id=self.workspace_id,
                kind=knowledge_item.get("kind", "domain_fact"),
                title=knowledge_item["title"],
                content=knowledge_item["content"],
                source_type="self_reflection",
                confidence=0.65,
            )
            new_knowledge += 1

        # 4. Extract skills from top success patterns
        success_memories = [
            m for m in memories if m["outcome"] == "success"
                                   and m.get("quality_score", 0) >= 0.7
        ]
        for mem in success_memories[:3]:
            skill_id = await self.skills.extract_from_outcome(
                workspace_id=self.workspace_id,
                task_description=mem["prompt_summary"],
                successful_approach=mem.get("strategy_used", ""),
                task_type=mem["task_type"],
                memory_id=str(mem["id"]),
            )
            if skill_id:
                new_skills += 1

        # 5. Record agent evolutions for high-priority recommendations
        for rec in reflection.get("recommendations", []):
            if rec.get("priority") == "high":
                await self._record_evolution(rec)

        # 6. Save reflection report
        report_id = str(uuid.uuid4())
        avg_quality = (
            sum(m.get("quality_score", 0.5) or 0.5 for m in memories)
            / len(memories)
        )
        await self._db.execute(
            sa.text("""
                INSERT INTO reflection_reports (
                    id, workspace_id, period_start, period_end,
                    tasks_analyzed, new_skills_discovered,
                    knowledge_entries_added, avg_quality_score,
                    top_patterns, recommendations, model_performance
                ) VALUES (
                    :id, :workspace_id, :period_start, :period_end,
                    :tasks_analyzed, :new_skills, :new_knowledge,
                    :avg_quality, :top_patterns::jsonb,
                    :recommendations::jsonb, :model_performance::jsonb
                )
            """),
            {
                "id": report_id,
                "workspace_id": self.workspace_id,
                "period_start": period_start,
                "period_end": period_end,
                "tasks_analyzed": len(memories),
                "new_skills": new_skills,
                "new_knowledge": new_knowledge,
                "avg_quality": avg_quality,
                "top_patterns": str(reflection.get("top_patterns", [])),
                "recommendations": str(reflection.get("recommendations", [])),
                "model_performance": "{}",
            },
        )
        await self._db.commit()

        report = {
            "report_id": report_id,
            "tasks_analyzed": len(memories),
            "new_skills_discovered": new_skills,
            "knowledge_entries_added": new_knowledge,
            "avg_quality_score": round(avg_quality, 3),
            "overall_health": reflection.get("overall_health", "unknown"),
            "summary": reflection.get("summary", ""),
            "recommendations": reflection.get("recommendations", []),
        }
        logger.info("reflection_completed", **{
            k: v for k, v in report.items()
            if k in ("tasks_analyzed", "new_skills_discovered",
                     "overall_health")
        })
        return report

    async def _collect_recent_memories(
        self, since: datetime
    ) -> list[dict[str, Any]]:
        rows = await self._db.execute(
            sa.text("""
                SELECT id, task_type, prompt_summary, outcome, quality_score,
                       strategy_used, what_worked, what_failed,
                       model_used, work_type, duration_ms
                FROM episodic_memories
                WHERE workspace_id = :w AND created_at >= :since
                ORDER BY created_at DESC
                LIMIT 100
            """),
            {"w": self.workspace_id, "since": since},
        )
        return [dict(r._mapping) for r in rows.fetchall()]

    def _summarize_memories(self, memories: list[dict[str, Any]]) -> str:
        total = len(memories)
        successes = sum(1 for m in memories if m["outcome"] == "success")
        avg_q = (
            sum(m.get("quality_score") or 0.5 for m in memories) / total
        )
        by_type: dict[str, int] = {}
        for m in memories:
            by_type[m["task_type"]] = by_type.get(m["task_type"], 0) + 1

        samples = memories[:5]
        sample_text = "\n".join(
            f"- [{m['outcome']}][q={m.get('quality_score', '?')}] "
            f"{m['task_type']}: {m['prompt_summary'][:100]}"
            for m in samples
        )
        return (
            f"Period summary: {total} tasks, {successes} successes, "
            f"avg_quality={avg_q:.2f}\n"
            f"Task types: {by_type}\n\n"
            f"Sample executions:\n{sample_text}"
        )

    async def _llm_reflect(self, summary: str) -> dict[str, Any]:
        import json
        response = await smart_router.complete(
            prompt=summary,
            system=_REFLECTION_SYSTEM,
            work_type=WorkType.REASONING,
        )
        content = response["choices"][0]["message"]["content"]
        try:
            return dict(json.loads(content))
        except (ValueError, KeyError):
            return {"top_patterns": [], "recommendations": [],
                    "new_knowledge": [], "overall_health": "unknown",
                    "summary": "Reflection parsing failed."}

    async def _record_evolution(self, rec: dict[str, Any]) -> None:
        await self._db.execute(
            sa.text("""
                INSERT INTO agent_evolutions (
                    id, workspace_id, agent_name, evolution_type,
                    trigger_reason, after_state
                ) VALUES (
                    :id, :workspace_id, :agent_name, :evolution_type,
                    :trigger_reason, :after_state::jsonb
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "workspace_id": self.workspace_id,
                "agent_name": rec.get("target", "global"),
                "evolution_type": rec.get("type", "strategy_shift"),
                "trigger_reason": rec.get("description", ""),
                "after_state": str(rec),
            },
        )
        await self._db.commit()
