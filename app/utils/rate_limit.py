"""Rate limiting middleware using slowapi + Redis backend."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings

_limiter: Limiter | None = None


def _build_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
        storage_uri=settings.resolved_redis_url,
    )


def _get_limits() -> dict[str, str]:
    settings = get_settings()
    return {
        "run": settings.rate_limit_run,
        "plan": settings.rate_limit_plan,
        "verify": settings.rate_limit_verify,
        "default": settings.rate_limit_default,
    }


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        _limiter = _build_limiter()
    return _limiter


limiter: Limiter = get_limiter()
LIMITS: dict[str, str] = _get_limits()
__all__ = ["limiter", "LIMITS"]
