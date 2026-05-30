"""Rate limiting helpers for SmartLLMRouter — tracks per-model usage and bans."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.utils.logging import get_logger

from .llm_models import FreeModel

logger = get_logger(__name__)


@dataclass
class _ModelUsage:
    """Track per-model usage for rate limiting."""

    requests_this_minute: int = 0
    requests_today: int = 0
    minute_window_start: float = field(default_factory=time.time)
    day_window_start: float = field(default_factory=time.time)
    consecutive_errors: int = 0
    last_error_time: float = 0.0
    is_banned_until: float = 0.0


_usage: dict[str, _ModelUsage] = {}
_usage_lock = asyncio.Lock()


async def _get_usage(model_id: str) -> _ModelUsage:
    async with _usage_lock:
        if model_id not in _usage:
            _usage[model_id] = _ModelUsage()
        return _usage[model_id]


async def _is_available(model: FreeModel) -> bool:
    """Return True if the model is not rate-limited or temporarily banned."""
    usage = await _get_usage(model.id)
    now = time.time()

    if usage.is_banned_until > now:
        return False

    if now - usage.minute_window_start >= 60:
        usage.requests_this_minute = 0
        usage.minute_window_start = now

    if now - usage.day_window_start >= 86_400:
        usage.requests_today = 0
        usage.day_window_start = now

    return (
        usage.requests_this_minute < model.req_per_min - 2
        and usage.requests_today < model.req_per_day - 5
    )


async def _record_request(model_id: str, success: bool) -> None:
    """Record a request and update error tracking."""
    usage = await _get_usage(model_id)
    usage.requests_this_minute += 1
    usage.requests_today += 1

    if success:
        usage.consecutive_errors = 0
    else:
        usage.consecutive_errors += 1
        usage.last_error_time = time.time()
        if usage.consecutive_errors >= 3:
            usage.is_banned_until = time.time() + 300
            logger.log_warn(
                "llm_router",
                "model_banned",
                f"Model {model_id} banned until {usage.is_banned_until}",
            )


__all__ = [
    "_ModelUsage",
    "_usage",
    "_usage_lock",
    "_is_available",
    "_record_request",
]
