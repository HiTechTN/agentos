"""Test fixtures for AgentOS — early patching of settings."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.config.settings import Settings

# Patch get_settings at module load time (before any test module is imported)
_test_settings = Settings(
    log_level="DEBUG",
    project_id="test-project",
    environment="test",
    openrouter_api_key="sk-test-key",
    ollama_base_url="http://test-ollama:11434",
    redis_url="memory://",
    postgres_host="localhost",
    postgres_user="test",
    postgres_password="test",
    postgres_db="test",
    scheduler_enabled=False,
    sandbox_enabled=False,
    hitl_mode="webhook_and_cli",
    hitl_timeout=0,
    ollama_fallback_model="qwen2.5",
)
_patcher = patch("app.config.settings.get_settings", return_value=_test_settings)
_patcher.start()

# In-memory Redis mock using dict
_redis_store: dict[str, Any] = {}


async def _mock_get(key: str) -> Any:
    return _redis_store.get(key)


async def _mock_setex(key: str, ttl: int, value: Any) -> None:
    _redis_store[key] = value


async def _mock_delete(*keys: str) -> int:
    count = 0
    for key in keys:
        count += _redis_store.pop(key, None) is not None
    return count


async def _mock_keys(pattern: str) -> list[str]:
    prefix = pattern.rstrip("*")
    return [k for k in _redis_store if k.startswith(prefix)]


async def _mock_flushdb() -> None:
    _redis_store.clear()


_mock_redis = AsyncMock()
_mock_redis.get = _mock_get
_mock_redis.setex = _mock_setex
_mock_redis.delete = _mock_delete
_mock_redis.keys = _mock_keys
_mock_redis.flushdb = _mock_flushdb
_mock_redis.ping = AsyncMock(return_value=True)
_mock_redis.aclose = AsyncMock(return_value=None)

_redis_patcher = patch("redis.asyncio.from_url", return_value=_mock_redis)
_redis_patcher.start()

_cache_redis_patcher = patch(
    "app.memory.cache.aioredis.from_url",
    return_value=_mock_redis,
)
_cache_redis_patcher.start()


@pytest.fixture(autouse=True)
def test_settings() -> Generator[Settings]:
    yield _test_settings


@pytest.fixture
def mock_llm_client() -> Generator[Any]:
    with patch("app.agents.base.LLMClient") as mock:
        instance = mock.return_value
        instance.chat = AsyncMock(
            return_value=type("Response", (), {"content": "Mocked LLM response"})()
        )
        yield instance


@pytest.fixture
def mock_hitl_gateway() -> Generator[Any]:
    with patch("app.agents.base.get_hitl_gateway") as mock_gateway:
        mock = AsyncMock()
        mock.request_approval = AsyncMock(side_effect=lambda **kw: kw.get("details", {}))
        mock_gateway.return_value = mock
        yield mock


@pytest.fixture
def logger() -> Any:
    from app.utils.logging import get_logger

    return get_logger("test")


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[Any]:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def test_client() -> Any:
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    from app.utils.auth import create_access_token

    token = create_access_token(sub="test-user", workspace="test-ws")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    from app.utils.auth import create_access_token

    token = create_access_token(sub="admin", workspace="test-ws", role="admin")
    return {"Authorization": f"Bearer {token}"}
