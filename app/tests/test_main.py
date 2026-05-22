"""Tests for app/main.py — API endpoints."""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """GET /health — returns dependency statuses."""

    @pytest.mark.asyncio
    async def test_returns_200(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_contains_api_status(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        data = resp.json()
        assert data["api"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_contains_all_service_keys(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/health")
        data = resp.json()
        for key in ("database", "redis", "ollama"):
            assert key in data


class TestDeployEndpoint:
    """GET /deploy — deployment assistant HTML page."""

    @pytest.mark.asyncio
    async def test_returns_html(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/deploy")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")


class TestMetricsEndpoint:
    """GET /metrics — Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_returns_plaintext(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")


class TestOptionalAuthMiddleware:
    """The optional auth middleware sets request.state.user but never rejects
    requests — it silently falls back to user=None on invalid/missing tokens."""

    @pytest.mark.asyncio
    async def test_get_route_works_without_auth(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/rules")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_route_works_with_bad_token(self, async_client: AsyncClient) -> None:
        resp = await async_client.get(
            "/api/v1/rules",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_other_route_without_auth(
        self, async_client: AsyncClient
    ) -> None:
        resp = await async_client.get("/api/v1/workspaces")
        assert resp.status_code == 200


class TestGetCurrentUserDirect:
    """Direct tests of get_current_user — the auth dependency that raises 401."""

    @pytest.mark.asyncio
    async def test_raises_401_without_credentials(self) -> None:
        from app.utils.auth import get_current_user

        with pytest.raises(Exception) as exc_info:
            await get_current_user(None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_raises_401_with_invalid_token(self) -> None:
        from fastapi.security import HTTPAuthorizationCredentials

        from app.utils.auth import get_current_user

        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalidtoken"
        )
        with pytest.raises(Exception) as exc_info:
            await get_current_user(creds)
        assert exc_info.value.status_code == 401
