import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# File 1: app/utils/hitl_gateway.py (79% → 100%)
#   Gaps: 47-53, 80, 106, 133-139, 142-144
# =============================================================================

class TestHITLGatewayRemainingBranches:

    @pytest.mark.asyncio
    async def test_wait_with_timeout(self):
        from app.utils.hitl_gateway import PendingApproval
        pa = PendingApproval("s", "dev", "deploy", {"target": "staging"})
        pa.approve()
        result = await pa.wait(timeout=5)
        assert result == {"target": "staging"}

    @pytest.mark.asyncio
    async def test_wait_rejected_raises(self):
        from app.utils.hitl_gateway import HITLRejectedError, PendingApproval
        pa = PendingApproval("s", "dev", "deploy", {"target": "staging"})
        pa.reject("not now")
        with pytest.raises(HITLRejectedError, match="rejected"):
            await pa.wait()

    @pytest.mark.asyncio
    async def test_request_approval_with_timeout_creates_auto_reject(self):
        from app.utils.hitl_gateway import HITLGateway, HITLPendingError
        gw = HITLGateway()
        with patch.object(gw, "_auto_reject", AsyncMock()) as mock_ar:
            with pytest.raises(HITLPendingError):
                await gw.request_approval("s", "dev", "deploy", {}, timeout=10)
            mock_ar.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_approval_no_timeout_no_auto_reject(self):
        from app.utils.hitl_gateway import HITLGateway, HITLPendingError
        gw = HITLGateway()
        with patch.object(gw, "_auto_reject", AsyncMock()) as mock_ar:
            with pytest.raises(HITLPendingError):
                await gw.request_approval("s", "dev", "deploy", {}, timeout=0)
            mock_ar.assert_not_called()

    def test_reject_unknown_approval_raises(self):
        from app.utils.hitl_gateway import HITLGateway
        gw = HITLGateway()
        with pytest.raises(ValueError, match="not found"):
            gw.reject("nonexistent")

    @pytest.mark.asyncio
    async def test_cli_confirm_approve(self):
        from app.utils.hitl_gateway import HITLGateway
        gw = HITLGateway()
        with (
            patch("rich.console.Console"),
            patch("rich.prompt.Confirm") as mock_confirm,
        ):
            mock_confirm.ask = MagicMock(return_value=True)
            result = await gw.cli_confirm("deploy", {"env": "prod"})
            assert result is True

    @pytest.mark.asyncio
    async def test_cli_confirm_reject(self):
        from app.utils.hitl_gateway import HITLGateway
        gw = HITLGateway()
        with (
            patch("rich.console.Console"),
            patch("rich.prompt.Confirm") as mock_confirm,
        ):
            mock_confirm.ask = MagicMock(return_value=False)
            result = await gw.cli_confirm("deploy", {"env": "prod"})
            assert result is False

    @pytest.mark.asyncio
    async def test_auto_reject_pending(self):
        from app.utils.hitl_gateway import HITLGateway, PendingApproval
        gw = HITLGateway()
        pa = PendingApproval("s", "dev", "deploy", {})
        pa._event.set = MagicMock()
        with patch("asyncio.sleep", AsyncMock()):
            await gw._auto_reject(pa, 1)
        assert pa.status == "rejected"

    @pytest.mark.asyncio
    async def test_auto_reject_already_approved(self):
        from app.utils.hitl_gateway import HITLGateway, PendingApproval
        gw = HITLGateway()
        pa = PendingApproval("s", "dev", "deploy", {})
        pa.approve()
        with patch("asyncio.sleep", AsyncMock()):
            await gw._auto_reject(pa, 1)
        assert pa.status == "approved"

    @pytest.mark.asyncio
    async def test_wait_zero_timeout_no_wait_for(self):
        from app.utils.hitl_gateway import PendingApproval
        pa = PendingApproval("s", "dev", "deploy", {})
        pa._event.set()
        result = await pa.wait(timeout=0)
        assert result == {}


# =============================================================================
# File 2: app/utils/logging.py (86% → 100%)
#   Gaps: 13, 15, 40-42, 100-101, 122-123, 142-143
# =============================================================================

