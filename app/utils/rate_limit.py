from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri=settings.resolved_redis_url,
)

LIMITS = {
    "run": settings.rate_limit_run,
    "plan": settings.rate_limit_plan,
    "verify": settings.rate_limit_verify,
}
