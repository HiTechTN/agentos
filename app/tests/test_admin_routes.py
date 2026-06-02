"""Tests for app/routes/admin.py — settings, services, LLM, users."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.utils.auth import create_access_token


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def admin_token() -> str:
    return create_access_token(sub="admin", workspace="test", role="admin")


def user_token() -> str:
    return create_access_token(sub="user", workspace="test", role="user")


# ── Settings ─────────────────────────────────────────────────────────────────


class TestSettingsEndpoint:
    @pytest.mark.asyncio
    async def test_get_settings(self, async_client: AsyncClient) -> None:
        token = admin_token()
        resp = await async_client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data
        assert data["settings"]["log_level"] == "DEBUG"
        assert "***" in data["settings"].get("openrouter_api_key", "")

    @pytest.mark.asyncio
    async def test_get_settings_non_admin_returns_403(self, async_client: AsyncClient) -> None:
        token = user_token()
        resp = await async_client.get(
            "/api/v1/admin/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_settings(self, async_client: AsyncClient) -> None:
        token = admin_token()
        from app.config.settings import get_settings as _gs

        _s = _gs()
        _original_log_level = _s.log_level
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, prefix=".env") as f:
            f.write("LOG_LEVEL=INFO\nTEST_KEY=old_value\n")
            env_path = f.name
        try:
            with patch("app.routes.admin.ENV_FILE", Path(env_path)):
                resp = await async_client.put(
                    "/api/v1/admin/settings",
                    json={"updates": {"TEST_KEY": "new_value"}},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 200
            assert resp.json()["keys"] == ["TEST_KEY"]
            with open(env_path) as f:
                content = f.read()
            assert "TEST_KEY=new_value" in content
        finally:
            _s.log_level = _original_log_level
            os.unlink(env_path)

    @pytest.mark.asyncio
    async def test_update_settings_no_env_file(self, async_client: AsyncClient) -> None:
        token = admin_token()
        with patch("app.routes.admin.ENV_FILE", Mock(exists=Mock(return_value=False))):
            resp = await async_client.put(
                "/api/v1/admin/settings",
                json={"updates": {"KEY": "val"}},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_update_settings_with_comment_lines(self, async_client: AsyncClient) -> None:
        token = admin_token()
        from app.config.settings import get_settings as _gs

        _s = _gs()
        _original_log_level = _s.log_level
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, prefix=".env") as f:
            f.write("# This is a comment\nLOG_LEVEL=INFO\n\n# Another comment\n")
            env_path = f.name
        try:
            with patch("app.routes.admin.ENV_FILE", Path(env_path)):
                resp = await async_client.put(
                    "/api/v1/admin/settings",
                    json={"updates": {"LOG_LEVEL": "ERROR"}},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 200
            assert resp.json()["keys"] == ["LOG_LEVEL"]
        finally:
            _s.log_level = _original_log_level
            os.unlink(env_path)


# ── Services ─────────────────────────────────────────────────────────────────


class TestServicesEndpoint:
    @pytest.mark.asyncio
    async def test_all_services_ok(self, async_client: AsyncClient) -> None:
        token = admin_token()
        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("redis.asyncio.from_url") as mock_redis,
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_redis.return_value = AsyncMock(ping=AsyncMock(), aclose=AsyncMock())
            mock_httpx_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_httpx_client
            mock_httpx_client.get.return_value = Mock(
                status_code=200,
                json=lambda: {"models": [{"name": "qwen2.5"}]},
            )

            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["services"]["database"] == "ok"
        assert data["services"]["redis"] == "ok"
        assert data["services"]["ollama"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_services_db_error(self, async_client: AsyncClient) -> None:
        token = admin_token()

        with patch(
            "app.memory.session.get_session_manager",
            side_effect=Exception("DB connection failed"),
        ):
            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert "error" in resp.json()["services"]["database"]

    @pytest.mark.asyncio
    async def test_services_redis_error(self, async_client: AsyncClient) -> None:
        token = admin_token()

        with (
            patch("app.memory.session.get_session_manager") as mock_sm,
            patch("redis.asyncio.from_url") as mock_from_url,
        ):
            mock_sm.return_value._init_db = AsyncMock()
            mock_sm.return_value._session_factory = Mock(
                return_value=Mock(
                    __aenter__=AsyncMock(return_value=AsyncMock()),
                    __aexit__=AsyncMock(),
                )
            )
            mock_from_url.return_value = AsyncMock(
                ping=AsyncMock(side_effect=Exception("Redis down")),
                aclose=AsyncMock(),
            )
            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert "error" in resp.json()["services"]["redis"]

    @pytest.mark.asyncio
    async def test_services_openrouter_error(self, async_client: AsyncClient) -> None:
        token = admin_token()
        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                Mock(status_code=200, json=lambda: {"models": [{"name": "qwen2.5"}]}),
                Mock(status_code=401, text="Unauthorized"),
            ]

            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["services"]["openrouter"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_services_ollama_http_error(self, async_client: AsyncClient) -> None:
        token = admin_token()
        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                Mock(status_code=500, text="Ollama down"),
                Mock(status_code=500, text="Ollama down fallback"),
                Mock(status_code=200, json=lambda: {"data": []}),
            ]

            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["services"]["ollama"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_services_openrouter_http_error(self, async_client: AsyncClient) -> None:
        token = admin_token()
        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("httpx.AsyncClient") as mock_httpx_cls,
        ):
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [
                Mock(status_code=200, json=lambda: {"models": [{"name": "qwen2.5"}]}),
                Mock(status_code=429, text="Rate limited"),
            ]

            resp = await async_client.get(
                "/api/v1/admin/services",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["services"]["openrouter"]["status"] == "error"


# ── LLM Providers ────────────────────────────────────────────────────────────


class TestLLMProvidersEndpoint:
    @pytest.mark.asyncio
    async def test_list_providers(self, async_client: AsyncClient) -> None:
        token = admin_token()
        resp = await async_client.get(
            "/api/v1/admin/llm/providers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "models_by_type" in data
        assert "current_selections" in data
        assert len(data["models_by_type"]) > 0


# ── LLM Test ─────────────────────────────────────────────────────────────────


class TestLLMTestEndpoint:
    @pytest.mark.asyncio
    async def test_test_model_success(self, async_client: AsyncClient) -> None:
        token = admin_token()

        with patch("httpx.AsyncClient") as mock_httpx_cls:
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(
                status_code=200,
                json=lambda: {
                    "choices": [{"message": {"content": "Hello there!"}}],
                },
            )
            resp = await async_client.post(
                "/api/v1/admin/llm/test",
                json={"model_id": "openai/gpt-4o", "prompt": "Say hi"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Hello" in data["response"]

    @pytest.mark.asyncio
    async def test_test_model_http_error(self, async_client: AsyncClient) -> None:
        token = admin_token()

        with patch("httpx.AsyncClient") as mock_httpx_cls:
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = Mock(
                status_code=429,
                text="Rate limited",
            )
            resp = await async_client.post(
                "/api/v1/admin/llm/test",
                json={"model_id": "bad/model"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_test_model_exception(self, async_client: AsyncClient) -> None:
        token = admin_token()

        with patch("httpx.AsyncClient") as mock_httpx_cls:
            mock_client = AsyncMock()
            mock_httpx_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = Exception("Connection failed")

            resp = await async_client.post(
                "/api/v1/admin/llm/test",
                json={"model_id": "any/model"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "Connection failed" in resp.json()["error"]


# ── LLM Select Model ─────────────────────────────────────────────────────────


class TestLLMSelectModelEndpoint:
    @pytest.mark.asyncio
    async def test_select_model_success(self, async_client: AsyncClient) -> None:
        token = admin_token()
        from app.config.settings import get_settings as _gs

        _s = _gs()
        _original_model = _s.model_for_code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, prefix=".env") as f:
            f.write("model_for_code=old_model\n")
            env_path = f.name
        try:
            with patch("app.routes.admin.ENV_FILE", Path(env_path)):
                resp = await async_client.put(
                    "/api/v1/admin/llm/select-model",
                    json={"work_type": "code_gen", "model_id": "qwen/qwen3-coder:free"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 200
            assert resp.json()["value"] == "qwen/qwen3-coder:free"
        finally:
            _s.model_for_code = _original_model
            os.unlink(env_path)

    @pytest.mark.asyncio
    async def test_select_model_invalid_work_type(self, async_client: AsyncClient) -> None:
        token = admin_token()
        resp = await async_client.put(
            "/api/v1/admin/llm/select-model",
            json={"work_type": "invalid", "model_id": "qwen/qwq-32b-preview"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_select_model_not_in_catalog(self, async_client: AsyncClient) -> None:
        token = admin_token()
        resp = await async_client.put(
            "/api/v1/admin/llm/select-model",
            json={"work_type": "code_gen", "model_id": "nonexistent/model"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_select_model_no_env_file(self, async_client: AsyncClient) -> None:
        token = admin_token()
        with patch("app.routes.admin.ENV_FILE", Mock(exists=Mock(return_value=False))):
            resp = await async_client.put(
                "/api/v1/admin/llm/select-model",
                json={"work_type": "code_gen", "model_id": "qwen/qwen3-coder:free"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_select_model_fallback_config_key(self, async_client: AsyncClient) -> None:
        token = admin_token()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, prefix=".env") as f:
            f.write("model_for_default=old_default\n")
            env_path = f.name
        try:
            with patch("app.routes.admin.ENV_FILE", Path(env_path)):
                resp = await async_client.put(
                    "/api/v1/admin/llm/select-model",
                    json={"work_type": "unknown_type", "model_id": "qwen/qwen3-coder:free"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 400
        finally:
            os.unlink(env_path)

    @pytest.mark.asyncio
    async def test_select_model_appends_new_line(self, async_client: AsyncClient) -> None:
        token = admin_token()
        from app.config.settings import get_settings as _gs

        _s_obj = _gs()
        _orig_code = _s_obj.model_for_code
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, prefix=".env") as f:
            f.write("OTHER_KEY=val\n")
            env_path = f.name
        try:
            with patch("app.routes.admin.ENV_FILE", Path(env_path)):
                resp = await async_client.put(
                    "/api/v1/admin/llm/select-model",
                    json={"work_type": "code_gen", "model_id": "qwen/qwen3-coder:free"},
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert resp.status_code == 200
            with open(env_path) as f:
                content = f.read()
            assert "model_for_code=qwen/qwen3-coder:free" in content
        finally:
            _s_obj.model_for_code = _orig_code
            os.unlink(env_path)


# ── Direct check_services unit tests ───────────────────────────────────────


class TestCheckServicesDirect:
    @pytest.mark.asyncio
    async def test_openrouter_http_error(self) -> None:
        from app.routes.admin import check_services

        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("app.routes.admin.httpx.AsyncClient") as mock_cls,
        ):
            mock_inst = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_inst

            async def _get_side_effect(*a: Any, **kw: Any) -> Mock:
                if "openrouter" in str(a[0]) if a else "":
                    return Mock(status_code=429, text="Rate limited")
                return Mock(status_code=200, json=lambda: {"models": [{"name": "qwen2.5"}]})

            mock_inst.get.side_effect = _get_side_effect
            result = await check_services(Mock())
            assert result["services"]["openrouter"]["status"] == "error"
            assert "Rate limited" in result["services"]["openrouter"]["detail"]

    @pytest.mark.asyncio
    async def test_openrouter_exception(self) -> None:
        from app.routes.admin import check_services

        mock_session = AsyncMock()
        mock_session.execute.return_value = Mock()

        with (
            patch(
                "app.memory.session.get_session_manager",
                return_value=Mock(
                    _init_db=AsyncMock(),
                    _session_factory=Mock(
                        return_value=Mock(
                            __aenter__=AsyncMock(return_value=mock_session),
                            __aexit__=AsyncMock(),
                        )
                    ),
                ),
            ),
            patch("app.routes.admin.httpx.AsyncClient") as mock_cls,
        ):
            mock_inst = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_inst
            mock_inst.get.side_effect = [
                Mock(status_code=200, json=lambda: {"models": [{"name": "qwen2.5"}]}),
                Exception("Connection refused"),
            ]
            result = await check_services(Mock())
            assert "Connection refused" in result["services"]["openrouter"]["detail"]


# ── Users ────────────────────────────────────────────────────────────────────


class TestAdminUsersEndpoint:
    @pytest.mark.asyncio
    async def test_list_users(self, async_client: AsyncClient) -> None:
        token = admin_token()
        session = AsyncMock()
        session.execute.return_value = Mock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        user_row = Mock()
        user_row.id = "uid"
        user_row.email = "test@example.com"
        user_row.name = "Test"
        user_row.avatar_url = None
        user_row.role = "admin"
        user_row.email_verified = True
        user_row.created_at = Mock(
            isoformat=lambda: "2026-01-01T00:00:00",
        )
        session.execute.return_value.fetchall.return_value = [user_row]

        with patch("app.routes.auth._get_session", return_value=session):
            resp = await async_client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["users"][0]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_list_users_non_admin(self, async_client: AsyncClient) -> None:
        token = user_token()
        resp = await async_client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
