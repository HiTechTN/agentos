"""Tests for SmartLLMRouter and WorkType detection."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.llm_router import (
    FREE_MODELS,
    FreeModel,
    SmartLLMRouter,
    WorkType,
    _is_available,
    _record_request,
    _usage,
    detect_work_type,
)


@pytest.fixture(autouse=True)
def clear_usage() -> None:
    _usage.clear()


class TestDetectWorkType:
    def test_code_keywords(self) -> None:
        assert detect_work_type("scaffold a FastAPI endpoint") == WorkType.CODE_GEN

    def test_agent_code_agent(self) -> None:
        assert detect_work_type("implement a feature", "@DevAgent") == WorkType.CODE_AGENT

    def test_planner_agent(self) -> None:
        assert detect_work_type("create a plan", "@Planner") == WorkType.REASONING

    def test_debug_keywords(self) -> None:
        assert detect_work_type("debug this error traceback") == WorkType.DEBUG

    def test_content_keywords(self) -> None:
        assert detect_work_type("write an SEO blog post") == WorkType.CONTENT

    def test_multimodal_keywords(self) -> None:
        assert detect_work_type("analyze this image screenshot") == WorkType.MULTIMODAL

    def test_fast_keywords(self) -> None:
        assert detect_work_type("quickly summarize this text") == WorkType.FAST

    def test_general_fallback(self) -> None:
        assert detect_work_type("do something") == WorkType.GENERAL

    def test_content_agent_name(self) -> None:
        assert detect_work_type("task", "@ContentAgent") == WorkType.CONTENT

    def test_debugger_agent_name(self) -> None:
        assert detect_work_type("task", "@Debugger") == WorkType.DEBUG

    def test_commerce_agent_name(self) -> None:
        assert detect_work_type("task", "@CommerceAgent") == WorkType.REASONING

    def test_explorer_agent_name(self) -> None:
        assert detect_work_type("task", "@Explorer") == WorkType.FAST

    def test_verifier_agent_name(self) -> None:
        assert detect_work_type("task", "@Verifier") == WorkType.CODE_GEN

    def test_codereviewer_agent_name(self) -> None:
        assert detect_work_type("task", "@CodeReviewer") == WorkType.CODE_GEN

    def test_marketing_agent_name(self) -> None:
        assert detect_work_type("task", "@MarketingAgent") == WorkType.CONTENT


class TestFreeModelsCatalogue:
    def test_all_work_types_have_models(self) -> None:
        for wt in WorkType:
            assert wt in FREE_MODELS, f"Missing models for {wt}"
            assert len(FREE_MODELS[wt]) >= 2

    def test_code_gen_models_have_tools(self) -> None:
        assert FREE_MODELS[WorkType.CODE_GEN][0].supports_tools

    def test_multimodal_models_have_vision(self) -> None:
        assert FREE_MODELS[WorkType.MULTIMODAL][0].supports_vision

    def test_model_ids_end_with_free(self) -> None:
        for models in FREE_MODELS.values():
            for m in models:
                if m.id != "openrouter/free":
                    assert m.id.endswith(":free"), f"{m.id} should end with :free"

    def test_debug_has_deepseek(self) -> None:
        ids = [m.id for m in FREE_MODELS[WorkType.DEBUG]]
        assert any("deepseek" in i for i in ids)


class TestModelFields:
    def test_model_has_required_fields(self) -> None:
        m = FreeModel(id="t:free", name="Test", context_window=128_000)
        assert m.id == "t:free"
        assert m.name == "Test"
        assert m.context_window == 128_000
        assert m.supports_tools is False
        assert m.supports_vision is False

    def test_model_default_rate_limits(self) -> None:
        m = FreeModel(id="t:free", name="Test", context_window=128_000)
        assert m.req_per_min == 20
        assert m.req_per_day == 200


class TestRateLimitTracking:
    @pytest.mark.asyncio
    async def test_model_available_by_default(self) -> None:
        model = FreeModel(id="test/model:free", name="Test", context_window=128_000)
        assert await _is_available(model)

    @pytest.mark.asyncio
    async def test_model_unavailable_when_rate_limited(self) -> None:
        model = FreeModel(
            id="test/model:free",
            name="Test",
            context_window=128_000,
            req_per_min=5,
            req_per_day=200,
        )
        from app.utils.llm_router import _ModelUsage, _usage_lock

        async with _usage_lock:
            _usage["test/model:free"] = _ModelUsage(requests_this_minute=4)
        assert not await _is_available(model)

    @pytest.mark.asyncio
    async def test_model_banned_after_errors(self) -> None:
        model = FreeModel(id="ban-test:free", name="Test", context_window=128_000)
        await _record_request("ban-test:free", success=False)
        await _record_request("ban-test:free", success=False)
        await _record_request("ban-test:free", success=False)
        assert not await _is_available(model)

    @pytest.mark.asyncio
    async def test_success_resets_errors(self) -> None:
        from app.utils.llm_router import _ModelUsage, _usage_lock

        async with _usage_lock:
            _usage["ok-model:free"] = _ModelUsage(consecutive_errors=2)
        await _record_request("ok-model:free", success=True)
        async with _usage_lock:
            assert _usage["ok-model:free"].consecutive_errors == 0

    @pytest.mark.asyncio
    async def test_minute_window_resets(self) -> None:
        model = FreeModel(id="window-test:free", name="Test", context_window=128_000)
        from app.utils.llm_router import _ModelUsage, _usage_lock

        async with _usage_lock:
            _usage["window-test:free"] = _ModelUsage(
                requests_this_minute=19,
                minute_window_start=time.time() - 120,
            )
        assert await _is_available(model)

    @pytest.mark.asyncio
    async def test_day_window_resets(self) -> None:
        model = FreeModel(id="day-test:free", name="Test", context_window=128_000)
        from app.utils.llm_router import _ModelUsage, _usage_lock

        async with _usage_lock:
            _usage["day-test:free"] = _ModelUsage(
                requests_today=195,
                day_window_start=time.time() - 172_800,
            )
        assert await _is_available(model)


class TestSmartLLMRouter:
    @pytest.fixture()
    def router(self) -> SmartLLMRouter:
        return SmartLLMRouter()

    @pytest.mark.asyncio
    async def test_select_model_returns_model(self, router: SmartLLMRouter) -> None:
        model = await router.select_model(WorkType.CODE_GEN)
        assert model is not None
        assert ":free" in model.id or model.id == "openrouter/free"

    @pytest.mark.asyncio
    async def test_select_model_respects_tool_requirement(self, router: SmartLLMRouter) -> None:
        model = await router.select_model(WorkType.FAST, requires_tools=True)
        assert model is None or model.supports_tools

    @pytest.mark.asyncio
    async def test_select_model_respects_vision(self, router: SmartLLMRouter) -> None:
        model = await router.select_model(WorkType.FAST, requires_vision=True)
        assert model is None or model.supports_vision

    @pytest.mark.asyncio
    async def test_complete_success(self, router: SmartLLMRouter) -> None:
        with patch.object(router, "_call_openrouter", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "def hello(): pass"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
            result = await router.complete(
                prompt="Write a hello function",
                agent_name="@DevAgent",
            )
        assert "choices" in result
        assert result["_router"]["source"] == "openrouter_free"

    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self, router: SmartLLMRouter) -> None:
        with patch.object(router, "_call_openrouter", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }
            result = await router.complete(
                prompt="hi",
                system="You are helpful",
            )
        assert result["_router"]["source"] == "openrouter_free"

    @pytest.mark.asyncio
    async def test_complete_with_messages(self, router: SmartLLMRouter) -> None:
        with patch.object(router, "_call_openrouter", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }
            result = await router.complete(
                messages=[{"role": "user", "content": "hello"}],
            )
        assert result["_router"]["source"] == "openrouter_free"

    @pytest.mark.asyncio
    async def test_complete_falls_back_to_ollama(self, router: SmartLLMRouter) -> None:
        import httpx

        with patch.object(
            router,
            "_call_openrouter",
            side_effect=httpx.HTTPStatusError(
                "429", request=MagicMock(), response=MagicMock(status_code=429)
            ),
        ):
            with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = {
                    "choices": [{"message": {"content": "fallback"}}],
                    "usage": {},
                    "_router": {
                        "source": "ollama_fallback",
                        "model_used": "qwen2.5-coder:7b",
                        "model_name": "Ollama/qwen2.5-coder:7b",
                        "work_type": "unknown",
                    },
                }
                result = await router.complete(
                    prompt="test",
                    work_type=WorkType.FAST,
                )
                assert result["_router"]["source"] == "ollama_fallback"

    @pytest.mark.asyncio
    async def test_complete_falls_back_after_multiple_429(
        self,
        router: SmartLLMRouter,
    ) -> None:
        import httpx

        with patch.object(
            router,
            "_call_openrouter",
            side_effect=httpx.HTTPStatusError(
                "429", request=MagicMock(), response=MagicMock(status_code=429)
            ),
        ):
            with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = {
                    "choices": [{"message": {"content": "fallback"}}],
                    "usage": {},
                    "_router": {"source": "ollama_fallback"},
                }
                result = await router.complete(
                    prompt="test",
                )
                assert result["_router"]["source"] == "ollama_fallback"

    @pytest.mark.asyncio
    async def test_complete_timeout_triggers_fallback(
        self,
        router: SmartLLMRouter,
    ) -> None:
        import httpx

        with patch.object(
            router,
            "_call_openrouter",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = {
                    "choices": [{"message": {"content": "fallback"}}],
                    "usage": {},
                    "_router": {"source": "ollama_fallback"},
                }
                result = await router.complete(prompt="test")
                assert result["_router"]["source"] == "ollama_fallback"

    @pytest.mark.asyncio
    async def test_ollama_fallback_returns_degraded(self, router: SmartLLMRouter) -> None:
        import httpx

        with patch.object(
            router,
            "_call_openrouter",
            side_effect=httpx.HTTPStatusError(
                "429", request=MagicMock(), response=MagicMock(status_code=429)
            ),
        ):
            result = await router.complete(prompt="test")
            assert result["_router"]["source"] == "degraded"
            assert "unavailable" in result["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_get_usage_report(self, router: SmartLLMRouter) -> None:
        report = await router.get_usage_report()
        assert isinstance(report, dict)

    @pytest.mark.asyncio
    async def test_get_usage_report_after_request(self, router: SmartLLMRouter) -> None:
        with patch.object(router, "_call_openrouter", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }
            await router.complete(prompt="test")
        report = await router.get_usage_report()
        assert len(report) > 0

    @pytest.mark.asyncio
    async def test_close(self, router: SmartLLMRouter) -> None:
        await router.close()

    @pytest.mark.asyncio
    async def test_select_model_no_available_returns_none(
        self,
        router: SmartLLMRouter,
    ) -> None:
        from app.utils.llm_router import _ModelUsage, _usage_lock

        # Ban all FAST models
        for banned in FREE_MODELS[WorkType.FAST]:
            async with _usage_lock:
                _usage[banned.id] = _ModelUsage(
                    consecutive_errors=3,
                    is_banned_until=time.time() + 9999,
                )
        selected: FreeModel | None = await router.select_model(WorkType.FAST)
        assert selected is None


class TestRouterEndpoints:
    @pytest.mark.asyncio
    async def test_router_status_endpoint(self, async_client: Any) -> None:
        resp = await async_client.get("/api/v1/llm/router/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_router_models_endpoint(self, async_client: Any) -> None:
        resp = await async_client.get("/api/v1/llm/router/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "code_gen" in data
        assert "debug" in data


class TestApiClientsIntegration:
    @pytest.mark.asyncio
    async def test_llm_complete_function(self) -> None:
        from app.utils.api_clients import llm_complete

        with patch(
            "app.utils.api_clients.smart_router.complete",
            new_callable=AsyncMock,
        ) as mock_complete:
            mock_complete.return_value = {
                "choices": [{"message": {"content": "hello"}}],
                "_router": {"source": "openrouter_free"},
            }
            result = await llm_complete(
                prompt="say hi",
                agent_name="@DevAgent",
            )
            assert result["_router"]["source"] == "openrouter_free"


class TestGetClient:
    @pytest.mark.asyncio
    async def test_get_client_creates_new(self) -> None:
        router = SmartLLMRouter()
        assert router._client is None
        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.is_closed = False
            mock_client.return_value = instance
            client = await router._get_client()
        assert client is not None

    @pytest.mark.asyncio
    async def test_get_client_reuses(self) -> None:
        router = SmartLLMRouter()
        with patch("httpx.AsyncClient") as mock_client:
            instance = MagicMock()
            instance.is_closed = False
            mock_client.return_value = instance
            first = await router._get_client()
            second = await router._get_client()
        assert first is second


class TestCallOpenRouter:
    @pytest.mark.asyncio
    async def test_call_openrouter_success(self) -> None:
        router = SmartLLMRouter()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"choices": [], "usage": {}})
        with patch.object(router, "_get_client") as mock_get:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_client
            result = await router._call_openrouter(
                model_id="test:free",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.5,
                max_tokens=100,
            )
        assert result == {"choices": [], "usage": {}}


class TestCallOllamaSuccess:
    @pytest.mark.asyncio
    async def test_call_ollama_returns_formatted(self) -> None:
        router = SmartLLMRouter()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"message": {"content": "ollama response"}})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client
            result = await router._call_ollama(
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7,
                max_tokens=100,
            )
        assert result["_router"]["source"] == "ollama_fallback"
        assert result["choices"][0]["message"]["content"] == "ollama response"


class TestCloseWithClient:
    @pytest.mark.asyncio
    async def test_close_existing_client(self) -> None:
        router = SmartLLMRouter()
        client = MagicMock()
        client.is_closed = False
        client.aclose = AsyncMock()
        router._client = client
        await router.close()
        client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_client(self) -> None:
        router = SmartLLMRouter()
        router._client = None
        await router.close()


class TestSelectModelFilters:
    @pytest.mark.asyncio
    async def test_requires_tools_skips_non_tool_models(self) -> None:
        router = SmartLLMRouter()
        model = await router.select_model(WorkType.GENERAL, requires_tools=True)
        assert model is None or model.supports_tools

    @pytest.mark.asyncio
    async def test_min_context_filters(self) -> None:
        router = SmartLLMRouter()
        model = await router.select_model(
            WorkType.FAST,
            min_context=1_000_000,
        )
        if model is not None:
            assert model.context_window >= 1_000_000

    @pytest.mark.asyncio
    async def test_requires_vision_skip(self) -> None:
        router = SmartLLMRouter()
        model = await router.select_model(WorkType.DEBUG, requires_vision=True)
        assert model is None or model.supports_vision


class TestCompleteFilters:
    @pytest.mark.asyncio
    async def test_complete_requires_vision_filters_models(self) -> None:
        router = SmartLLMRouter()
        # DEBUG models don't support vision, so requires_vision=True will
        # skip them and fall through to Ollama
        with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {
                "choices": [{"message": {"content": "fallback"}}],
                "_router": {"source": "ollama_fallback"},
            }
            result = await router.complete(
                prompt="test",
                work_type=WorkType.DEBUG,
                requires_vision=True,
            )
            assert result["_router"]["source"] == "ollama_fallback"

    @pytest.mark.asyncio
    async def test_complete_requires_tools_skips_non_tool(self) -> None:
        router = SmartLLMRouter()
        # GENERAL[0] = Nemotron 70B which doesn't support tools
        # requires_tools=True will skip it, then fall through
        with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {
                "choices": [{"message": {"content": "fallback"}}],
                "_router": {"source": "ollama_fallback"},
            }
            result = await router.complete(
                prompt="test",
                work_type=WorkType.GENERAL,
                requires_tools=True,
            )
            assert result["_router"]["source"] == "ollama_fallback"

    @pytest.mark.asyncio
    async def test_complete_skips_unavailable_models(self) -> None:
        router = SmartLLMRouter()
        from app.utils.llm_router import _ModelUsage, _usage_lock

        # Ban all GENERAL models so none are available
        for model in FREE_MODELS[WorkType.GENERAL]:
            async with _usage_lock:
                _usage[model.id] = _ModelUsage(
                    consecutive_errors=3,
                    is_banned_until=time.time() + 9999,
                )
        with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
            mock_ollama.return_value = {
                "choices": [{"message": {"content": "fallback"}}],
                "_router": {"source": "ollama_fallback"},
            }
            result = await router.complete(
                prompt="test",
                work_type=WorkType.GENERAL,
            )
            assert result["_router"]["source"] == "ollama_fallback"


class TestCompleteNon429Error:
    @pytest.mark.asyncio
    async def test_complete_non_429_error(self) -> None:
        import httpx

        router = SmartLLMRouter()
        error_resp = MagicMock()
        error_resp.status_code = 500
        with patch.object(
            router,
            "_call_openrouter",
            side_effect=httpx.HTTPStatusError(
                "500",
                request=MagicMock(),
                response=error_resp,
            ),
        ):
            with patch.object(router, "_call_ollama", new_callable=AsyncMock) as mock_ollama:
                mock_ollama.return_value = {
                    "choices": [{"message": {"content": "fallback"}}],
                    "_router": {"source": "ollama_fallback"},
                }
                result = await router.complete(prompt="test")
                assert result["_router"]["source"] == "ollama_fallback"


class TestGetUsageReportAfterError:
    @pytest.mark.asyncio
    async def test_report_includes_banned_model(self) -> None:
        router = SmartLLMRouter()
        from app.utils.llm_router import _ModelUsage, _usage_lock

        async with _usage_lock:
            _usage["banned:free"] = _ModelUsage(
                consecutive_errors=3,
                is_banned_until=time.time() + 9999,
            )
        report = await router.get_usage_report()
        assert report["banned:free"]["is_banned"] is True


class TestDynamicModels:
    @pytest.fixture()
    def router(self) -> SmartLLMRouter:
        return SmartLLMRouter()

    def test_get_candidates_returns_hardcoded_when_no_dynamic(self, router: SmartLLMRouter) -> None:
        router._dynamic_models = None
        candidates = router._get_candidates(WorkType.CODE_GEN)
        assert len(candidates) >= 2
        assert all(isinstance(m, FreeModel) for m in candidates)

    def test_get_candidates_uses_dynamic_first(self, router: SmartLLMRouter) -> None:
        dyn_model = FreeModel(id="dyn/test:free", name="Dynamic", context_window=128_000)
        router._dynamic_models = {WorkType.CODE_GEN: [dyn_model]}
        candidates = router._get_candidates(WorkType.CODE_GEN)
        assert candidates[0].id == "dyn/test:free"
        assert len(candidates) > 1

    def test_get_candidates_deduplicates(self, router: SmartLLMRouter) -> None:
        # Same id as a hardcoded model
        hardcoded_id = FREE_MODELS[WorkType.FAST][0].id
        dyn_model = FreeModel(id=hardcoded_id, name="Dynamic", context_window=128_000)
        router._dynamic_models = {WorkType.FAST: [dyn_model]}
        candidates = router._get_candidates(WorkType.FAST)
        ids = [m.id for m in candidates]
        assert ids.count(hardcoded_id) == 1

    def test_get_candidates_empty_dict_falls_back(self, router: SmartLLMRouter) -> None:
        router._dynamic_models = {}
        candidates = router._get_candidates(WorkType.FAST)
        assert len(candidates) >= 2

    def test_get_candidates_fallback_work_type(self, router: SmartLLMRouter) -> None:
        candidates = router._get_candidates(WorkType.GENERAL)
        assert len(candidates) >= 1

    @pytest.mark.asyncio
    async def test_reload_dynamic_models_success(self, router: SmartLLMRouter) -> None:
        mock_row = (
            "test/model-a:free",
            "Model A",
            128_000,
            True,
            False,
            False,
            20,
            200,
            "code_gen",
            '["code_gen","debug"]',
        )

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine),
            patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=lambda: mock_session),
        ):
            await router._reload_dynamic_models()

        assert router._dynamic_models is not None
        assert len(router._dynamic_models[WorkType.CODE_GEN]) == 1
        assert router._dynamic_models[WorkType.CODE_GEN][0].id == "test/model-a:free"
        # Also registered under debug
        assert router._dynamic_models[WorkType.DEBUG][0].id == "test/model-a:free"

    @pytest.mark.asyncio
    async def test_reload_dynamic_models_db_error(self, router: SmartLLMRouter) -> None:
        router._dynamic_models = None
        with (
            patch(
                "sqlalchemy.ext.asyncio.create_async_engine",
                side_effect=RuntimeError("db down"),
            ),
        ):
            await router._reload_dynamic_models()
        # Falls back to empty dict, not None
        assert router._dynamic_models == {}

    @pytest.mark.asyncio
    async def test_reload_dynamic_models_empty(self, router: SmartLLMRouter) -> None:
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=mock_engine),
            patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=lambda: mock_session),
        ):
            await router._reload_dynamic_models()

        assert router._dynamic_models is not None
        # All work types should have empty lists
        for wt in WorkType:
            assert router._dynamic_models[wt] == []

    @pytest.mark.asyncio
    async def test_select_model_uses_dynamic_first(self, router: SmartLLMRouter) -> None:
        dyn_model = FreeModel(id="dyn/first:free", name="Dynamic First", context_window=128_000)
        router._dynamic_models = {WorkType.FAST: [dyn_model]}
        model = await router.select_model(WorkType.FAST)
        assert model is not None
        assert model.id == "dyn/first:free"

    @pytest.mark.asyncio
    async def test_complete_uses_dynamic_models(self, router: SmartLLMRouter) -> None:
        dyn_model = FreeModel(id="dyn/test:free", name="Dynamic Test", context_window=128_000)
        router._dynamic_models = {WorkType.DEBUG: [dyn_model]}
        with patch.object(router, "_call_openrouter", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {},
            }
            result = await router.complete(
                prompt="debug this",
                work_type=WorkType.DEBUG,
            )
        assert result["_router"]["source"] == "openrouter_free"
        # Should have called with the dynamic model
        mock_call.assert_called_once()
        args = mock_call.call_args[1]
        assert args["model_id"] == "dyn/test:free"
