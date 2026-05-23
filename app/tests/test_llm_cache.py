from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.llm_cache import PersistentLLMCache, llm_cache


class TestPersistentLLMCache:
    def test_singleton_is_global(self) -> None:
        assert llm_cache is not None
        assert isinstance(llm_cache, PersistentLLMCache)

    @pytest.mark.asyncio
    async def test_connect_redis_unavailable_keeps_l1_only(self) -> None:
        cache = PersistentLLMCache()
        assert cache._redis is None
        with patch("app.utils.llm_cache.redis_async.from_url", side_effect=Exception("No Redis")):
            with pytest.raises(Exception):
                await cache.connect()
        assert cache._redis is None
        await cache.set("m", [{"role": "user", "content": "hi"}], "l1-works")
        assert await cache.get("m", [{"role": "user", "content": "hi"}]) == "l1-works"

    @pytest.mark.asyncio
    async def test_set_and_get_l1(self) -> None:
        cache = PersistentLLMCache()
        model = "gpt-4"
        messages = [{"role": "user", "content": "hello"}]
        response = {"choices": [{"text": "world"}]}
        await cache.set(model, messages, response)
        cached = await cache.get(model, messages)
        assert cached == response

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self) -> None:
        cache = PersistentLLMCache()
        result = await cache.get("model-x", [{"role": "user", "content": "nope"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_l1_populated_on_set(self) -> None:
        cache = PersistentLLMCache()
        await cache.set("m", [{"role": "user", "content": "x"}], "response-data")
        result = await cache.get("m", [{"role": "user", "content": "x"}])
        assert result == "response-data"

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_redis_returns_zero(self) -> None:
        cache = PersistentLLMCache()
        count = await cache.invalidate_pattern("llm_cache:*")
        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_pattern_with_redis(self) -> None:
        cache = PersistentLLMCache()
        cache._redis = MagicMock()
        cache._redis.keys = AsyncMock(return_value=["llm_cache:abc", "llm_cache:def"])
        cache._redis.delete = AsyncMock(return_value=2)
        count = await cache.invalidate_pattern("llm_cache:*")
        assert count == 2
        cache._redis.keys.assert_awaited_once_with("llm_cache:*")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_keys(self) -> None:
        cache = PersistentLLMCache()
        cache._redis = MagicMock()
        cache._redis.keys = AsyncMock(return_value=[])
        count = await cache.invalidate_pattern("llm_cache:*")
        assert count == 0

    def test_key_consistency(self) -> None:
        cache = PersistentLLMCache()
        k1 = cache._key("m", [{"role": "user", "content": "hi"}])
        k2 = cache._key("m", [{"role": "user", "content": "hi"}])
        assert k1 == k2
        assert k1.startswith("llm_cache:")

    def test_key_differs_for_different_inputs(self) -> None:
        cache = PersistentLLMCache()
        k1 = cache._key("m", [{"role": "user", "content": "hi"}])
        k2 = cache._key("m", [{"role": "user", "content": "bye"}])
        assert k1 != k2

    def test_key_differs_for_different_models(self) -> None:
        cache = PersistentLLMCache()
        k1 = cache._key("gpt-4", [{"role": "user", "content": "hi"}])
        k2 = cache._key("claude-3", [{"role": "user", "content": "hi"}])
        assert k1 != k2

    def test_ttl_is_seven_days(self) -> None:
        cache = PersistentLLMCache()
        assert cache.TTL_SECONDS == 86400 * 7

    @pytest.mark.asyncio
    async def test_singleton_instance_is_same(self) -> None:
        from app.utils.llm_cache import llm_cache as other_ref

        assert other_ref is llm_cache
