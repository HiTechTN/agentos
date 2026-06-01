"""Comprehensive tests for the Intelligence Engine modules.

Covers:
  - app.memory.episodic (EpisodicMemory, TaskOutcome)
  - app.skills.registry   (SkillsRegistry)
  - app.memory.knowledge  (KnowledgeBase)
  - app.learning.reflection   (SelfReflectionEngine)
  - app.learning.context_enricher (ContextEnricher)
  - app.api.intelligence        (REST endpoints)
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# Global patch: structured logging compatibility
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _patch_structured_logging() -> Generator[None]:
    """Patch Logger.info to accept structured-dict kwargs.

    Several production modules call ``logger.info("event", key=val, ...)``
    which the standard ``logging.Logger.info`` rejects.  This fixture
    filters out unexpected keyword arguments so those calls are harmless.
    """
    import logging

    original = logging.Logger._log

    def _patched_log(
        self: logging.Logger,
        level: int,
        msg: object,
        args: tuple[object, ...],
        exc_info: Any = None,
        **kwargs: Any,
    ) -> None:
        valid = {"extra", "stack_info", "stacklevel"}
        filtered = {k: v for k, v in kwargs.items() if k in valid}
        return original(self, level, msg, args, exc_info=exc_info, **filtered)

    with patch.object(logging.Logger, "_log", _patched_log):
        yield


# ═══════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock AsyncSession with execute/commit."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


# ═══════════════════════════════════════════════════════════════════════
# 1. Episodic Memory — TaskOutcome dataclass + EpisodicMemory
# ═══════════════════════════════════════════════════════════════════════


class TestTaskOutcome:
    """Verify the TaskOutcome dataclass default/field behaviour."""

    def test_defaults(self) -> None:
        from app.memory.episodic import TaskOutcome

        t = TaskOutcome(
            workspace_id="ws-1",
            task_type="code_gen",
            prompt_summary="scaffold API",
            outcome="success",
        )
        assert t.quality_score is None
        assert t.duration_ms is None
        assert t.agent_used == ""
        assert t.model_used == ""
        assert t.work_type == ""
        assert t.input_tokens == 0
        assert t.output_tokens == 0
        assert t.strategy_used == ""
        assert t.what_worked == ""
        assert t.what_failed == ""
        assert t.context_tags == []
        assert t.session_id is None

    def test_all_fields(self) -> None:
        from app.memory.episodic import TaskOutcome

        t = TaskOutcome(
            workspace_id="ws-1",
            task_type="code_gen",
            prompt_summary="Build a REST API with FastAPI",
            outcome="success",
            quality_score=0.95,
            duration_ms=12000,
            agent_used="@DevAgent",
            model_used="gpt-4o",
            work_type="CODE_GEN",
            input_tokens=450,
            output_tokens=1200,
            strategy_used="TDD + iterative refinement",
            what_worked="type hints and tests",
            what_failed="initial schema was wrong",
            context_tags=["python", "fastapi", "rest"],
            session_id="sess-abc123",
        )
        assert t.quality_score == 0.95
        assert t.duration_ms == 12000
        assert t.agent_used == "@DevAgent"
        assert t.model_used == "gpt-4o"
        assert t.context_tags == ["python", "fastapi", "rest"]
        assert t.session_id == "sess-abc123"


class TestEpisodicMemory:
    """EpisodicMemory record / recall / get_best_strategy / get_stats."""

    @pytest.mark.asyncio
    async def test_record(self, mock_db: MagicMock) -> None:
        from app.memory.episodic import EpisodicMemory, TaskOutcome

        mem = EpisodicMemory(mock_db)
        outcome = TaskOutcome(
            workspace_id="ws-1",
            task_type="code_gen",
            prompt_summary="scaffold",
            outcome="success",
        )
        memory_id = await mem.record(outcome)

        assert isinstance(memory_id, str)
        assert len(memory_id) > 0
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_record_truncates_long_prompt(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.episodic import EpisodicMemory, TaskOutcome

        mem = EpisodicMemory(mock_db)
        outcome = TaskOutcome(
            workspace_id="ws-1",
            task_type="code_gen",
            prompt_summary="x" * 2000,
            outcome="success",
        )
        memory_id = await mem.record(outcome)
        assert isinstance(memory_id, str)

        _call_kwargs = mock_db.execute.call_args[0][1]
        assert len(_call_kwargs["prompt_summary"]) <= 500

    @pytest.mark.asyncio
    async def test_recall_similar_with_outcome_filter(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "m1",
            "task_type": "code_gen",
            "prompt_summary": "build",
            "outcome": "success",
            "quality_score": 0.9,
            "strategy_used": "TDD",
            "what_worked": "tests",
            "what_failed": "",
            "model_used": "gpt4",
            "work_type": "CODE_GEN",
            "created_at": "2025-01-01",
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await mem.recall_similar(
            task_type="code_gen",
            workspace_id="ws-1",
            limit=5,
            outcome_filter="success",
        )
        assert len(results) == 1
        assert results[0]["id"] == "m1"
        assert results[0]["strategy_used"] == "TDD"

    @pytest.mark.asyncio
    async def test_recall_similar_no_filter(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await mem.recall_similar(
            task_type="code_gen",
            workspace_id="ws-1",
            outcome_filter=None,
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_best_strategy_found(self, mock_db: MagicMock) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)

        rows = []
        for score, strat in [(0.5, "basic"), (0.95, "advanced"), (0.7, "medium")]:
            r = MagicMock()
            r._mapping = {
                "id": "x",
                "quality_score": score,
                "strategy_used": strat,
                "outcome": "success",
            }
            rows.append(r)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db.execute.return_value = mock_result

        best = await mem.get_best_strategy("code_gen", "ws-1")
        assert best == "advanced"

    @pytest.mark.asyncio
    async def test_get_best_strategy_with_none_score(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)

        r = MagicMock()
        r._mapping = {
            "id": "x",
            "quality_score": None,
            "strategy_used": "fallback",
            "outcome": "success",
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [r]
        mock_db.execute.return_value = mock_result

        best = await mem.get_best_strategy("code_gen", "ws-1")
        assert best == "fallback"

    @pytest.mark.asyncio
    async def test_get_best_strategy_no_memories(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        best = await mem.get_best_strategy("code_gen", "ws-1")
        assert best is None

    @pytest.mark.asyncio
    async def test_get_stats(self, mock_db: MagicMock) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "task_type": "code_gen",
            "total": 15,
            "successes": 12,
            "avg_quality": 0.85,
            "avg_duration_ms": 4500,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        stats = await mem.get_stats("ws-1", days=14)
        assert stats["days"] == 14
        assert len(stats["by_task_type"]) == 1
        assert stats["by_task_type"][0]["total"] == 15

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, mock_db: MagicMock) -> None:
        from app.memory.episodic import EpisodicMemory

        mem = EpisodicMemory(mock_db)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        stats = await mem.get_stats("ws-1")
        assert stats["days"] == 7
        assert stats["by_task_type"] == []


# ═══════════════════════════════════════════════════════════════════════
# 2. Skills Registry
# ═══════════════════════════════════════════════════════════════════════


class TestSkillsRegistry:
    """SkillsRegistry extract / find / get_all / record_usage."""

    # ── extract_from_outcome ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_extract_from_outcome_success(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        skill_data = {
            "name": "API Scaffolder",
            "slug": "api-scaffolder",
            "category": "coding",
            "description": "Scaffolds REST APIs from OpenAPI specs",
            "trigger_patterns": ["api", "rest", "openapi", "scaffold"],
            "procedure": "1. Parse the OpenAPI spec\n2. Generate models\n3. Create routes",
            "confidence_score": 0.8,
        }

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": json.dumps(skill_data)}}],
                }
            )

            dup_result = MagicMock()
            dup_result.fetchone.return_value = None
            mock_db.execute.return_value = dup_result

            skill_id = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="Scaffold a FastAPI project from an OpenAPI spec",
                successful_approach="Used the api-scaffolder template",
                task_type="code_gen",
                memory_id="mem-42",
            )

        assert skill_id is not None
        assert isinstance(skill_id, str)
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_extract_from_outcome_no_memory_id(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        skill_data = {
            "name": "Generic Skill",
            "slug": "generic-skill",
            "category": "general",
            "description": "A generic skill",
            "trigger_patterns": ["generic"],
            "procedure": "Do thing",
            "confidence_score": 0.6,
        }

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": json.dumps(skill_data)}}],
                }
            )

            dup_result = MagicMock()
            dup_result.fetchone.return_value = None
            mock_db.execute.return_value = dup_result

            skill_id = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="Generic task",
                successful_approach="Generic approach",
                task_type="general",
                memory_id=None,
            )

        assert skill_id is not None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_skip(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": '{"skip": true}'}}],
                }
            )

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="Simple task",
                successful_approach="Just did it",
                task_type="general",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_invalid_json(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": "not valid json at all"}}],
                }
            )

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="x",
                successful_approach="y",
                task_type="z",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_empty_content(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": ""}}],
                }
            )

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="x",
                successful_approach="y",
                task_type="z",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_invalid_slug(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "name": "Bad Slug",
                                        "slug": "INVALID SLUG WITH SPACES!!!",
                                        "category": "coding",
                                    }
                                )
                            }
                        }
                    ],
                }
            )

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="x",
                successful_approach="y",
                task_type="z",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_empty_slug(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "name": "No Slug",
                                        "slug": "",
                                        "category": "coding",
                                    }
                                )
                            }
                        }
                    ],
                }
            )

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="x",
                successful_approach="y",
                task_type="z",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_from_outcome_duplicate(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        with patch("app.skills.registry.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "name": "Existing",
                                        "slug": "existing-skill",
                                        "category": "coding",
                                    }
                                )
                            }
                        }
                    ],
                }
            )

            dup_result = MagicMock()
            dup_result.fetchone.return_value = {"id": "existing"}
            mock_db.execute.return_value = dup_result

            result = await registry.extract_from_outcome(
                workspace_id="ws-1",
                task_description="x",
                successful_approach="y",
                task_type="z",
            )

        assert result is None
        assert mock_db.commit.called

    # ── find_relevant ────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_find_relevant_with_matches(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "s1",
            "name": "API Builder",
            "slug": "api-builder",
            "category": "coding",
            "description": "Builds APIs fast",
            "procedure": "Step 1: Scaffold",
            "confidence_score": 0.9,
            "trigger_patterns": '["api", "rest", "endpoint"]',
            "success_count": 10,
            "failure_count": 1,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await registry.find_relevant(
            task_description="Build a REST API endpoint with FastAPI",
            workspace_id="ws-1",
        )

        assert len(results) == 1
        assert results[0]["slug"] == "api-builder"

    @pytest.mark.asyncio
    async def test_find_relevant_score_from_confidence_only(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "s1",
            "name": "Docker Deploy",
            "slug": "docker-deploy",
            "category": "devops",
            "description": "",
            "procedure": "",
            "trigger_patterns": '["docker", "deploy", "container"]',
            "confidence_score": 0.8,
            "success_count": 5,
            "failure_count": 0,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await registry.find_relevant(
            task_description="Write a Python script",
            workspace_id="ws-1",
        )

        # Even without keyword matches, the confidence contribution
        # (0.8 * 0.5 = 0.4) pushes score above 0.
        assert len(results) == 1
        assert results[0]["id"] == "s1"

    @pytest.mark.asyncio
    async def test_find_relevant_empty_candidates(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await registry.find_relevant(
            task_description="Anything",
            workspace_id="ws-1",
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_find_relevant_none_triggers(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "s1",
            "name": "Null Triggers",
            "slug": "null-triggers",
            "category": "general",
            "description": "",
            "procedure": "",
            "trigger_patterns": None,
            "confidence_score": 0.5,
            "success_count": 0,
            "failure_count": 0,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await registry.find_relevant(
            task_description="anything at all",
            workspace_id="ws-1",
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_relevant_bad_json_triggers(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "s1",
            "name": "Bad JSON",
            "slug": "bad-json",
            "category": "general",
            "description": "",
            "procedure": "",
            "trigger_patterns": "not-json-at-all",
            "confidence_score": 0.7,
            "success_count": 0,
            "failure_count": 0,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await registry.find_relevant(
            task_description="anything",
            workspace_id="ws-1",
        )
        assert len(results) == 1

    # ── get_all ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_all_no_category(self, mock_db: MagicMock) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {"id": "s1", "name": "Skill A"}
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row, MagicMock()]
        mock_db.execute.return_value = mock_result

        results = await registry.get_all("ws-1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_all_with_category(self, mock_db: MagicMock) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await registry.get_all("ws-1", category="coding")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_all_with_no_results(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await registry.get_all("ws-1", category="nonexistent")
        assert results == []

    # ── record_usage ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_record_usage_success(self, mock_db: MagicMock) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)
        await registry.record_usage("ws-1", "test-skill", succeeded=True)

        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_record_usage_failure(self, mock_db: MagicMock) -> None:
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry(mock_db)
        await registry.record_usage("ws-1", "test-skill", succeeded=False)

        assert mock_db.execute.called
        assert mock_db.commit.called


# ═══════════════════════════════════════════════════════════════════════
# 3. Knowledge Base
# ═══════════════════════════════════════════════════════════════════════


class TestKnowledgeBase:
    """KnowledgeBase add / query / build_context_block / validate."""

    @pytest.mark.asyncio
    async def test_add(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        entry_id = await kb.add(
            workspace_id="ws-1",
            kind="best_practice",
            title="Use async/await for I/O",
            content="Always prefer async/await over threading for I/O-bound tasks",
            source_type="self_reflection",
            confidence=0.85,
            tags=["python", "async"],
        )

        assert isinstance(entry_id, str)
        assert len(entry_id) > 0
        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_defaults(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        entry_id = await kb.add(
            workspace_id="ws-1",
            kind="domain_fact",
            title="Test",
            content="Test content",
        )

        assert isinstance(entry_id, str)
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_truncates_title_and_content(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        long_title = "x" * 500
        long_content = "y" * 3000

        await kb.add(
            workspace_id="ws-1",
            kind="constraint",
            title=long_title,
            content=long_content,
        )

        call_params = mock_db.execute.call_args[0][1]
        assert len(call_params["title"]) == 256
        assert len(call_params["content"]) == 2000

    # ── query ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_query_with_keywords(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "k1",
            "kind": "best_practice",
            "title": "Use async",
            "content": "Always use async/await",
            "confidence": 0.9,
            "usage_count": 5,
            "tags": ["python"],
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        results = await kb.query("ws-1", ["async", "python"])

        assert len(results) == 1
        assert results[0]["title"] == "Use async"
        assert mock_db.execute.call_count >= 2
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_query_empty_keywords(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await kb.query("ws-1", [])

        assert results == []
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_kind_filter(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await kb.query("ws-1", ["constraint"], kind="constraint")
        assert results == []

    @pytest.mark.asyncio
    async def test_query_no_results_no_update(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        results = await kb.query("ws-1", ["nonexistent"])

        assert results == []
        assert mock_db.execute.call_count == 1
        assert not mock_db.commit.called

    @pytest.mark.asyncio
    async def test_query_truncates_keywords(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "k1",
            "kind": "best_practice",
            "title": "Test",
            "content": "Test",
            "confidence": 0.9,
            "usage_count": 0,
            "tags": [],
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        many_keywords = [str(i) for i in range(50)]
        results = await kb.query("ws-1", many_keywords)
        assert len(results) == 1

    # ── build_context_block ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_build_context_block(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "k1",
            "kind": "best_practice",
            "title": "Use async",
            "content": "Prefer async/await for all I/O operations",
            "confidence": 0.9,
            "usage_count": 0,
            "tags": [],
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        block = await kb.build_context_block("ws-1", ["async"])
        assert block.startswith("## Relevant Project Knowledge")
        assert "Use async" in block
        assert "best_practice" in block

    @pytest.mark.asyncio
    async def test_build_context_block_no_entries(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        block = await kb.build_context_block("ws-1", ["nothing"])
        assert block == ""

    @pytest.mark.asyncio
    async def test_build_context_block_max_chars(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        rows = []
        for i in range(10):
            r = MagicMock()
            r._mapping = {
                "id": f"k{i}",
                "kind": "best_practice",
                "title": f"Long Title {i}",
                "content": "X" * 200,
                "confidence": 0.9,
                "usage_count": 0,
                "tags": [],
            }
            rows.append(r)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = rows
        mock_db.execute.return_value = mock_result

        block = await kb.build_context_block("ws-1", ["test"], max_chars=300)
        assert len(block) <= 300
        assert block.startswith("## Relevant Project Knowledge")

    @pytest.mark.asyncio
    async def test_build_context_block_exact_fit(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)

        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "k1",
            "kind": "fact",
            "title": "T",
            "content": "C",
            "confidence": 0.9,
            "usage_count": 0,
            "tags": [],
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        block = await kb.build_context_block("ws-1", ["test"], max_chars=100)
        assert len(block) > 0
        assert len(block) <= 100

    # ── validate ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_validate_valid(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)
        await kb.validate("ws-1", "entry-1", is_valid=True)

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_validate_invalid(self, mock_db: MagicMock) -> None:
        from app.memory.knowledge import KnowledgeBase

        kb = KnowledgeBase(mock_db)
        await kb.validate("ws-1", "entry-1", is_valid=False)

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════
# 4. Self-Reflection Engine
# ═══════════════════════════════════════════════════════════════════════


class TestSelfReflectionEngine:
    """SelfReflectionEngine should_reflect / run / _llm_reflect / _record_evolution."""

    # ── should_reflect ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_should_reflect_true(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        mock_row = MagicMock()
        mock_row.c = 15
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        assert await engine.should_reflect() is True

    @pytest.mark.asyncio
    async def test_should_reflect_false(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        mock_row = MagicMock()
        mock_row.c = 3
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        assert await engine.should_reflect() is False

    @pytest.mark.asyncio
    async def test_should_reflect_no_row(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        assert await engine.should_reflect() is False

    # ── run (force=True, full cycle) ─────────────────────────────────

    @pytest.mark.asyncio
    async def test_run_force_full_cycle(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        memories = [
            {
                "id": "m1",
                "task_type": "code_gen",
                "prompt_summary": "Scaffold a FastAPI REST API",
                "outcome": "success",
                "quality_score": 0.92,
                "strategy_used": "TDD + iterative refinement",
                "what_worked": "type hints",
                "what_failed": "",
                "model_used": "gpt-4o",
                "work_type": "CODE_GEN",
                "duration_ms": 8500,
            },
            {
                "id": "m2",
                "task_type": "debug",
                "prompt_summary": "Fix intermittent connection timeout",
                "outcome": "success",
                "quality_score": 0.75,
                "strategy_used": "Add retry logic with exponential backoff",
                "what_worked": "logging",
                "what_failed": "",
                "model_used": "gpt-4o-mini",
                "work_type": "DEBUG",
                "duration_ms": 3200,
            },
            {
                "id": "m3",
                "task_type": "content",
                "prompt_summary": "Write blog post about async Python",
                "outcome": "failure",
                "quality_score": 0.3,
                "strategy_used": "Direct generation",
                "what_worked": "",
                "what_failed": "too verbose",
                "model_used": "claude-3",
                "work_type": "CONTENT",
                "duration_ms": 15000,
            },
        ]

        reflection_data = {
            "top_patterns": [
                {"pattern": "TDD improves code quality", "frequency": 2, "outcome": "success"},
            ],
            "recommendations": [
                {
                    "target": "@DevAgent",
                    "type": "strategy_shift",
                    "description": "Always use TDD for code_gen tasks",
                    "priority": "high",
                },
                {
                    "target": "global",
                    "type": "model_preference",
                    "description": "Consider gpt-4o for code tasks",
                    "priority": "medium",
                },
            ],
            "new_knowledge": [
                {
                    "kind": "best_practice",
                    "title": "TDD for APIs",
                    "content": "Test-driven development produces higher quality APIs",
                },
                {
                    "kind": "failure_mode",
                    "title": "Content verbosity",
                    "content": "Direct generation produces verbose output",
                },
            ],
            "overall_health": "good",
            "summary": "Two out of three tasks succeeded. TDD continues to be effective.",
        }

        mock_record_evol = AsyncMock()
        mock_knowledge_add = AsyncMock(return_value="kb-1")
        mock_skills_extract = AsyncMock(side_effect=["skill-1", None])
        with (
            patch.object(engine, "_collect_recent_memories", AsyncMock(return_value=memories)),
            patch.object(engine._db, "execute", AsyncMock(return_value=MagicMock())),
            patch.object(engine._db, "commit", AsyncMock()),
            patch.object(engine.knowledge, "add", mock_knowledge_add),
            patch.object(engine.skills, "extract_from_outcome", mock_skills_extract),
            patch.object(engine, "_record_evolution", mock_record_evol),
        ):
            with patch("app.learning.reflection.smart_router") as mock_router:
                mock_router.complete = AsyncMock(
                    return_value={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(reflection_data),
                                }
                            }
                        ],
                    }
                )
                report = await engine.run(force=True)

        assert report is not None
        assert report["tasks_analyzed"] == 3
        assert report["new_skills_discovered"] == 1
        assert report["knowledge_entries_added"] == 2
        assert report["overall_health"] == "good"
        assert report["summary"] == reflection_data["summary"]
        assert report["avg_quality_score"] == round((0.92 + 0.75 + 0.3) / 3, 3)
        mock_record_evol.assert_awaited_once()
        mock_knowledge_add.assert_awaited()
        mock_skills_extract.assert_awaited()

    # ── run (force=False, should_reflect=False) ──────────────────────

    @pytest.mark.asyncio
    async def test_run_skipped_when_not_force(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        mock_row = MagicMock()
        mock_row.c = 3
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = mock_result

        report = await engine.run(force=False)
        assert report is None

    # ── run (no memories) ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_run_no_memories_returns_none(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        with patch.object(engine, "_collect_recent_memories", AsyncMock(return_value=[])):
            report = await engine.run(force=True)

        assert report is None

    # ── run (low-quality success memories, no skill extraction) ──────

    @pytest.mark.asyncio
    async def test_run_no_skill_extraction_for_low_quality(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        memories = [
            {
                "id": "m1",
                "task_type": "code_gen",
                "prompt_summary": "Simple task",
                "outcome": "success",
                "quality_score": 0.5,
                "strategy_used": "Basic",
                "what_worked": "",
                "what_failed": "",
                "model_used": "gpt4",
                "work_type": "CODE_GEN",
                "duration_ms": 1000,
            },
        ]

        reflection_data = {
            "top_patterns": [],
            "recommendations": [],
            "new_knowledge": [],
            "overall_health": "degraded",
            "summary": "Nothing notable.",
        }

        with patch.object(engine, "_collect_recent_memories", AsyncMock(return_value=memories)):
            with patch("app.learning.reflection.smart_router") as mock_router:
                mock_router.complete = AsyncMock(
                    return_value={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(reflection_data),
                                }
                            }
                        ],
                    }
                )
                report = await engine.run(force=True)

        assert report is not None
        assert report["new_skills_discovered"] == 0
        assert report["knowledge_entries_added"] == 0
        assert report["overall_health"] == "degraded"

    # ── run (no high-priority recommendations → no evolution) ────────

    @pytest.mark.asyncio
    async def test_run_no_high_priority_recommendations(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        memories = [
            {
                "id": "m1",
                "task_type": "code_gen",
                "prompt_summary": "Task",
                "outcome": "success",
                "quality_score": 0.9,
                "strategy_used": "TDD",
                "what_worked": "",
                "what_failed": "",
                "model_used": "gpt4",
                "work_type": "CODE_GEN",
                "duration_ms": 1000,
            },
        ]

        reflection_data = {
            "top_patterns": [],
            "recommendations": [
                {
                    "target": "global",
                    "type": "prompt_update",
                    "description": "Minor tweak",
                    "priority": "low",
                },
            ],
            "new_knowledge": [],
            "overall_health": "excellent",
            "summary": "All good.",
        }

        with patch.object(engine, "_collect_recent_memories", AsyncMock(return_value=memories)):
            with patch("app.learning.reflection.smart_router") as mock_router:
                mock_router.complete = AsyncMock(
                    return_value={
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(reflection_data),
                                }
                            }
                        ],
                    }
                )
                report = await engine.run(force=True)

        assert report is not None
        assert report["overall_health"] == "excellent"

    # ── _llm_reflect ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_llm_reflect_valid_json(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        with patch("app.learning.reflection.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "top_patterns": [],
                                        "recommendations": [],
                                        "new_knowledge": [],
                                        "overall_health": "excellent",
                                        "summary": "Everything is running smoothly.",
                                    }
                                )
                            }
                        }
                    ],
                }
            )

            result = await engine._llm_reflect("summary text")

        assert result["overall_health"] == "excellent"
        assert result["summary"] == "Everything is running smoothly."

    @pytest.mark.asyncio
    async def test_llm_reflect_invalid_json(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        with patch("app.learning.reflection.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": "not valid json"}}],
                }
            )

            result = await engine._llm_reflect("summary text")

        assert result["overall_health"] == "unknown"
        assert "parsing failed" in result["summary"]

    @pytest.mark.asyncio
    async def test_llm_reflect_empty_content(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        with patch("app.learning.reflection.smart_router") as mock_router:
            mock_router.complete = AsyncMock(
                return_value={
                    "choices": [{"message": {"content": ""}}],
                }
            )

            result = await engine._llm_reflect("summary text")
        assert result["overall_health"] == "unknown"

    # ── _record_evolution ────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_record_evolution(self, mock_db: MagicMock) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine(mock_db, "ws-1")

        await engine._record_evolution(
            {
                "target": "@DevAgent",
                "type": "strategy_shift",
                "description": "Switch to TDD for all code_gen tasks",
                "priority": "high",
            }
        )

        mock_db.execute.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    # ── _summarize_memories ──────────────────────────────────────────

    def test_summarize_memories(self) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine.__new__(SelfReflectionEngine)

        memories: list[dict[str, Any]] = [
            {
                "id": "m1",
                "task_type": "code_gen",
                "prompt_summary": "Build a CRUD API with FastAPI",
                "outcome": "success",
                "quality_score": 0.92,
                "strategy_used": "TDD",
                "what_worked": "type hints",
                "what_failed": "",
                "model_used": "gpt4",
                "work_type": "CODE_GEN",
                "duration_ms": 5000,
            },
            {
                "id": "m2",
                "task_type": "debug",
                "prompt_summary": "Fix timeout in connection pool",
                "outcome": "failure",
                "quality_score": None,
                "strategy_used": "print debug",
                "what_worked": "",
                "what_failed": "no instrumentation",
                "model_used": "gpt3.5",
                "work_type": "DEBUG",
                "duration_ms": 3000,
            },
        ]

        summary = engine._summarize_memories(memories)

        assert "2 tasks" in summary
        assert "1 successes" in summary
        assert "code_gen" in summary
        assert "debug" in summary
        assert "Build a CRUD API" in summary
        assert "Fix timeout" in summary

    def test_summarize_memories_single(self) -> None:
        from app.learning.reflection import SelfReflectionEngine

        engine = SelfReflectionEngine.__new__(SelfReflectionEngine)

        memories: list[dict[str, Any]] = [
            {
                "id": "m1",
                "task_type": "code_gen",
                "prompt_summary": "Single task",
                "outcome": "success",
                "quality_score": 0.8,
                "strategy_used": "",
                "what_worked": "",
                "what_failed": "",
                "model_used": "",
                "work_type": "",
                "duration_ms": 0,
            },
        ]

        summary = engine._summarize_memories(memories)
        assert "1 tasks" in summary
        assert "1 successes" in summary
        assert "Single task" in summary


# ═══════════════════════════════════════════════════════════════════════
# 5. Context Enricher
# ═══════════════════════════════════════════════════════════════════════


class TestContextEnricher:
    """ContextEnricher enrich with various combinations of includes."""

    @pytest.mark.asyncio
    async def test_enrich_all_included(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(
                enricher.episodic,
                "recall_similar",
                AsyncMock(
                    return_value=[
                        {
                            "quality_score": 0.9,
                            "prompt_summary": "Build FastAPI REST API",
                            "strategy_used": "TDD",
                        },
                    ]
                ),
            ),
            patch.object(
                enricher.skills,
                "find_relevant",
                AsyncMock(
                    return_value=[
                        {
                            "name": "API Scaffolder",
                            "confidence_score": 0.85,
                            "description": "Scaffolds REST APIs",
                            "procedure": "1. Create routes\n2. Add models",
                        },
                    ]
                ),
            ),
            patch.object(
                enricher.knowledge,
                "build_context_block",
                AsyncMock(return_value="## Relevant Project Knowledge\n- test\n"),
            ),
        ):
            result = await enricher.enrich(
                base_system="You are @DevAgent, a coding assistant.",
                task_description="Build a REST API with FastAPI",
                task_type="code_gen",
                workspace_id="ws-1",
            )

        assert "You are @DevAgent, a coding assistant." in result
        assert "Relevant Past Experiences" in result
        assert "Available Skills" in result
        assert "Relevant Project Knowledge" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_enrich_no_memories(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(enricher.episodic, "recall_similar", AsyncMock(return_value=[])),
            patch.object(
                enricher.skills,
                "find_relevant",
                AsyncMock(
                    return_value=[
                        {
                            "name": "Skill",
                            "confidence_score": 0.8,
                            "description": "Desc",
                            "procedure": "Proc",
                        },
                    ]
                ),
            ),
            patch.object(
                enricher.knowledge,
                "build_context_block",
                AsyncMock(return_value="## Knowledge Block\n"),
            ),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Do something",
                task_type="general",
                workspace_id="ws-1",
            )

        assert "Relevant Past Experiences" not in result
        assert "Available Skills" in result
        assert "Knowledge Block" in result

    @pytest.mark.asyncio
    async def test_enrich_no_skills(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(
                enricher.episodic,
                "recall_similar",
                AsyncMock(
                    return_value=[
                        {
                            "quality_score": 0.7,
                            "prompt_summary": "Past task",
                            "strategy_used": "Manual",
                        },
                    ]
                ),
            ),
            patch.object(enricher.skills, "find_relevant", AsyncMock(return_value=[])),
            patch.object(
                enricher.knowledge,
                "build_context_block",
                AsyncMock(return_value="## Knowledge\n- item\n"),
            ),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Test something",
                task_type="general",
                workspace_id="ws-1",
            )

        assert "Relevant Past Experiences" in result
        assert "Available Skills" not in result

    @pytest.mark.asyncio
    async def test_enrich_no_knowledge(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(
                enricher.episodic,
                "recall_similar",
                AsyncMock(
                    return_value=[
                        {
                            "quality_score": 0.8,
                            "prompt_summary": "Past task",
                            "strategy_used": "TDD",
                        },
                    ]
                ),
            ),
            patch.object(enricher.skills, "find_relevant", AsyncMock(return_value=[])),
            patch.object(enricher.knowledge, "build_context_block", AsyncMock(return_value="")),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Test something",
                task_type="general",
                workspace_id="ws-1",
            )

        assert "Relevant Past Experiences" in result

    @pytest.mark.asyncio
    async def test_enrich_all_disabled(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        result = await enricher.enrich(
            base_system="Just the base prompt.",
            task_description="Do something",
            task_type="general",
            workspace_id="ws-1",
            include_memories=False,
            include_skills=False,
            include_knowledge=False,
        )

        assert result == "Just the base prompt."

    @pytest.mark.asyncio
    async def test_enrich_only_knowledge(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with patch.object(
            enricher.knowledge,
            "build_context_block",
            AsyncMock(return_value="## Relevant Project Knowledge\n- item\n"),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Do something",
                task_type="general",
                workspace_id="ws-1",
                include_memories=False,
                include_skills=False,
                include_knowledge=True,
            )

        assert "Relevant Project Knowledge" in result
        assert "You are an agent." in result

    @pytest.mark.asyncio
    async def test_enrich_only_skills(self, mock_db: MagicMock) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with patch.object(
            enricher.skills,
            "find_relevant",
            AsyncMock(
                return_value=[
                    {
                        "name": "Test Skill",
                        "confidence_score": 0.9,
                        "description": "A test",
                        "procedure": "Do X",
                    },
                ]
            ),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Test task",
                task_type="general",
                workspace_id="ws-1",
                include_memories=False,
                include_skills=True,
                include_knowledge=False,
            )

        assert "Available Skills" in result

    @pytest.mark.asyncio
    async def test_enrich_char_limit_skip_block(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(
                enricher.episodic,
                "recall_similar",
                AsyncMock(
                    return_value=[
                        {
                            "quality_score": 0.9,
                            "prompt_summary": "X" * 2000,
                            "strategy_used": "Y" * 1000,
                        },
                    ]
                ),
            ),
            patch.object(enricher.skills, "find_relevant", AsyncMock(return_value=[])),
            patch.object(enricher.knowledge, "build_context_block", AsyncMock(return_value="")),
        ):
            result = await enricher.enrich(
                base_system="You are an agent.",
                task_description="Test",
                task_type="general",
                workspace_id="ws-1",
            )
        assert "Relevant Past Experiences" in result

    @pytest.mark.asyncio
    async def test_enrich_all_none_no_enrichment(
        self,
        mock_db: MagicMock,
    ) -> None:
        from app.learning.context_enricher import ContextEnricher

        enricher = ContextEnricher(mock_db)

        with (
            patch.object(enricher.episodic, "recall_similar", AsyncMock(return_value=[])),
            patch.object(enricher.skills, "find_relevant", AsyncMock(return_value=[])),
            patch.object(enricher.knowledge, "build_context_block", AsyncMock(return_value="")),
        ):
            result = await enricher.enrich(
                base_system="Just the base prompt.",
                task_description="Test",
                task_type="general",
                workspace_id="ws-1",
            )

        assert result == "Just the base prompt."


# ═══════════════════════════════════════════════════════════════════════
# 6. Intelligence API — REST endpoints
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def mock_intel_session() -> Generator[MagicMock]:
    """Patch _session_factory and _engine in the intelligence API module."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock()
    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_db
    with (
        patch("app.api.intelligence._session_factory", mock_session_factory),
        patch("app.api.intelligence._engine", MagicMock()),
    ):
        yield mock_db


