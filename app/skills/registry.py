"""Skills Registry — auto-growing library of reusable agent procedures.

Skills are extracted from successful task patterns and stored persistently.
Every time an agent solves a problem well, a skill can be crystallised
and reused in future tasks of the same type.

A skill = (trigger_patterns, procedure, success_examples, confidence_score)
"""
from __future__ import annotations

import re
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.llm_router import WorkType, smart_router
from app.utils.logging import get_logger

logger = get_logger(__name__)

_EXTRACT_SYSTEM = """You are a Skill Extractor for an AI agent system.
Given a successful task execution, extract a reusable skill definition.
Return ONLY valid JSON with these fields:
{
  "name": "Short skill name (3-6 words)",
  "slug": "kebab-case-slug",
  "category": "one of: coding|content|marketing|commerce|devops|analysis|general",
  "description": "What this skill does in 1-2 sentences",
  "trigger_patterns": ["list", "of", "keywords", "that", "trigger", "this", "skill"],
  "procedure": "Step-by-step procedure as markdown, max 500 chars",
  "confidence_score": 0.75
}
If no reusable skill can be extracted, return: {"skip": true}
Return raw JSON only. No markdown, no preamble."""


class SkillsRegistry:
    """Persistent registry of agent skills that grows automatically.

    The registry:
    - Extracts new skills from successful task completions (auto-discovery)
    - Retrieves relevant skills for a given task (skill lookup)
    - Updates confidence scores based on outcomes (reinforcement)
    - Prunes skills that consistently fail (quality control)
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    # ── Auto-discovery ────────────────────────────────────────────────

    async def extract_from_outcome(
        self,
        workspace_id: str,
        task_description: str,
        successful_approach: str,
        task_type: str,
        memory_id: str | None = None,
    ) -> str | None:
        """Auto-extract a skill from a successful task completion.

        Args:
            workspace_id: Workspace scope.
            task_description: What the task was.
            successful_approach: How it was solved.
            task_type: Category of task.
            memory_id: Linked episodic memory ID.

        Returns:
            Skill ID if extracted, None if no extractable skill found.
        """
        prompt = (
            f"Task: {task_description[:300]}\n\n"
            f"Successful approach:\n{successful_approach[:600]}"
        )
        response = await smart_router.complete(
            prompt=prompt,
            system=_EXTRACT_SYSTEM,
            work_type=WorkType.REASONING,
        )
        content = response["choices"][0]["message"]["content"]

        try:
            import json
            data = json.loads(content)
        except (ValueError, KeyError):
            return None

        if data.get("skip"):
            return None

        slug = data.get("slug", "")
        if not slug or not re.match(r"^[a-z0-9-]+$", slug):
            return None

        # Check for duplicate
        existing = await self._db.execute(
            sa.text("SELECT id FROM skills WHERE workspace_id=:w AND slug=:s"),
            {"w": workspace_id, "s": slug},
        )
        if existing.fetchone():
            await self._increment_success(workspace_id, slug)
            return None

        skill_id = str(uuid.uuid4())
        await self._db.execute(
            sa.text("""
                INSERT INTO skills (
                    id, workspace_id, name, slug, category, description,
                    trigger_patterns, procedure, confidence_score,
                    auto_discovered, source_memory_ids
                ) VALUES (
                    :id, :workspace_id, :name, :slug, :category,
                    :description, :trigger_patterns::jsonb, :procedure,
                    :confidence_score, true, :source_memory_ids::jsonb
                )
            """),
            {
                "id": skill_id,
                "workspace_id": workspace_id,
                "name": data["name"],
                "slug": slug,
                "category": data.get("category", "general"),
                "description": data.get("description", ""),
                "trigger_patterns": str(data.get("trigger_patterns", [])),
                "procedure": data.get("procedure", ""),
                "confidence_score": float(data.get("confidence_score", 0.5)),
                "source_memory_ids": f'["{memory_id}"]' if memory_id else "[]",
            },
        )
        await self._db.commit()
        logger.info("skill_extracted", skill_id=skill_id, slug=slug,
                    workspace=workspace_id)
        return skill_id

    # ── Lookup ────────────────────────────────────────────────────────

    async def find_relevant(
        self,
        task_description: str,
        workspace_id: str,
        limit: int = 3,
        min_confidence: float = 0.4,
    ) -> list[dict[str, Any]]:
        """Find skills relevant to the current task using keyword matching.

        Args:
            task_description: The current task prompt.
            workspace_id: Workspace scope.
            limit: Max skills to return.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of matching skill records ordered by confidence desc.
        """
        text = task_description.lower()
        rows = await self._db.execute(
            sa.text("""
                SELECT id, name, slug, category, description, procedure,
                       trigger_patterns, confidence_score,
                       success_count, failure_count
                FROM skills
                WHERE workspace_id = :workspace_id
                  AND is_active = true
                  AND confidence_score >= :min_confidence
                ORDER BY confidence_score DESC, success_count DESC
                LIMIT 50
            """),
            {"workspace_id": workspace_id, "min_confidence": min_confidence},
        )
        candidates = [dict(r._mapping) for r in rows.fetchall()]

        # Keyword scoring
        scored: list[tuple[float, dict[str, Any]]] = []
        for skill in candidates:
            import json
            try:
                triggers = json.loads(skill["trigger_patterns"] or "[]")
            except (ValueError, TypeError):
                triggers = []
            score = sum(1.0 for t in triggers if t.lower() in text)
            score += skill["confidence_score"] * 0.5
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    async def get_all(
        self, workspace_id: str, category: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all active skills for a workspace."""
        q = "SELECT * FROM skills WHERE workspace_id=:w AND is_active=true"
        params: dict[str, Any] = {"w": workspace_id}
        if category:
            q += " AND category=:cat"
            params["cat"] = category
        q += " ORDER BY confidence_score DESC, success_count DESC"
        rows = await self._db.execute(sa.text(q), params)
        return [dict(r._mapping) for r in rows.fetchall()]

    # ── Reinforcement ─────────────────────────────────────────────────

    async def record_usage(
        self, workspace_id: str, slug: str, succeeded: bool
    ) -> None:
        """Update skill stats and confidence after use."""
        if succeeded:
            await self._increment_success(workspace_id, slug)
        else:
            await self._increment_failure(workspace_id, slug)

    async def _increment_success(
        self, workspace_id: str, slug: str
    ) -> None:
        await self._db.execute(
            sa.text("""
                UPDATE skills SET
                    success_count = success_count + 1,
                    confidence_score = LEAST(1.0, confidence_score + 0.05),
                    updated_at = NOW()
                WHERE workspace_id=:w AND slug=:s
            """),
            {"w": workspace_id, "s": slug},
        )
        await self._db.commit()

    async def _increment_failure(
        self, workspace_id: str, slug: str
    ) -> None:
        await self._db.execute(
            sa.text("""
                UPDATE skills SET
                    failure_count = failure_count + 1,
                    confidence_score = GREATEST(0.0, confidence_score - 0.1),
                    is_active = CASE
                        WHEN failure_count >= 4 THEN false
                        ELSE true
                    END,
                    updated_at = NOW()
                WHERE workspace_id=:w AND slug=:s
            """),
            {"w": workspace_id, "s": slug},
        )
        await self._db.commit()
