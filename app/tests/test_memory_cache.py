from unittest.mock import patch

import pytest

from app.memory.cache import Cache, get_cache


@pytest.mark.asyncio
async def test_cache_set_get_local():
    cache = Cache()
    cache._use_redis = False
    await cache.set("key1", {"data": 42}, ttl=60)
    value = await cache.get("key1")
    assert value == {"data": 42}


@pytest.mark.asyncio
async def test_cache_set_get_string_value():
    cache = Cache()
    cache._use_redis = False
    await cache.set("str_key", "hello", ttl=60)
    value = await cache.get("str_key")
    assert value == "hello"


@pytest.mark.asyncio
async def test_cache_get_missing_key():
    cache = Cache()
    cache._use_redis = False
    value = await cache.get("nonexistent")
    assert value is None


@pytest.mark.asyncio
async def test_cache_delete():
    cache = Cache()
    cache._use_redis = False
    await cache.set("del_key", "value", ttl=60)
    await cache.delete("del_key")
    assert await cache.get("del_key") is None


@pytest.mark.asyncio
async def test_cache_delete_nonexistent():
    cache = Cache()
    cache._use_redis = False
    result = await cache.delete("no-such-key")
    assert result is True


@pytest.mark.asyncio
async def test_cache_flush():
    cache = Cache()
    cache._use_redis = False
    await cache.set("k1", "v1", ttl=60)
    await cache.set("k2", "v2", ttl=60)
    await cache.flush()
    assert await cache.get("k1") is None
    assert await cache.get("k2") is None


@pytest.mark.asyncio
async def test_cache_default_ttl():
    cache = Cache()
    cache._use_redis = False
    await cache.set("ttl_key", "value")
    value = await cache.get("ttl_key")
    assert value == "value"


@pytest.mark.asyncio
async def test_cache_overwrite_key():
    cache = Cache()
    cache._use_redis = False
    await cache.set("overwrite", "old", ttl=60)
    await cache.set("overwrite", "new", ttl=60)
    value = await cache.get("overwrite")
    assert value == "new"


@pytest.mark.asyncio
async def test_cache_redis_unavailable_fallback():
    cache = Cache()
    with patch.object(cache, "_get_redis", return_value=None):
        await cache.set("fallback_key", "fallback_value", ttl=60)
    value = await cache.get("fallback_key")
    assert value == "fallback_value"


@pytest.mark.asyncio
async def test_cache_singleton():
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2
