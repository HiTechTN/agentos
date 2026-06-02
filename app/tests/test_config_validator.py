"""Tests for config_validator — production configuration validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config.settings import Settings
from app.utils.config_validator import (
    ConfigValidationError,
    validate_and_block,
    validate_production_config,
)


def _make_settings(
    environment: str = "development",
    jwt_secret: str = "agentos-jwt-secret-change-in-prod",
    database_url: str | None = "sqlite:///test.db",
    postgres_password: str = "secret",
    openrouter_api_key: str = "sk-key",
    rate_limit_default: str = "100/minute",
) -> Settings:
    return Settings(
        environment=environment,
        jwt_secret=jwt_secret,
        database_url=database_url,
        postgres_password=postgres_password,
        openrouter_api_key=openrouter_api_key,
        rate_limit_default=rate_limit_default,
    )


_GET_SETTINGS_PATH = "app.utils.config_validator.get_settings"


class TestValidationError:
    def test_validation_error_class(self) -> None:
        err = ConfigValidationError("something is wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something is wrong"

    def test_validation_error_can_be_caught(self) -> None:
        try:
            raise ConfigValidationError("critical failure")
        except ConfigValidationError as e:
            assert str(e) == "critical failure"


class TestValidateDev:
    def test_validate_dev_no_errors(self) -> None:
        settings = _make_settings(
            environment="development",
            jwt_secret="dev-secret-key",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert warnings == []

    def test_validate_dev_with_default_jwt_returns_warnings(self) -> None:
        settings = _make_settings(
            environment="development",
            jwt_secret="agentos-jwt-secret-change-in-prod",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert len(warnings) >= 1
        assert any("change-in-prod" in w.lower() for w in warnings)

    def test_validate_dev_returns_warnings_does_not_raise(self) -> None:
        settings = _make_settings(
            environment="development",
            jwt_secret="agentos-jwt-secret-change-in-prod",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert isinstance(warnings, list)


class TestValidateProduction:
    def test_validate_prod_jwt_default(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="agentos-jwt-secret-change-in-prod",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert any("JWT_SECRET" in w for w in warnings)

    def test_validate_prod_jwt_empty(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert any("JWT_SECRET" in w for w in warnings)

    def test_validate_prod_no_password(self) -> None:
        settings = _make_settings(
            environment="production",
            database_url=None,
            postgres_password="",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert any("password" in w.lower() for w in warnings)

    def test_validate_prod_no_api_key(self) -> None:
        settings = _make_settings(
            environment="production",
            openrouter_api_key="",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert any("OPENROUTER_API_KEY" in w for w in warnings)

    def test_validate_prod_rate_limit_default(self) -> None:
        settings = _make_settings(
            environment="production",
            rate_limit_default="100/minute",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert any("RATE_LIMIT_DEFAULT" in w for w in warnings)

    def test_validate_prod_all_passed(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="a-very-strong-unique-secret-12345",
            database_url="postgresql://user:strongpass@db:5432/prod",
            openrouter_api_key="sk-strong-key",
            rate_limit_default="30/minute",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert warnings == []

    def test_validate_prod_catches_all_at_once(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="agentos-jwt-secret-change-in-prod",
            database_url=None,
            postgres_password="",
            openrouter_api_key="",
            rate_limit_default="100/minute",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            warnings = validate_production_config()
        assert len(warnings) >= 4


class TestValidateAndBlock:
    @pytest.mark.asyncio
    async def test_validate_and_block_dev(self) -> None:
        settings = _make_settings(
            environment="development",
            jwt_secret="agentos-jwt-secret-change-in-prod",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            await validate_and_block()

    @pytest.mark.asyncio
    async def test_validate_and_block_prod_raises(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="agentos-jwt-secret-change-in-prod",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            with pytest.raises(ConfigValidationError) as exc:
                await validate_and_block()
            assert "JWT_SECRET" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validate_and_block_prod_clean_does_not_raise(self) -> None:
        settings = _make_settings(
            environment="production",
            jwt_secret="super-secure-production-key-abc123",
            database_url="postgresql://user:pass@db:5432/prod",
            openrouter_api_key="sk-secure-key",
            rate_limit_default="30/minute",
        )
        with patch(_GET_SETTINGS_PATH, return_value=settings):
            await validate_and_block()
