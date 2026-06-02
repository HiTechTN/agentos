"""Production configuration validator.

Runs at startup to catch common misconfigurations before they cause
security incidents or runtime failures.
"""

from __future__ import annotations

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigValidationError(Exception):
    """Raised when a critical configuration check fails."""


def validate_production_config() -> list[str]:
    """Validate all settings for production readiness.

    Returns:
        A list of warning/error messages. An empty list means all checks passed.
    """
    settings = get_settings()
    warnings: list[str] = []

    if "change-in-prod" in settings.jwt_secret.get_secret_value().lower():
        warnings.append("JWT_SECRET still contains default value 'change-in-prod'")

    if settings.environment == "production":
        jwt_val = settings.jwt_secret.get_secret_value()
        if not jwt_val or jwt_val.startswith("agentos-"):
            warnings.append("JWT_SECRET appears to be a default/demo value")

        if not settings.database_url and not settings.postgres_password:
            warnings.append("No database password configured")

        if not settings.openrouter_api_key:
            warnings.append("OPENROUTER_API_KEY is empty — LLM calls will fail")

    if settings.environment != "production":
        return warnings

    if settings.rate_limit_default == "100/minute":
        warnings.append("RATE_LIMIT_DEFAULT is at default — consider tightening for production")

    return warnings


async def validate_and_block() -> None:
    """Validate config and raise ConfigValidationError if critical issues found.

    In production mode, this blocks startup with a clear error message.
    In development mode, warnings are logged but startup continues.
    """
    warnings = validate_production_config()
    if not warnings:
        logger.log_action("config", "validation_passed", "completed")
        return

    settings = get_settings()
    if settings.environment == "production":
        msg = "CRITICAL: Production configuration validation failed:\n" + "\n".join(
            f"  - {w}" for w in warnings
        )
        logger.log_error("config", "validation_failed", msg)
        raise ConfigValidationError(msg)
    for w in warnings:
        logger.log_warn("config", "config_warning", w, settings.environment)