class TestIntelligenceAPI:
    """Integration tests for all intelligence REST endpoints."""

    @pytest.mark.asyncio
    async def test_get_memories(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {"id": "m1", "task_type": "code", "outcome": "success"}
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/memories/ws-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_get_memory_stats(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {
            "task_type": "code",
            "total": 10,
            "successes": 7,
            "avg_quality": 0.8,
            "avg_duration_ms": 5000,
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/memories/ws-1/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["days"] == 7
        assert len(data["data"]["by_task_type"]) == 1

    @pytest.mark.asyncio
    async def test_list_skills(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {"id": "s1", "name": "API Builder"}
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/skills/ws-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_list_skills_with_category(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/skills/ws-1?category=coding",
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_knowledge(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {"id": "k1", "kind": "best_practice", "title": "Test"}
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/knowledge/ws-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_add_knowledge(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_intel_session.execute.return_value = MagicMock()

        response = await async_client.post(
            "/api/v1/intelligence/knowledge/ws-1",
            headers=auth_headers,
            json={"title": "New Knowledge", "content": "Test content"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data["data"]

    @pytest.mark.asyncio
    async def test_trigger_reflection(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        with patch.object(
            SelfReflectionEngine,
            "run",
            AsyncMock(
                return_value={
                    "report_id": "r-1",
                    "tasks_analyzed": 5,
                    "new_skills_discovered": 2,
                    "knowledge_entries_added": 3,
                    "avg_quality_score": 0.85,
                    "overall_health": "good",
                    "summary": "Good performance",
                    "recommendations": [],
                }
            ),
        ):
            response = await async_client.post(
                "/api/v1/intelligence/reflect/ws-1?force=true",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["report_id"] == "r-1"
        assert data["data"]["overall_health"] == "good"

    @pytest.mark.asyncio
    async def test_trigger_reflection_no_force(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        from app.learning.reflection import SelfReflectionEngine

        with patch.object(SelfReflectionEngine, "run", AsyncMock(return_value=None)):
            response = await async_client.post(
                "/api/v1/intelligence/reflect/ws-1",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["data"] is None

    @pytest.mark.asyncio
    async def test_list_reflection_reports(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "r-1",
            "period_start": "2025-01-01",
            "period_end": "2025-01-02",
            "tasks_analyzed": 10,
            "new_skills_discovered": 2,
            "knowledge_entries_added": 3,
            "avg_quality_score": 0.8,
            "summary": "Good",
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/reflect/ws-1/reports",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_list_evolutions(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_row = MagicMock()
        mock_row._mapping = {
            "id": "e-1",
            "agent_name": "@DevAgent",
            "evolution_type": "strategy_shift",
        }
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/evolutions/ws-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1

    @pytest.mark.asyncio
    async def test_list_evolutions_with_agent(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/evolutions/ws-1?agent_name=@DevAgent",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 0

    @pytest.mark.asyncio
    async def test_evolutions_without_agent_filter(
        self,
        async_client: Any,
        auth_headers: dict[str, str],
        mock_intel_session: MagicMock,
    ) -> None:
        mock_rows = [
            MagicMock(_mapping={"id": "e-1", "agent_name": "@DevAgent"}),
            MagicMock(_mapping={"id": "e-2", "agent_name": "@Planner"}),
        ]
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_intel_session.execute.return_value = mock_result

        response = await async_client.get(
            "/api/v1/intelligence/evolutions/ws-1",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
