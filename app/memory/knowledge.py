"""Knowledge Base — cumulative domain knowledge that enriches all agents.

Every time an agent discovers something useful (an API pattern, a project
constraint, a best practice), it's stored here and automatically injected
into future agent contexts.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logging import get_logger

logger = get_logger(__name__)

KIND_API_PATTERN = "api_pattern"
KIND_CODE_PATTERN = "code_pattern"
KIND_CONSTRAINT = "constraint"
KIND_BEST_PRACTICE = "best_practice"
KIND_DOMAIN_FACT = "domain_fact"
KIND_FAILURE_MODE = "failure_mode"


class KnowledgeBase:
    """Persistent, queryable store of domain knowledge.

    Knowledge entries are written by agents after task completion,
    retrieved before task execution to enrich context, and decayed
    over time if they prove unreliable.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    async def add(
        self,
        workspace_id: str,
        kind: str,
        title: str,
        content: str,
        source_type: str = "task_completion",
        confidence: float = 0.7,
        tags: list[str] | None = None,
    ) -> str:
        """Add a knowledge entry. Returns entry ID."""
        entry_id = str(uuid.uuid4())
        await self._db.execute(
            sa.text("""
                INSERT INTO knowledge_entries (
                    id, workspace_id, kind, title, content,
                    source_type, confidence, tags
                ) VALUES (
                    :id, :workspace_id, :kind, :title, :content,
                    :source_type, :confidence, CAST(:tags AS jsonb)
                )
                ON CONFLICT DO NOTHING
            """),
            {
                "id": entry_id,
                "workspace_id": workspace_id,
                "kind": kind,
                "title": title[:256],
                "content": content[:2000],
                "source_type": source_type,
                "confidence": confidence,
                "tags": str(tags or []),
            },
        )
        await self._db.commit()
        logger.debug("knowledge_added kind=%s title=%s", kind, title[:50])
        return entry_id

    async def query(
        self,
        workspace_id: str,
        keywords: list[str] | None = None,
        kind: str | None = None,
        limit: int = 5,
        min_confidence: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant knowledge entries by keyword matching.

        Args:
            workspace_id: Workspace scope.
            keywords: Keywords to search for in title and content.
                      If None or empty, returns all entries sorted by confidence.
            kind: Optional filter by knowledge kind.
            limit: Max entries to return.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of matching knowledge entries.
        """
        if not keywords:
            rows = await self._db.execute(
                sa.text("""
                    SELECT id, kind, title, content, confidence, usage_count, tags
                    FROM knowledge_entries
                    WHERE workspace_id = :workspace_id
                      AND confidence >= :min_confidence
                    ORDER BY confidence DESC, usage_count DESC
                    LIMIT :limit
                """),
                {
                    "workspace_id": workspace_id,
                    "min_confidence": min_confidence,
                    "limit": limit,
                },
            )
            return [dict(r._mapping) for r in rows.fetchall()]

        params: dict[str, Any] = {
            "workspace_id": workspace_id,
            "min_confidence": min_confidence,
            "patterns": [f"%{k}%" for k in keywords[:10]],
            "limit": limit,
        }
        conditions = [
            "workspace_id = :workspace_id",
            "confidence >= :min_confidence",
            "(title ILIKE ANY(:patterns) OR content ILIKE ANY(:patterns))",
        ]
        if kind:
            conditions.append("kind = :kind")
            params["kind"] = kind

        _parts = [
            "SELECT id, kind, title, content, confidence, usage_count, tags",
            "FROM knowledge_entries",
            "WHERE " + " AND ".join(conditions),
            "ORDER BY confidence DESC, usage_count DESC",
            "LIMIT :limit",
        ]
        query = " ".join(_parts)  # nosec
        rows = await self._db.execute(sa.text(query), params)
        entries = [dict(r._mapping) for r in rows.fetchall()]

        if entries:
            ids = [e["id"] for e in entries]
            await self._db.execute(
                sa.text("""
                    UPDATE knowledge_entries
                    SET usage_count = usage_count + 1
                    WHERE id = ANY(:ids::uuid[])
                """),
                {"ids": ids},
            )
            await self._db.commit()

        return entries

    async def build_context_block(
        self,
        workspace_id: str,
        keywords: list[str],
        max_chars: int = 1500,
    ) -> str:
        """Build a compact context block to inject into agent prompts.

        Returns a formatted string ready for injection in system prompts.
        """
        entries = await self.query(workspace_id, keywords, limit=8)
        if not entries:
            return ""

        lines = ["## Relevant Project Knowledge\n"]
        total = len(lines[0])
        for e in entries:
            line = f"- [{e['kind']}] **{e['title']}**: {e['content'][:200]}\n"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

        return "".join(lines)

    async def validate(self, workspace_id: str, entry_id: str, is_valid: bool) -> None:
        """Validate or invalidate a knowledge entry based on observed outcomes."""
        delta = 0.1 if is_valid else -0.2
        await self._db.execute(
            sa.text("""
                UPDATE knowledge_entries SET
                    confidence = GREATEST(0.0, LEAST(1.0, confidence + :delta)),
                    last_validated_at = NOW()
                WHERE id = :id AND workspace_id = :w
            """),
            {"delta": delta, "id": entry_id, "w": workspace_id},
        )
        await self._db.commit()
