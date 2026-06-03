"""Tests for app/routes/models.py — Model Discovery & Rotation API."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.utils.auth import create_access_token


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    token = create_access_token(sub="admin", workspace="test-ws", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def async_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestModelCatalog:
    @pytest.mark.asyncio
    async def test_get_catalog_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        rot = Mock()
        rot.get_catalog = AsyncMock(return_value=[])

        with (
            patch("app.utils.rotation_engine.RotationEngine", return_value=rot),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.get(
                "/api/v1/llm/models/catalog",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        rot.get_catalog.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_catalog_with_data(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        data = [{"id": "test/model:free", "name": "Test Model"}]
        rot = Mock()
        rot.get_catalog = AsyncMock(return_value=data)

        with (
            patch("app.utils.rotation_engine.RotationEngine", return_value=rot),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.get(
                "/api/v1/llm/models/catalog",
                headers=auth_headers,
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_catalog_unauthorized(self, async_client: AsyncClient) -> None:
        resp = await async_client.get("/api/v1/llm/models/catalog")
        assert resp.status_code == 401


class TestModelSync:
    @pytest.mark.asyncio
    async def test_sync_models(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        snapshot = Mock()
        snapshot.models_found = 10
        snapshot.models_new = 3
        snapshot.models_removed = 1
        snapshot.models_updated = 6
        snapshot.duration_ms = 2000
        snapshot.error = None

        disc = Mock()
        disc.sync = AsyncMock(return_value=snapshot)

        with (
            patch("app.utils.model_discovery.ModelDiscoveryEngine", return_value=disc),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.post(
                "/api/v1/llm/models/sync",
                headers=auth_headers,
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_unauthorized(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/llm/models/sync")
        assert resp.status_code == 401


class TestModelHealth:
    @pytest.mark.asyncio
    async def test_health_check(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        rot = Mock()
        rot.select_model = AsyncMock(return_value={"id": "test/model:free"})

        bench = Mock()
        bench.test = AsyncMock(return_value=(True, 500.0))
        bench.close = AsyncMock()

        with (
            patch("app.utils.rotation_engine.RotationEngine", return_value=rot),
            patch("app.utils.model_discovery.ModelBenchmark", return_value=bench),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.get(
                "/api/v1/llm/models/health",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        bench.close.assert_awaited_once()


class TestModelDisable:
    @pytest.mark.asyncio
    async def test_disable_model(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        rot = Mock()
        rot.disable_model = AsyncMock()

        with (
            patch("app.utils.rotation_engine.RotationEngine", return_value=rot),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.post(
                "/api/v1/llm/models/test/model%3Afree/disable",
                headers=auth_headers,
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_disable_unauthorized(self, async_client: AsyncClient) -> None:
        resp = await async_client.post("/api/v1/llm/models/test/model%3Afree/disable")
        assert resp.status_code == 401


class TestRotationStats:
    @pytest.mark.asyncio
    async def test_rotation_stats(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        rot = Mock()
        rot.get_rotation_stats = AsyncMock(
            return_value=[{"model_id": "test/model:free", "action": "selected"}]
        )

        with (
            patch("app.utils.rotation_engine.RotationEngine", return_value=rot),
            patch("app.routes.models.create_async_engine"),
            patch("app.routes.models.async_sessionmaker"),
        ):
            resp = await async_client.get(
                "/api/v1/llm/models/rotation/status",
                headers=auth_headers,
            )

        assert resp.status_code == 200
