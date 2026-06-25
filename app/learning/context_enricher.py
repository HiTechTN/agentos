"""Context Enricher — auto-injects memory, skills and knowledge into agents.

Before any agent executes a task, the enricher:
  1. Recalls similar past experiences from episodic memory
  2. Finds relevant skills from the skills registry
  3. Retrieves applicable knowledge from the knowledge base
  4. Builds an enriched context block to prepend to the system prompt

This makes every agent smarter over time without any manual intervention.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.episodic import EpisodicMemory
from app.memory.knowledge import KnowledgeBase
from app.skills.registry import SkillsRegistry
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ContextEnricher:
    """Builds an enriched context block from accumulated intelligence.

    Usage::

        enricher = ContextEnricher(db_session)
        enriched_system = await enricher.enrich(
            base_system="You are @DevAgent...",
            task_description="Scaffold a FastAPI REST API",
            task_type="code_gen",
            workspace_id="default",
        )
        # enriched_system now contains relevant skills, past experiences,
        # and domain knowledge prepended to the base system prompt
    """

    MAX_ENRICHMENT_CHARS = 2000

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session
        self.episodic = EpisodicMemory(db_session)
        self.skills = SkillsRegistry(db_session)
        self.knowledge = KnowledgeBase(db_session)

    async def _build_memories_block(
        self,
        task_type: str,
        workspace_id: str,
        chars_used: int,
    ) -> str | None:
        """Build context block from past successful experiences."""
        memories = await self.episodic.recall_similar(
            task_type=task_type,
            workspace_id=workspace_id,
            limit=3,
            outcome_filter="success",
        )
        if not memories:
            return None
        lines = ["## Relevant Past Experiences\n"]
        for m in memories:
            q = m.get("quality_score")
            score = f"{q:.1f}" if q else "?"
            line = (
                f"- [quality={score}] {m['prompt_summary'][:80]} "
                f"\u2192 Used: {m.get('strategy_used', 'N/A')[:60]}\n"
            )
            lines.append(line)
        block = "".join(lines)
        if chars_used + len(block) >= self.MAX_ENRICHMENT_CHARS:
            return None
        return block

    async def _build_skills_block(
        self,
        task_description: str,
        workspace_id: str,
        chars_used: int,
    ) -> str | None:
        """Build context block from relevant skills."""
        skill_list = await self.skills.find_relevant(
            task_description=task_description,
            workspace_id=workspace_id,
            limit=3,
        )
        if not skill_list:
            return None
        lines = ["## Available Skills\n"]
        for s in skill_list:
            conf = s.get("confidence_score", 0.5)
            line = (
                f"- **{s['name']}** (confidence={conf:.1f}): "
                f"{s['description'][:100]}\n"
                f"  Procedure: {s['procedure'][:150]}\n"
            )
            lines.append(line)
        block = "".join(lines)
        if chars_used + len(block) >= self.MAX_ENRICHMENT_CHARS:
            return None
        return block

    async def _build_knowledge_block(
        self,
        task_description: str,
        workspace_id: str,
        chars_used: int,
    ) -> str | None:
        """Build context block from domain knowledge."""
        keywords = task_description.lower().split()[:15]
        return await self.knowledge.build_context_block(
            workspace_id=workspace_id,
            keywords=keywords,
            max_chars=self.MAX_ENRICHMENT_CHARS - chars_used,
        )

    async def enrich(
        self,
        base_system: str,
        task_description: str,
        task_type: str,
        workspace_id: str,
        include_skills: bool = True,
        include_memories: bool = True,
        include_knowledge: bool = True,
    ) -> str:
        """Build an enriched system prompt with accumulated intelligence.

        Returns the base_system augmented with relevant context,
        capped at MAX_ENRICHMENT_CHARS for the enrichment block.
        """
        blocks: list[str] = []
        chars_used = 0

        if include_memories:
            block = await self._build_memories_block(task_type, workspace_id, chars_used)
            if block:
                blocks.append(block)
                chars_used += len(block)

        if include_skills:
            block = await self._build_skills_block(task_description, workspace_id, chars_used)
            if block:
                blocks.append(block)
                chars_used += len(block)

        if include_knowledge:
            block = await self._build_knowledge_block(task_description, workspace_id, chars_used)
            if block:
                blocks.append(block)

        if not blocks:
            return base_system

        enrichment = "\n".join(blocks)
        logger.debug(
            "context_enriched task_type=%s chars=%d blocks=%d",
            task_type,
            len(enrichment),
            len(blocks),
        )
        return f"{enrichment}\n\n---\n\n{base_system}"
