"""Tests for RotationEngine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.utils.rotation_engine import RotationEngine


@pytest.fixture()
def mock_db() -> MagicMock:
    return AsyncMock()


@pytest.fixture()
def engine(mock_db: MagicMock) -> RotationEngine:
    return RotationEngine(db_session=mock_db)


def _make_candidate(overrides: dict | None = None) -> dict:
    base = {
        "id": "test/model:free",
        "name": "Test Model",
        "provider": "test",
        "context_window": 8192,
        "supports_tools": True,
        "supports_vision": False,
        "avg_latency_ms": 500.0,
        "success_rate": 0.95,
        "quality_score": 0.8,
        "rotation_weight": 1.0,
        "total_requests": 100,
        "total_errors": 5,
        "is_rate_limited_until": None,
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_fetchall(rows: list[dict]) -> MagicMock:
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


def _to_row_mapping(rows: list[dict]) -> list[MagicMock]:
    """Convert dicts to objects with _mapping attribute."""
    out = []
    for r in rows:
        mock = MagicMock()
        mock._mapping = r
        out.append(mock)
    return out


class TestRotationEngine:
    @pytest.mark.asyncio
    async def test_select_model_no_candidates(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=_mock_fetchall([]))

        model = await engine.select_model("code_gen")
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_returns_candidate(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate()])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen")
        assert model is not None
        assert model["id"] == "test/model:free"

    @pytest.mark.asyncio
    async def test_select_model_filters_rate_limited(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate()])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen")
        assert model is not None
        assert model["id"] == "test/model:free"

    @pytest.mark.asyncio
    async def test_select_model_filters_in_memory_banned(self, engine: RotationEngine) -> None:
        engine._in_memory_bans["test/model:free"] = float("inf")
        candidates = _to_row_mapping([_make_candidate()])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen")
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_filters_high_error_rate(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate({"total_requests": 100, "total_errors": 50})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen")
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_filters_slow_latency(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate({"avg_latency_ms": 12000.0})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen")
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_requires_tools(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate({"supports_tools": False})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen", requires_tools=True)
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_requires_vision(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate({"supports_vision": False})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen", requires_vision=True)
        assert model is None

    @pytest.mark.asyncio
    async def test_select_model_min_context(self, engine: RotationEngine) -> None:
        candidates = _to_row_mapping([_make_candidate({"context_window": 4096})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(candidates))

        model = await engine.select_model("code_gen", min_context=8192)
        assert model is None

    @pytest.mark.asyncio
    async def test_record_success(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine.record_success("test/model:free", "code_gen", latency_ms=450)

        assert "test/model:free" not in engine._in_memory_bans
        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_record_success_clears_bans(self, engine: RotationEngine) -> None:
        engine._in_memory_bans["test/model:free"] = 12345.0
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine.record_success("test/model:free", "code_gen", latency_ms=300)

        assert "test/model:free" not in engine._in_memory_bans

    @pytest.mark.asyncio
    async def test_record_error(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine.record_error("test/model:free", "code_gen", error_code="500")

        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_record_rate_limit(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine.record_rate_limit("test/model:free", "code_gen")

        assert "test/model:free" in engine._in_memory_bans
        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_disable_model(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=MagicMock())
        engine._db.commit = AsyncMock()

        await engine.disable_model("test/model:free", reason="test")

        assert engine._in_memory_bans["test/model:free"] == float("inf")
        engine._db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_catalog(self, engine: RotationEngine) -> None:
        cat_rows = _to_row_mapping([_make_candidate({"disabled_reason": None})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(cat_rows))

        catalog = await engine.get_catalog()
        assert len(catalog) == 1
        assert catalog[0]["id"] == "test/model:free"

    @pytest.mark.asyncio
    async def test_get_catalog_no_results(self, engine: RotationEngine) -> None:
        engine._db.execute = AsyncMock(return_value=_mock_fetchall([]))

        catalog = await engine.get_catalog()
        assert catalog == []

    @pytest.mark.asyncio
    async def test_get_catalog_with_work_type_filter(self, engine: RotationEngine) -> None:
        cat_rows = _to_row_mapping([_make_candidate()])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(cat_rows))

        catalog = await engine.get_catalog(work_type="code_gen")
        assert len(catalog) == 1

    @pytest.mark.asyncio
    async def test_get_catalog_active_only(self, engine: RotationEngine) -> None:
        cat_rows = _to_row_mapping([_make_candidate({"is_active": True})])
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(cat_rows))

        catalog = await engine.get_catalog()
        assert len(catalog) == 1
        assert catalog[0]["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_rotation_stats(self, engine: RotationEngine) -> None:
        log_rows = _to_row_mapping(
            [
                {
                    "model_id": "test/model:free",
                    "work_type": "code_gen",
                    "reason": "selected",
                    "latency_ms": 500,
                    "success": True,
                    "error_code": None,
                    "rotated_to": None,
                    "created_at": "2025-01-01T00:00:00",
                },
            ]
        )
        engine._db.execute = AsyncMock(return_value=_mock_fetchall(log_rows))

        stats = await engine.get_rotation_stats(limit=10)
        assert len(stats) == 1
        assert stats[0]["reason"] == "selected"

    def test_is_banned_disabled(self, engine: RotationEngine) -> None:
        engine._in_memory_bans["test/model:free"] = float("inf")
        assert engine._is_banned("test/model:free") is True

    def test_is_banned_not_banned(self, engine: RotationEngine) -> None:
        assert engine._is_banned("test/model:free") is False

    def test_is_banned_active(self, engine: RotationEngine) -> None:
        import time

        engine._in_memory_bans["test/model:free"] = time.time() + 3600
        assert engine._is_banned("test/model:free") is True

    def test_is_banned_expired(self, engine: RotationEngine) -> None:
        import time

        engine._in_memory_bans["test/model:free"] = time.time() - 100
        assert engine._is_banned("test/model:free") is False
        assert "test/model:free" not in engine._in_memory_bans
