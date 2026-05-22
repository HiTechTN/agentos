from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings

__all__ = ["limiter", "LIMITS"]

LIMITS: dict[str, str] = {}


def _make_limiter() -> Limiter:
    settings = get_settings()
    LIMITS["run"] = settings.rate_limit_run
    LIMITS["plan"] = settings.rate_limit_plan
    LIMITS["verify"] = settings.rate_limit_verify
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
        storage_uri=settings.resolved_redis_url,
    )


limiter = _make_limiter()
