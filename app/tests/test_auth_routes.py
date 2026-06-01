"""Tests for app/routes/auth.py — register, login, OAuth, me endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config.settings import get_settings
from app.main import app
from app.utils.auth import create_access_token


def _mock_db_session() -> AsyncMock:
    session = AsyncMock()
    session.execute.return_value = Mock()
    session.execute.return_value.fetchone.return_value = None
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Register ────────────────────────────────────────────────────────────────


class TestRegisterEndpoint:
    @pytest.mark.asyncio
    async def test_register_success(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.return_value = None

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.post(
                "/api/v1/auth/register",
                json={"email": "new@example.com", "password": "password123", "name": "New User"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["name"] == "New User"
        assert data["role"] == "user"

    @pytest.mark.asyncio
    async def test_register_admin_email(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.return_value = None

        settings = get_settings()
        original = settings.admin_emails
        settings.admin_emails = "admin@example.com"
        try:
            with patch("app.routes.auth._get_session", return_value=session):
                resp = await async_client.post(
                    "/api/v1/auth/register",
                    json={"email": "admin@example.com", "password": "password123"},
                )
            assert resp.status_code == 200
            assert resp.json()["role"] == "admin"
        finally:
            settings.admin_emails = original

    @pytest.mark.asyncio
    async def test_register_duplicate(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.return_value = Mock(id="existing")

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.post(
                "/api/v1/auth/register",
                json={"email": "dup@example.com", "password": "password123"},
            )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_register_empty_fields(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/auth/register", json={"email": "", "password": ""})
        assert resp.status_code == 422


# ── Login ────────────────────────────────────────────────────────────────────


class TestLoginEndpoint:
    @pytest.mark.asyncio
    async def test_login_empty_fields(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/auth/login", json={"email": "", "password": ""})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_login_success(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        user_row = Mock()
        user_row.id = "u1"
        user_row.email = "u@example.com"
        user_row.password_hash = "salt:hash"
        user_row.name = "U"
        user_row.avatar_url = None
        user_row.role = "user"
        session.execute.return_value.fetchone.return_value = user_row

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("app.routes.auth._verify_password", return_value=True),
        ):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "u@example.com", "password": "pass1234"},
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        user_row = Mock()
        user_row.id = "u1"
        user_row.email = "u@example.com"
        user_row.password_hash = "salt:hash"
        user_row.role = "user"
        session.execute.return_value.fetchone.return_value = user_row

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("app.routes.auth._verify_password", return_value=False),
        ):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "u@example.com", "password": "wrong"},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.return_value = None

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "no@example.com", "password": "pass1234"},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_admin_promotion(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        user_row = Mock()
        user_row.id = "a1"
        user_row.email = "admin@example.com"
        user_row.password_hash = "salt:hash"
        user_row.name = "Admin"
        user_row.avatar_url = None
        user_row.role = "user"
        session.execute.return_value.fetchone.return_value = user_row

        settings = get_settings()
        original = settings.admin_emails
        settings.admin_emails = "admin@example.com"
        try:
            with (
                patch("app.routes.auth._get_session", return_value=session),
                patch("app.routes.auth._verify_password", return_value=True),
            ):
                resp = await async_client.post(
                    "/api/v1/auth/login",
                    json={"email": "admin@example.com", "password": "pass1234"},
                )
            assert resp.status_code == 200
            assert resp.json()["user"]["role"] == "admin"
        finally:
            settings.admin_emails = original


# ── OAuth Login ──────────────────────────────────────────────────────────────


class TestOAuthLoginEndpoint:
    @pytest.mark.asyncio
    async def test_google(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/auth/google/login?redirect_uri=agentos://cb")
        assert resp.status_code == 200
        assert "google" in resp.json()["authorization_url"]

    @pytest.mark.asyncio
    async def test_github(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/auth/github/login")
        assert resp.status_code == 200
        assert "github" in resp.json()["authorization_url"]

    @pytest.mark.asyncio
    async def test_unsupported_provider(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/auth/twitter/login")
        assert resp.status_code == 400


# ── OAuth Callback ───────────────────────────────────────────────────────────


class TestOAuthCallbackEndpoint:
    @pytest.mark.asyncio
    async def test_unsupported_provider(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/auth/twitter/callback", json={"code": "x"})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_existing_social_account(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        social_row = Mock()
        social_row.id = "u1"
        social_row.email = "social@example.com"
        social_row.name = "Social"
        social_row.avatar_url = None
        social_row.role = "user"
        session.execute.return_value.fetchone.return_value = social_row

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            token_resp = Mock(status_code=200)
            token_resp.json.return_value = {"access_token": "oauth-token"}
            userinfo_resp = Mock(status_code=200)
            userinfo_resp.json.return_value = {
                "id": "g123",
                "email": "social@example.com",
                "name": "Social",
            }
            mock_client.post.return_value = token_resp
            mock_client.get.return_value = userinfo_resp

            resp = await async_client.post(
                "/api/v1/auth/google/callback", json={"code": "valid-code"}
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_callback_new_user(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.side_effect = [None, None]

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(
                status_code=200,
                json=lambda: {"access_token": "oauth-token"},
            )
            mock_client.get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "id": "new-g-id",
                    "email": "new@example.com",
                    "name": "New User",
                    "picture": "https://pic",
                },
            )
            resp = await async_client.post(
                "/api/v1/auth/google/callback", json={"code": "new-code"}
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_callback_token_exchange_fails(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(status_code=400, text="bad request")

            resp = await async_client.post(
                "/api/v1/auth/google/callback", json={"code": "bad-code"}
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_userinfo_fetch_fails(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(
                status_code=200, json=lambda: {"access_token": "valid-token"}
            )
            mock_client.get.return_value = Mock(status_code=401, text="unauthorized")

            resp = await async_client.post(
                "/api/v1/auth/google/callback", json={"code": "valid-code"}
            )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_existing_user_by_email(self, async_client: AsyncClient) -> None:
        session = _mock_db_session()
        session.execute.return_value.fetchone.side_effect = [None, Mock(id="existing-uid")]

        with (
            patch("app.routes.auth._get_session", return_value=session),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(
                status_code=200,
                json=lambda: {"access_token": "oauth-token"},
            )
            mock_client.get.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "id": "new-g-id",
                    "email": "existing@example.com",
                    "name": "Existing",
                },
            )
            resp = await async_client.post(
                "/api/v1/auth/google/callback", json={"code": "new-code"}
            )
        assert resp.status_code == 200
        assert "access_token" in resp.json()


# ── Get Me ───────────────────────────────────────────────────────────────────


class TestMeEndpoint:
    @pytest.mark.asyncio
    async def test_get_me_success(self, async_client: AsyncClient) -> None:
        token = create_access_token(sub="uid", workspace="test", role="user")
        session = _mock_db_session()
        user_row = Mock()
        user_row.id = "uid"
        user_row.email = "me@example.com"
        user_row.name = "Me"
        user_row.avatar_url = None
        user_row.role = "user"
        session.execute.return_value.fetchone.return_value = user_row

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"

    @pytest.mark.asyncio
    async def test_get_me_not_found(self, async_client: AsyncClient) -> None:
        token = create_access_token(sub="nope", workspace="test", role="user")
        session = _mock_db_session()
        session.execute.return_value.fetchone.return_value = None

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
