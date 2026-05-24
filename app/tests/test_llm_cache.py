"""Tests for PersistentLLMCache (L1 + Redis L2)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.utils.llm_cache import PersistentLLMCache


@pytest.fixture()
def cache() -> PersistentLLMCache:
    return PersistentLLMCache()


@pytest.fixture()
def messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "hello"}]


class TestLLMCacheKey:
    def test_same_input_same_key(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        k1 = cache._make_key("gpt-4", messages)
        k2 = cache._make_key("gpt-4", messages)
        assert k1 == k2

    def test_different_model_different_key(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        k1 = cache._make_key("gpt-4", messages)
        k2 = cache._make_key("claude-3", messages)
        assert k1 != k2

    def test_key_starts_with_prefix(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        assert cache._make_key("m", messages).startswith("llm_cache:")


class TestLLMCacheL1:
    @pytest.mark.asyncio
    async def test_miss_returns_none(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        result = await cache.get("model", messages)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_then_get_returns_value(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        await cache.set("model", messages, {"content": "hi"})
        result = await cache.get("model", messages)
        assert result == {"content": "hi"}

    @pytest.mark.asyncio
    async def test_invalidate_clears_l1(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        await cache.set("model", messages, "value")
        await cache.invalidate()
        assert await cache.get("model", messages) is None


class TestLLMCacheRedis:
    @pytest.mark.asyncio
    async def test_redis_hit_promotes_to_l1(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"answer": 42}')
        cache._redis = mock_redis

        result = await cache.get("model", messages)
        assert result == {"answer": 42}
        key = cache._make_key("model", messages)
        assert key in cache._l1

    @pytest.mark.asyncio
    async def test_set_writes_to_redis(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        mock_redis = AsyncMock()
        cache._redis = mock_redis
        await cache.set("model", messages, {"r": 1})
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_calls_redis_delete(
        self, cache: PersistentLLMCache, messages: list[dict[str, str]]
    ) -> None:
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=["llm_cache:abc"])
        mock_redis.delete = AsyncMock(return_value=1)
        cache._redis = mock_redis
        count = await cache.invalidate()
        assert count == 1
