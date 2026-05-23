"""Persistent LLM response cache with Redis backend + local L1."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as redis_async

from app.config.settings import get_settings


class PersistentLLMCache:
    """SHA256-keyed LLM response cache with Redis backend + local L1."""

    def __init__(self) -> None:
        self._l1: dict[str, Any] = {}
        self._redis: redis_async.Redis | None = None
        self.TTL_SECONDS = 86400 * 7

    async def connect(self) -> None:
        settings = get_settings()
        self._redis = redis_async.from_url(  # type: ignore[no-untyped-call]
            settings.resolved_redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    def _key(self, model: str, messages: list[dict[str, Any]]) -> str:
        payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return f"llm_cache:{hashlib.sha256(payload.encode()).hexdigest()}"

    async def get(self, model: str, messages: list[dict[str, Any]]) -> Any | None:
        key = self._key(model, messages)
        if key in self._l1:
            return self._l1[key]
        if self._redis:
            raw = await self._redis.get(key)
            if raw:
                value = json.loads(raw)
                self._l1[key] = value
                return value
        return None

    async def set(self, model: str, messages: list[dict[str, Any]], response: Any) -> None:
        key = self._key(model, messages)
        self._l1[key] = response
        if self._redis:
            await self._redis.setex(key, self.TTL_SECONDS, json.dumps(response))

    async def invalidate_pattern(self, pattern: str = "llm_cache:*") -> int:
        if not self._redis:
            return 0
        keys = await self._redis.keys(pattern)
        if keys:
            result = await self._redis.delete(*keys)
            return result if result is not None else 0
        return 0


llm_cache = PersistentLLMCache()
