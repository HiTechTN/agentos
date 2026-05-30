import json
import pickle
from typing import Any

import redis.asyncio as aioredis

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("cache")


class Cache:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._redis: aioredis.Redis | None = None
        self._local_cache: dict[str, tuple[float, Any]] = {}
        self._use_redis = True

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            self._redis = aioredis.from_url(
                self.settings.resolved_redis_url,
                decode_responses=False,
            )
            await self._redis.ping()  # type: ignore[misc]
            logger.log_action("cache", "redis_init", "connected")
            return self._redis
        except Exception as e:
            logger.log_warn("cache", "redis_init", f"Redis unavailable, using local dict: {e}")
            self._use_redis = False
            return None

    async def get(self, key: str, ttl: int | None = None) -> Any | None:
        if self._use_redis:
            redis = await self._get_redis()
            if redis:
                data = await redis.get(key)
                if data:
                    try:
                        return pickle.loads(data)  # nosec B301
                    except Exception:
                        return json.loads(data)

        import time

        entry = self._local_cache.get(key)
        if entry:
            expires, value = entry
            if ttl and ttl > 0 and (time.time() - expires > ttl):
                del self._local_cache[key]
                return None
            return value
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        if ttl is None:
            ttl = self.settings.llm_cache_ttl

        if self._use_redis:
            redis = await self._get_redis()
            if redis:
                try:
                    data = pickle.dumps(value)
                    await redis.setex(key, ttl, data)
                    return True
                except Exception as e:
                    logger.log_warn("cache", "redis_set", f"Redis write failed: {e}")

        import time

        self._local_cache[key] = (time.time(), value)
        return True

    async def delete(self, key: str) -> bool:
        if self._use_redis:
            redis = await self._get_redis()
            if redis:
                await redis.delete(key)
        self._local_cache.pop(key, None)
        return True

    async def flush(self) -> bool:
        self._local_cache.clear()
        if self._use_redis:
            redis = await self._get_redis()
            if redis:
                await redis.flushdb()
        return True


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache
