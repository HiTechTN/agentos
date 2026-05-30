"""Two-level LLM response cache: in-memory L1 + Redis L2."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.config.settings import get_settings


class PersistentLLMCache:
    """SHA256-keyed LLM cache with Redis persistence and local L1."""

    TTL_SECONDS: int = 86_400 * 7  # 7 days

    def __init__(self) -> None:
        self._l1: dict[str, Any] = {}
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        try:
            settings = get_settings()
            self._redis = aioredis.from_url(
                settings.resolved_redis_url,
                encoding="utf-8",
                decode_responses=True,
            )  # type: ignore[no-untyped-call]
        except Exception:
            self._redis = None

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    def _make_key(self, model: str, messages: list[dict[str, str]]) -> str:
        payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f"llm_cache:{digest}"

    async def get(self, model: str, messages: list[dict[str, str]]) -> Any | None:
        key = self._make_key(model, messages)
        if key in self._l1:
            return self._l1[key]
        if self._redis:
            raw = await self._redis.get(key)
            if raw:
                value = json.loads(raw)
                self._l1[key] = value
                return value
        return None

    async def set(self, model: str, messages: list[dict[str, str]], response: Any) -> None:
        key = self._make_key(model, messages)
        self._l1[key] = response
        if self._redis:
            await self._redis.setex(key, self.TTL_SECONDS, json.dumps(response))

    async def invalidate(self, pattern: str = "llm_cache:*") -> int:
        self._l1.clear()
        if not self._redis:
            return 0
        keys: list[str] = await self._redis.keys(pattern)
        if keys:
            return int(await self._redis.delete(*keys))
        return 0


llm_cache = PersistentLLMCache()
