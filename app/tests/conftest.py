from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.config.settings import Settings
from app.utils.logging import get_logger


@pytest.fixture(autouse=True)
def test_settings():
    settings = Settings(
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
    with patch("app.config.settings.get_settings", return_value=settings):
        yield settings





@pytest.fixture
def mock_llm_client():
    with patch("app.agents.base.LLMClient") as mock:
        instance = mock.return_value
        instance.chat = AsyncMock(
            return_value=type("Response", (), {"content": "Mocked LLM response"})()
        )
        yield instance


@pytest.fixture
def mock_hitl_gateway():
    with patch("app.agents.base.get_hitl_gateway") as mock_gateway:
        mock = AsyncMock()
        mock.request_approval = AsyncMock(side_effect=lambda **kw: kw.get("details", {}))
        mock_gateway.return_value = mock
        yield mock


@pytest.fixture
def logger():
    return get_logger("test")


@pytest_asyncio.fixture
async def async_client():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
