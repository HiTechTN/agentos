"""Tests for JWT authentication middleware."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config.settings import get_settings
from app.utils.auth import (
    TokenPayload,
    create_access_token,
    get_current_user,
    require_admin,
)


@pytest.fixture()
def valid_token() -> str:
    return create_access_token(sub="user-1", workspace="ws-test")


@pytest.fixture()
def admin_token() -> str:
    return create_access_token(sub="admin-1", workspace="ws-test", role="admin")


@pytest.fixture()
def expired_token() -> str:
    settings = get_settings()
    payload = {
        "sub": "user-1",
        "workspace": "ws-test",
        "role": "user",
        "exp": datetime.now(UTC) - timedelta(hours=1),
        "iat": int(time.time()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


class TestCreateAccessToken:
    def test_returns_decodable_string(self, valid_token: str) -> None:
        settings = get_settings()
        decoded = jwt.decode(
            valid_token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        assert decoded["sub"] == "user-1"

    def test_default_role_is_user(self, valid_token: str) -> None:
        settings = get_settings()
        decoded = jwt.decode(
            valid_token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        assert decoded["role"] == "user"

    def test_custom_role_encoded(self, admin_token: str) -> None:
        settings = get_settings()
        decoded = jwt.decode(
            admin_token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        assert decoded["role"] == "admin"

    def test_expiry_in_future(self, valid_token: str) -> None:
        settings = get_settings()
        decoded = jwt.decode(
            valid_token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        assert decoded["exp"] > time.time()

    def test_custom_expiry_hours(self) -> None:
        token = create_access_token("u", "ws", expires_hours=1)
        settings = get_settings()
        decoded = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        expected = time.time() + 3600
        assert abs(decoded["exp"] - expected) < 5


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_token_returns_payload(self, valid_token: str) -> None:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
        result = await get_current_user(creds)
        assert isinstance(result, TokenPayload)
        assert result.sub == "user-1"

    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self) -> None:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self, expired_token: str) -> None:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds)
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self) -> None:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not.a.valid.jwt")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(creds)
        assert exc.value.status_code == 401


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_admin_user_passes(self, admin_token: str) -> None:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=admin_token)
        user = await get_current_user(creds)
        result = await require_admin(user)
        assert result.role == "admin"

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self, valid_token: str) -> None:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=valid_token)
        user = await get_current_user(creds)
        with pytest.raises(HTTPException) as exc:
            await require_admin(user)
        assert exc.value.status_code == 403