class TestLoggingRemainingBranches:

    def test_mask_sensitive_nested_dict(self):
        from app.utils.logging import _mask_sensitive
        data = {"nested": {"api_key": "sk-123", "name": "test"}}
        result = _mask_sensitive(data)
        assert result["nested"]["api_key"] == "***MASKED***"
        assert result["nested"]["name"] == "test"

    def test_mask_sensitive_key_with_substring(self):
        from app.utils.logging import _mask_sensitive
        data = {"my_api_key": "secret123"}
        result = _mask_sensitive(data)
        assert result["my_api_key"] == "***MASKED***"

    @pytest.mark.asyncio
    async def test_broadcast_subscriber_exception(self):
        from app.utils.logging import LogBroadcaster
        b = LogBroadcaster()
        bad_cb = MagicMock(side_effect=Exception("subscriber error"))
        b.subscribe(bad_cb)
        await b.broadcast({"msg": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_async_subscriber_called(self):
        from app.utils.logging import LogBroadcaster
        b = LogBroadcaster()
        cb = AsyncMock()
        b.subscribe(cb)
        await b.broadcast({"msg": "test"})
        cb.assert_awaited_once_with({"msg": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_sync_subscriber(self):
        from app.utils.logging import LogBroadcaster
        b = LogBroadcaster()
        results = []
        def sync_cb(record):
            results.append(record)
        b.subscribe(sync_cb)
        await b.broadcast({"msg": "sync"})
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_log_action_broadcast_exception(self):
        from app.utils.logging import get_logger
        logger = get_logger("test_log_action_exc")
        with patch("asyncio.ensure_future", side_effect=Exception("broadcast fail")):
            result = logger.log_action("agent1", "test_action", "ok")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_log_error_broadcast_exception(self):
        from app.utils.logging import get_logger
        logger = get_logger("test_log_error_exc")
        with patch("asyncio.ensure_future", side_effect=Exception("broadcast fail")):
            result = logger.log_error("agent1", "test_action", "error msg")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_log_warn_broadcast_exception(self):
        from app.utils.logging import get_logger
        logger = get_logger("test_log_warn_exc")
        with patch("asyncio.ensure_future", side_effect=Exception("broadcast fail")):
            result = logger.log_warn("agent1", "test_action", "warn msg")
        assert isinstance(result, str)

    def test_unsubscribe_removes_callback(self):
        from app.utils.logging import LogBroadcaster
        b = LogBroadcaster()
        cb = MagicMock()
        b.subscribe(cb)
        assert len(b._subscribers) == 1
        b.unsubscribe(cb)
        assert len(b._subscribers) == 0

    def test_unsubscribe_missing_does_nothing(self):
        from app.utils.logging import LogBroadcaster
        b = LogBroadcaster()
        b.unsubscribe(MagicMock())

    def test_get_broadcaster_singleton(self):
        from app.utils.logging import _broadcaster, get_broadcaster
        assert get_broadcaster() is _broadcaster


# =============================================================================
# File 3: app/utils/telemetry.py (87% → 100%)
#   Gaps: 69, 72-112, 116
# =============================================================================

class TestTelemetryRemainingBranches:

    @pytest.mark.asyncio
    async def test_end_span_enabled_exports(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = True
        span = await tel.start_span("test")
        with patch.object(tel, "_export", AsyncMock()) as mock_export:
            await tel.end_span(span)
            mock_export.assert_awaited_once_with(span)
        assert span in [s for s in tel._spans]

    @pytest.mark.asyncio
    async def test_export_success(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = True
        tel.settings.otlp_endpoint = "http://fake-jaeger:4318"
        tel.settings.service_name = "test-service"
        span = await tel.start_span("test-span", attributes={"key": "val"})
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        with patch("httpx.AsyncClient", return_value=mock_client):
            await tel._export(span)
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_exception_passes(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = True
        span = await tel.start_span("test-span")
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("export failed"))
        mock_client.__aenter__.return_value = mock_client
        with patch("httpx.AsyncClient", return_value=mock_client):
            await tel._export(span)

    def test_trace_context_manager(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = False

        async def run_trace():
            async with tel.trace("test", attributes={"k": "v"}) as span:
                span.set_attribute("k2", "v2")
                return span

        import asyncio
        span = asyncio.run(run_trace())
        assert span.name == "test"
        assert span.attributes.get("k2") == "v2"

    @pytest.mark.asyncio
    async def test_get_spans_filtered_by_trace_id(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = False
        s1 = await tel.start_span("one", trace_id="trace-a")
        s2 = await tel.start_span("two", trace_id="trace-b")
        await tel.end_span(s1)
        await tel.end_span(s2)
        results = tel.get_spans(trace_id="trace-a")
        assert len(results) == 1
        assert results[0]["name"] == "one"

    @pytest.mark.asyncio
    async def test_get_spans_all(self):
        from app.utils.telemetry import OpenTelemetrySetup
        tel = OpenTelemetrySetup()
        tel.enabled = False
        s1 = await tel.start_span("one")
        s2 = await tel.start_span("two")
        await tel.end_span(s1)
        await tel.end_span(s2)
        results = tel.get_spans()
        assert len(results) == 2

    def test_set_attribute_on_span(self):
        from app.utils.telemetry import Span
        s = Span("test")
        s.set_attribute("env", "prod")
        assert s.attributes["env"] == "prod"

    def test_span_context_manager(self):
        from app.utils.telemetry import Span
        s = Span("test")
        with s:
            s.set_attribute("in", "context")
        assert s.duration_ms >= 0

    def test_span_to_dict(self):
        from app.utils.telemetry import Span
        with Span("test", trace_id="trace-1", attributes={"a": "b"}) as s:
            pass
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["trace_id"] == "trace-1"
        assert d["attributes"]["a"] == "b"

    def test_get_telemetry_singleton(self):
        from app.utils.telemetry import get_telemetry

        t1 = get_telemetry()
        t2 = get_telemetry()
        assert t1 is t2


# =============================================================================
# File 4: app/utils/llm_cache.py (85% → 100%)
#   Gaps: 39-43, 50 (Redis-backed get/set)
# =============================================================================

class TestPersistentLLMCacheRedisPaths:

    @pytest.mark.asyncio
    async def test_get_redis_hit(self):
        from app.utils.llm_cache import PersistentLLMCache
        cache = PersistentLLMCache()
        cache._redis = AsyncMock()
        cache._redis.get = AsyncMock(return_value='{"cached": "data"}')
        result = await cache.get("model", [{"role": "user", "content": "hi"}])
        assert result == {"cached": "data"}
        assert result in cache._l1.values()

    @pytest.mark.asyncio
    async def test_get_redis_miss(self):
        from app.utils.llm_cache import PersistentLLMCache
        cache = PersistentLLMCache()
        cache._redis = AsyncMock()
        cache._redis.get = AsyncMock(return_value=None)
        result = await cache.get("model", [{"role": "user", "content": "hi"}])
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_redis(self):
        from app.utils.llm_cache import PersistentLLMCache
        cache = PersistentLLMCache()
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()
        await cache.set("model", [{"role": "user", "content": "hi"}], "response-data")
        cache._redis.setex.assert_awaited_once()
        args, _ = cache._redis.setex.call_args
        assert args[2] == '"response-data"'


# =============================================================================
# File 5: app/memory/cache.py (70% → 100%)
#   Gaps: 22, 29-30, 40-46, 54-55, 66-71, 80-82, 89-91
# =============================================================================

class TestCacheRedisPaths:

    @pytest.mark.asyncio
    async def test_get_redis_returns_pickled_data(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.get = AsyncMock(return_value=pickle_dumps({"val": 42}))
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.get("pickled-key")
        assert result == {"val": 42}

    @pytest.mark.asyncio
    async def test_get_redis_returns_json_data(self):
        import json

        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.get = AsyncMock(return_value=json.dumps({"val": 42}).encode())
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.get("json-key")
        assert result == {"val": 42}

    @pytest.mark.asyncio
    async def test_get_redis_returns_none_on_miss(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.get = AsyncMock(return_value=None)
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.get("miss-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_local_cache_expired(self):
        import time

        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = False
        cache._local_cache["expired"] = (time.time() - 100, "old")
        result = await cache.get("expired", ttl=10)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_local_cache_not_expired(self):
        import time

        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = False
        cache._local_cache["good"] = (time.time(), "fresh")
        result = await cache.get("good", ttl=60)
        assert result == "fresh"

    @pytest.mark.asyncio
    async def test_get_redis_pickle_fallback_to_json(self):

        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        json_data = b'{"key": "fallback_val"}'
        cache._redis.get = AsyncMock(return_value=json_data)
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.get("bad-pickle")
        assert result == {"key": "fallback_val"}

    @pytest.mark.asyncio
    async def test_set_redis_success(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock()
        cache._redis.ping = AsyncMock()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.set("key", "value", ttl=60)
        assert result is True
        cache._redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_redis_write_failure(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.setex = AsyncMock(side_effect=Exception("write error"))
        cache._redis.ping = AsyncMock()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.set("key", "value", ttl=60)
        assert result is True
        assert "key" in cache._local_cache

    @pytest.mark.asyncio
    async def test_delete_redis(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.delete = AsyncMock()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.delete("some-key")
        assert result is True
        cache._redis.delete.assert_awaited_once_with("some-key")

    @pytest.mark.asyncio
    async def test_flush_redis(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        cache._redis.flushdb = AsyncMock()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=cache._redis)):
            result = await cache.flush()
        assert result is True
        cache._redis.flushdb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_redis_early_return_on_cached_redis(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = AsyncMock()
        result = await cache._get_redis()
        assert result is cache._redis

    @pytest.mark.asyncio
    async def test_get_redis_init_connected(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = None
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()
        with patch("app.memory.cache.aioredis.from_url", return_value=mock_redis):
            result = await cache._get_redis()
        assert result is mock_redis
        assert cache._redis is mock_redis

    @pytest.mark.asyncio
    async def test_get_redis_init_failure_fallback(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._redis = None
        with patch("app.memory.cache.aioredis.from_url", side_effect=Exception("no redis")):
            result = await cache._get_redis()
        assert result is None
        assert cache._use_redis is False

    @pytest.mark.asyncio
    async def test_get_redis_use_redis_false_skips(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = False
        cache._local_cache["local"] = (0.0, "val")
        result = await cache.get("local")
        assert result == "val"

    @pytest.mark.asyncio
    async def test_get_redis_none_fallback_to_local(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = True
        import time
        cache._local_cache["local"] = (time.time(), "local-val")
        with patch.object(cache, "_get_redis", AsyncMock(return_value=None)):
            result = await cache.get("local")
        assert result == "local-val"

    @pytest.mark.asyncio
    async def test_set_no_ttl_uses_default(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = False
        result = await cache.set("key", "val")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_redis_none_fallback_to_local(self):
        from app.memory.cache import Cache
        cache = Cache()
        cache._use_redis = True
        with patch.object(cache, "_get_redis", AsyncMock(return_value=None)):
            result = await cache.set("key", "val")
        assert result is True
        assert "key" in cache._local_cache

    @pytest.mark.asyncio
    async def test_delete_redis_none_skips(self):
        from app.memory.cache import Cache
        cache = Cache()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=None)):
            result = await cache.delete("key")
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_redis_none_skips(self):
        from app.memory.cache import Cache
        cache = Cache()
        with patch.object(cache, "_get_redis", AsyncMock(return_value=None)):
            result = await cache.flush()
        assert result is True


def pickle_dumps(obj):
    import pickle
    return pickle.dumps(obj)


# =============================================================================
# File 6: app/memory/session.py (70% → 100%)
#   Gaps: 24, 29-33, 73, 95-112, 123-138
# =============================================================================

class TestSessionManagerDBPaths:

    @pytest.fixture
    def sm(self):
        from app.memory.session import SessionManager
        return SessionManager()

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.fetchone = MagicMock()
        return session

    @pytest.fixture
    def mock_factory(self, mock_session):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=mock_session)
        cm.__aexit__ = AsyncMock()
        factory = MagicMock(return_value=cm)
        return factory

    @pytest.mark.asyncio
    async def test_init_db_early_return(self, sm):
        sm._engine = MagicMock()
        sm._session_factory = MagicMock()
        await sm._init_db()
        assert sm._engine is not None

    @pytest.mark.asyncio
    async def test_init_db_failure_sets_fallback(self, sm):
        sm._engine = None
        with patch("app.memory.session.create_async_engine", side_effect=Exception("db fail")):
            await sm._init_db()
        assert sm._use_json_fallback is True

    @pytest.mark.asyncio
    async def test_init_db_success(self, sm):
        sm._engine = None
        mock_engine = MagicMock()
        with patch("app.memory.session.create_async_engine", return_value=mock_engine):
            await sm._init_db()
        assert sm._engine is mock_engine
        assert sm._session_factory is not None
        assert sm._use_json_fallback is False

    @pytest.mark.asyncio
    async def test_create_db_path(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        session_id = await sm.create("proj-1", "wf-1")
        assert isinstance(session_id, str)
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_db_failure_fallback(self, sm):
        sm._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db exec failed"))
        cm.__aexit__ = AsyncMock()
        sm._session_factory.return_value = cm
        sm._engine = MagicMock()
        session_id = await sm.create("proj-1", "wf-1")
        assert session_id in sm._sessions

    @pytest.mark.asyncio
    async def test_update_db_success(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.update("session-id", context={"key": "val"}, status="running")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_db_no_rows(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.update("session-id", context={"key": "val"})
        assert result is False

    @pytest.mark.asyncio
    async def test_update_db_context_only(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.update("session-id", context={"key": "val"})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_db_status_only(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.update("session-id", status="completed")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_db_failure(self, sm):
        sm._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db update fail"))
        cm.__aexit__ = AsyncMock()
        sm._session_factory.return_value = cm
        result = await sm.update("session-id", status="running")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_db_found(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        import json
        from datetime import datetime
        row = ("id-1", "proj-1", "wf-1", "running", json.dumps({"k": "v"}), datetime(2025, 1, 1), datetime(2025, 1, 2))  # noqa: E501
        mock_result = MagicMock()
        mock_result.fetchone.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.get("id-1")
        assert result is not None
        assert result["id"] == "id-1"
        assert result["project_id"] == "proj-1"
        assert result["workflow_id"] == "wf-1"
        assert result["status"] == "running"
        assert result["context"] == {"k": "v"}
        assert "created_at" in result
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_get_db_not_found(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_db_failure_fallback_to_memory(self, sm):
        sm._engine = MagicMock()
        sm._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db get fail"))
        cm.__aexit__ = AsyncMock()
        sm._session_factory.return_value = cm
        sm._sessions["mem-id"] = {"id": "mem-id", "project_id": "proj"}
        result = await sm.get("mem-id")
        assert result == {"id": "mem-id", "project_id": "proj"}

    @pytest.mark.asyncio
    async def test_get_db_failure_no_fallback(self, sm):
        sm._engine = MagicMock()
        sm._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db get fail"))
        cm.__aexit__ = AsyncMock()
        sm._session_factory.return_value = cm
        result = await sm.get("no-such")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_db_exception_returns_false(self, sm, mock_factory):
        sm._session_factory = mock_factory
        mock_cm = sm._session_factory.return_value
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("db crash"))
        result = await sm.update("id", status="x")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_with_context_as_dict(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        from datetime import datetime
        row = ("id-2", "proj-2", "wf-2", "pending", {"k": "v"}, datetime(2025, 1, 1), datetime(2025, 1, 2))  # noqa: E501
        mock_result = MagicMock()
        mock_result.fetchone.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.get("id-2")
        assert result["context"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_get_with_non_isoformat_dates(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        row = ("id-3", "proj-3", "wf-3", "done", "{}", "2025-01-01", "2025-01-02")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.get("id-3")
        assert result["created_at"] == "2025-01-01"

    @pytest.mark.asyncio
    async def test_update_in_memory_with_fallback(self, sm):
        sm._use_json_fallback = True
        sm._sessions["sid"] = {"id": "sid", "status": "pending", "context": {}, "updated_at": "old"}
        result = await sm.update("sid", status="running", context={"a": 1})
        assert result is True
        assert sm._sessions["sid"]["status"] == "running"
        assert sm._sessions["sid"]["context"] == {"a": 1}

    @pytest.mark.asyncio
    async def test_update_in_memory_not_found(self, sm):
        sm._use_json_fallback = True
        sm._sessions.clear()
        result = await sm.update("no-id", status="running")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_db_row_without_isoformat(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        class FakeDate:
            def isoformat(self):
                return "2025-06-01T00:00:00"
        row = ("id-4", "proj-4", "wf-4", "done", "{}", FakeDate(), FakeDate())
        mock_result = MagicMock()
        mock_result.fetchone.return_value = row
        mock_session.execute = AsyncMock(return_value=mock_result)
        result = await sm.get("id-4")
        assert result["created_at"] == "2025-06-01T00:00:00"

    @pytest.mark.asyncio
    async def test_get_from_fallback_sessions(self, sm):
        sm._use_json_fallback = True
        sm._sessions["mem-s1"] = {"id": "mem-s1", "project_id": "p1"}
        result = await sm.get("mem-s1")
        assert result == {"id": "mem-s1", "project_id": "p1"}

    @pytest.mark.asyncio
    async def test_get_with_in_memory_fallback_found(self, sm, mock_factory, mock_session):
        sm._engine = MagicMock()
        sm._session_factory = mock_factory
        sm._sessions["inmem"] = {"id": "inmem", "project_id": "p"}
        result = await sm.get("inmem")
        assert result == {"id": "inmem", "project_id": "p"}


# =============================================================================
# File 7: app/memory/vector_store.py (78% → 100%)
#   Gaps: 24-37, 68-70, 102-104, 116-117, 138-139
# =============================================================================

class TestVectorStoreRemainingBranches:

    @pytest.fixture
    def vs(self):
        from app.memory.vector_store import VectorStore
        return VectorStore()

    @pytest.mark.asyncio
    async def test_init_db_success(self, vs):
        vs._engine = None
        mock_engine = MagicMock()
        mock_conn = AsyncMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(),
        ))
        with patch("app.memory.vector_store.create_async_engine", return_value=mock_engine):
            await vs._init_db()
        assert vs._engine is mock_engine
        assert vs._session_factory is not None
        assert vs._use_json_fallback is False
        assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_init_db_early_return(self, vs):
        vs._engine = MagicMock()
        vs._session_factory = MagicMock()
        await vs._init_db()

    @pytest.mark.asyncio
    async def test_init_db_failure(self, vs):
        vs._engine = None
        with patch("app.memory.vector_store.create_async_engine", side_effect=Exception("db fail")):
            await vs._init_db()
        assert vs._use_json_fallback is True

    @pytest.mark.asyncio
    async def test_store_db_failure_falls_back_to_json(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        vs._use_json_fallback = False
        vs._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db write fail"))
        cm.__aexit__ = AsyncMock()
        vs._session_factory.return_value = cm
        vs._engine = MagicMock()
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_store_json", AsyncMock(return_value="fallback-id")) as mock_store_json,  # noqa: E501
        ):
            entry_id = await vs.store("proj-1", "hello")
        assert entry_id == "fallback-id"
        mock_store_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_db_failure_falls_back_to_json(self, vs):
        mock_embedding = [0.1, 0.2, 0.3]
        vs._use_json_fallback = False
        vs._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db search fail"))
        cm.__aexit__ = AsyncMock()
        vs._session_factory.return_value = cm
        vs._engine = MagicMock()
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_search_json", MagicMock(return_value=[{"id": "fallback"}])) as mock_search,  # noqa: E501
        ):
            results = await vs.search("proj-1", "hello")
        assert results == [{"id": "fallback"}]
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_db_exception_returns_false(self, vs):
        vs._session_factory = MagicMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=Exception("db delete fail"))
        cm.__aexit__ = AsyncMock()
        vs._session_factory.return_value = cm
        vs._engine = MagicMock()
        result = await vs.delete("id-1")
        assert result is False

    @pytest.mark.asyncio
    async def test_store_json_with_existing_file(self, vs):
        mock_embedding = [0.1, 0.2]
        existing = [{"id": "old-id", "project_id": "proj-1", "content": "old", "embedding": [0.0]}]
        import json
        mock_file = MagicMock()
        mock_file.__enter__.return_value.__iter__.return_value = iter([json.dumps(existing)])
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_json_fallback_path", return_value="/tmp/test_fallback.json"),
            patch("os.makedirs"),
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_file),
            patch("app.memory.vector_store.json.load", return_value=existing),
            patch("app.memory.vector_store.json.dump"),
        ):
            entry_id = await vs._store_json("new-id", "proj-1", "new content", None, mock_embedding)
        assert entry_id == "new-id"

    @pytest.mark.asyncio
    async def test_store_json_no_existing_file(self, vs):
        mock_embedding = [0.1, 0.2]
        with (
            patch.object(vs._embedding_client, "embed", AsyncMock(return_value=mock_embedding)),
            patch.object(vs, "_json_fallback_path", return_value="/tmp/test_fallback.json"),
            patch("os.makedirs"),
            patch("os.path.exists", return_value=False),
            patch("builtins.open", MagicMock()),
            patch("app.memory.vector_store.json.dump"),
        ):
            entry_id = await vs._store_json("new-id", "proj-1", "new content", None, mock_embedding)
        assert entry_id == "new-id"


# =============================================================================
# File 8: app/scheduler.py (65% → 100%)
#   Gaps: 35, 38, 49-50, 71-73, 76-77, 101, 107-120, 123-142
# =============================================================================

class TestScheduledTaskRemaining:

    def test_should_run_disabled(self):
        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "* * * * *", "prompt")
        t.enabled = False
        assert t.should_run(1000) is False

    def test_should_run_invalid_cron_few_parts(self):
        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "* * *", "prompt")
        assert t.should_run(1000) is False

    def test_should_run_invalid_cron_exception(self):
        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "a b c d e", "prompt")
        assert t.should_run(float('inf')) is False

    def test_get_scheduler_singleton(self):
        from app.scheduler import _scheduler, get_scheduler
        old = _scheduler
        import app.scheduler as sched_mod
        sched_mod._scheduler = None
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2
        sched_mod._scheduler = old

    def test_should_run_matches(self):
        import time

        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "* * * * *", "prompt")
        assert t.should_run(time.time()) is True

    def test_should_run_exact_minute(self):
        from datetime import datetime

        from app.scheduler import ScheduledTask
        now = datetime.now()
        cron = f"{now.minute} * * * *"
        t = ScheduledTask("test", cron, "prompt")
        assert t.should_run(now.timestamp()) is True

    def test_should_run_no_match(self):
        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "99 * * * *", "prompt")
        assert t.should_run(0) is False

    def test_to_dict(self):
        from app.scheduler import ScheduledTask
        t = ScheduledTask("test", "* * * * *", "prompt", task_id="abc123")
        d = t.to_dict()
        assert d["id"] == "abc123"
        assert d["name"] == "test"
        assert d["enabled"] is True
        assert d["run_count"] == 0


class TestSchedulerRemainingBranches:

    @pytest.fixture
    def sched(self):
        from app.scheduler import Scheduler
        return Scheduler()

    @pytest.mark.asyncio
    async def test_start(self, sched):
        with patch.object(sched, "_run_loop", AsyncMock()) as mock_loop:
            await sched.start()
        assert sched._running is True
        mock_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, sched):
        sched._running = True
        await sched.stop()
        assert sched._running is False

    def test_remove_task_not_found(self, sched):
        result = sched.remove_task("nonexistent")
        assert result is False

    def test_remove_task_found(self, sched):
        import asyncio
        asyncio.run(sched.add_task("test", "* * * * *", "prompt"))
        all_tasks = sched.list_tasks()
        assert len(all_tasks) == 1
        tid = all_tasks[0]["id"]
        result = sched.remove_task(tid)
        assert result is True
        assert len(sched.list_tasks()) == 0

    @pytest.mark.asyncio
    async def test_run_loop_cancelled_error_breaks(self, sched):
        sched._running = True
        sched.settings.scheduler_check_interval = 1
        with patch.object(sched, "_execute_task", AsyncMock()):
            task = MagicMock()
            task.should_run.return_value = True
            task.last_run = 0.0
            task.id = "t1"
            sched._tasks["t1"] = task
            asyncio_sleep = AsyncMock(side_effect=[asyncio.CancelledError()])
            with patch("asyncio.sleep", asyncio_sleep):
                await sched._run_loop()

    @pytest.mark.asyncio
    async def test_run_loop_exception_logs_and_continues(self, sched):
        sched._running = True
        sched.settings.scheduler_check_interval = 1
        exc = Exception("unexpected error")

        async def side_effect(*args, **kwargs):
            if not hasattr(side_effect, "called"):
                side_effect.called = True
                raise exc
            raise asyncio.CancelledError()

        asyncio_sleep = AsyncMock(side_effect=side_effect)
        with (
            patch("asyncio.sleep", asyncio_sleep),
            patch.object(sched, "_execute_task", AsyncMock()),
            patch("app.scheduler.logger.log_error") as mock_log_error,
        ):
            try:
                await sched._run_loop()
            except asyncio.CancelledError:
                pass
            mock_log_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_loop_executes_task(self, sched):
        sched._running = True
        sched.settings.scheduler_check_interval = 1

        task = MagicMock()
        task.should_run.return_value = True
        task.last_run = 0.0
        task.run_count = 0
        task.id = "t1"
        task.name = "test-task"
        task.project_id = "default"
        task.prompt = "do-something"
        task.channel = "console"
        sched._tasks["t1"] = task

        with (
            patch.object(sched, "_execute_task", AsyncMock()) as mock_exec,
            patch("asyncio.sleep", AsyncMock(side_effect=[None, asyncio.CancelledError()])),
        ):
            try:
                await sched._run_loop()
            except asyncio.CancelledError:
                pass
            assert task.run_count == 1
            assert task.last_run > 0
            mock_exec.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_run_loop_skips_task_if_recently_run(self, sched):
        import time
        sched._running = True
        sched.settings.scheduler_check_interval = 1

        task = MagicMock()
        task.should_run.return_value = True
        task.last_run = time.time()
        task.run_count = 0
        task.id = "t1"
        sched._tasks["t1"] = task

        with (
            patch.object(sched, "_execute_task", AsyncMock()),
            patch("asyncio.sleep", AsyncMock(side_effect=[asyncio.CancelledError()])),
        ):
            try:
                await sched._run_loop()
            except asyncio.CancelledError:
                pass
            assert task.run_count == 0

    @pytest.mark.asyncio
    async def test_execute_task_success(self, sched):
        task = MagicMock()
        task.name = "test-task"
        task.id = "t1"
        task.project_id = "default"
        task.prompt = "do it"
        task.channel = "console"

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value={"status": "completed"})

        mock_notif = AsyncMock()
        mock_notif.send = AsyncMock()

        with (
            patch("app.scheduler.get_orchestrator", return_value=mock_orch),
            patch("app.scheduler.get_notifications", return_value=mock_notif),
        ):
            await sched._execute_task(task)

        mock_orch.run.assert_awaited_once_with(prompt="do it", project_id="default")
        mock_notif.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_task_failure(self, sched):
        task = MagicMock()
        task.name = "test-task"
        task.id = "t1"
        task.project_id = "default"
        task.prompt = "do it"

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=Exception("execution failed"))

        with (
            patch("app.scheduler.get_orchestrator", return_value=mock_orch),
            patch("app.scheduler.get_notifications"),
            patch("app.scheduler.logger.log_error") as mock_log_error,
        ):
            await sched._execute_task(task)

        mock_log_error.assert_called_once()
