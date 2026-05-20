"""Tests for v2.0/v3.0 features: parallel execution, metrics, telemetry, notifications, caching, multi-model routing, scheduler, workspaces."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
import time

from app.orchestrator import AgentOSOrchestrator, AgentOSState
from app.utils.metrics import MetricsCollector
from app.utils.telemetry import TelemetryTracer
from app.utils.notifications import NotificationManager
from app.utils.logging import LogBroadcaster, get_broadcaster
from app.memory.workspace import WorkspaceManager, get_workspace_manager


# --- Metrics ---

class TestMetrics:
    def test_counter_increment(self):
        m = MetricsCollector()
        m.counter("test_counter")
        m.counter("test_counter")
        assert m.metrics["test_counter"]["value"] == 2

    def test_timing(self):
        m = MetricsCollector()
        m.timing("test_timing", 1.5)
        assert m.metrics["test_timing"]["count"] == 1

    def test_gauge(self):
        m = MetricsCollector()
        m.gauge("test_gauge", 42)
        assert m.metrics["test_gauge"]["value"] == 42

    def test_render_prometheus(self):
        m = MetricsCollector()
        m.counter("requests_total")
        output = m.render_prometheus()
        assert "requests_total" in output
        assert "TYPE requests_total counter" in output


# --- Telemetry ---

class TestTelemetry:
    @pytest.mark.asyncio
    async def test_trace_context_manager(self):
        t = TelemetryTracer(enabled=False)
        async with t.trace("test_span", "trace-1") as span:
            span.set_attribute("key", "value")
            pass
        assert len(t.spans) > 0
        assert t.spans[0]["name"] == "test_span"

    def test_span_attributes(self):
        t = TelemetryTracer(enabled=False)
        span = t._create_span("test", "trace-1")
        span["attributes"]["key"] = "value"
        assert span["attributes"]["key"] == "value"


# --- Notifications ---

class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_console(self):
        n = NotificationManager()
        with patch.object(n.logger, "log_action") as mock_log:
            await n.send("console", "test subject", "test body")
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_webhook(self):
        n = NotificationManager()
        n.settings.slack_webhook_url = "https://hooks.slack.com/test"
        with patch("httpx.AsyncClient.post", AsyncMock()) as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            await n.send("slack", "test", "body")
            mock_post.assert_called_once()


# --- Logging Pub/Sub ---

class TestLogBroadcaster:
    def test_subscribe_unsubscribe(self):
        b = LogBroadcaster()
        cb = MagicMock()
        unsub = b.subscribe(cb)
        assert len(b._subscribers) == 1
        unsub()
        assert len(b._subscribers) == 0

    @pytest.mark.asyncio
    async def test_broadcast(self):
        b = LogBroadcaster()
        received = []
        def cb(msg):
            received.append(msg)
        b.subscribe(cb)
        await b.broadcast({"message": "hello"})
        assert len(received) == 1
        assert received[0]["message"] == "hello"


# --- Multi-Model Routing ---

class TestMultiModelRouting:
    @pytest.mark.asyncio
    async def test_chat_with_model_selection(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        with patch.object(client, "chat", AsyncMock(return_value=MagicMock(content="test"))):
            with patch.object(client.settings, "model_for_code", "test-model"):
                result = await client.chat_with_model_selection(
                    task_type="code",
                    messages=[{"role": "user", "content": "write code"}],
                )
                assert result.content == "test"

    @pytest.mark.asyncio
    async def test_task_type_defaults(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        assert client.get_model_for_task("code") == client.settings.model_for_code
        assert client.get_model_for_task("content") == client.settings.model_for_content
        assert client.get_model_for_task("unknown_type") == client.settings.model_for_default


# --- LLM Response Cache ---

class TestLLMCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        client.cache_enabled = True
        key = client._make_cache_key("model-x", [{"role": "user", "content": "hi"}], 0.7)
        client._cache[key] = {"response": "cached", "timestamp": time.time()}
        result = await client._check_cache("model-x", [{"role": "user", "content": "hi"}], 0.7)
        assert result == "cached"

    def test_cache_miss(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        result = client._check_cache_sync("no-such-key")
        assert result is None

    def test_cache_clear(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        client._cache["test"] = "value"
        client.clear_cache()
        assert len(client._cache) == 0

    def test_cache_key_consistency(self):
        from app.utils.api_clients import LLMClient
        client = LLMClient()
        k1 = client._make_cache_key("m", [{"role": "user", "content": "hi"}], 0.7)
        k2 = client._make_cache_key("m", [{"role": "user", "content": "hi"}], 0.7)
        assert k1 == k2


# --- Parallel Execution ---

class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_execute_parallel(self):
        orchestrator = AgentOSOrchestrator()
        state: AgentOSState = {
            "project_id": "test",
            "session_id": "test-session",
            "trace_id": "test-trace",
            "prompt": "test",
            "tasks": [
                {"agent": "content", "action": "write", "params": {}},
                {"agent": "marketing", "action": "email", "params": {}},
            ],
            "current_task_index": 0,
            "agent_sequence": [],
            "results": {},
            "errors": [],
            "pending_hitl": [],
            "status": "running",
            "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
            "start_time": 0.0,
            "parallel_batch": [
                {"agent": "content", "action": "write", "params": {}},
                {"agent": "marketing", "action": "email", "params": {}},
            ],
        }

        async def mock_execute(task, session_id="", trace_id=""):
            return {"agent": task["agent"], "action": task["action"], "success": True, "result": {}}

        with patch("app.agents.content.ContentAgent.execute", mock_execute), \
             patch("app.agents.marketing.MarketingAgent.execute", mock_execute):
            result = await orchestrator._execute_parallel(state)
            assert "results" in result
            assert result["current_task_index"] >= state["current_task_index"] + 1


# --- Workspace Manager ---

class TestWorkspace:
    def test_create_and_get(self):
        wm = WorkspaceManager()
        ws = wm.create_workspace("test-proj")
        assert ws.id == "test-proj"
        assert wm.get_workspace("test-proj") is ws

    def test_list_workspaces(self):
        wm = WorkspaceManager()
        wm.create_workspace("a")
        wm.create_workspace("b")
        names = [w["id"] for w in wm.list_workspaces()]
        assert "a" in names
        assert "b" in names

    def test_delete_workspace(self):
        wm = WorkspaceManager()
        wm.create_workspace("to-delete")
        assert wm.delete_workspace("to-delete") is True
        assert wm.get_workspace("to-delete") is None
        assert wm.delete_workspace("nonexistent") is False

    def test_default_exists(self):
        wm = WorkspaceManager()
        wm.ensure_default()
        assert wm.get_workspace("default") is not None
