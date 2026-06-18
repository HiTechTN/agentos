from typing import Any

# ruff: noqa: E402
"""v2/v3: parallel exec, metrics, telemetry, notifications, caching, routing, scheduler."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.workspace import WorkspaceManager
from app.orchestrator import AgentOSOrchestrator, AgentOSState
from app.utils.logging import LogBroadcaster
from app.utils.metrics import MetricsCollector
from app.utils.notifications import NotificationManager
from app.utils.telemetry import Span

# --- Metrics ---


class TestMetrics:
    def test_counter_increment(self) -> None:
        m = MetricsCollector()
        m.inc("test_counter")
        m.inc("test_counter")
        assert m._counters["test_counter"] == 2

    def test_timing(self) -> None:
        m = MetricsCollector()
        m.timing("test_timing", 1.5)
        assert len(m._timings["test_timing"]) == 1

    def test_gauge(self) -> None:
        m = MetricsCollector()
        m.gauge("test_gauge", 42)
        assert m._gauges["test_gauge"] == 42

    def test_render_prometheus(self) -> None:
        m = MetricsCollector()
        m.inc("requests_total")
        output = m.render_prometheus()
        assert "requests_total" in output


# --- Telemetry ---


class TestTelemetry:
    @pytest.mark.asyncio
    async def test_trace_context_manager(self) -> None:
        from app.utils.telemetry import OpenTelemetrySetup

        t = OpenTelemetrySetup()
        async with t.trace("test_span", "trace-1") as span:
            span.set_attribute("key", "value")
        spans = t.get_spans()
        assert len(spans) > 0
        assert spans[0]["name"] == "test_span"

    def test_span_attributes(self) -> None:
        span = Span("test", "trace-1")
        span.set_attribute("key", "value")
        assert span.attributes["key"] == "value"


# --- Notifications ---


class TestNotifications:
    @pytest.mark.asyncio
    async def test_send_console(self) -> None:
        n = NotificationManager()
        with patch("app.utils.notifications.logger.log_action") as mock_log:
            result = await n.send("console", "test subject", "test body")
            assert result is True
            assert mock_log.call_count >= 1

    @pytest.mark.asyncio
    async def test_send_slack_webhook(self) -> None:
        n = NotificationManager()
        n.settings.slack_webhook_url = "https://hooks.slack.com/test"
        with patch("httpx.AsyncClient.post", AsyncMock()) as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = await n.send("slack", "test", "body")
            assert result is True
            mock_post.assert_called_once()


# --- Logging Pub/Sub ---


class TestLogBroadcaster:
    def test_subscribe_unsubscribe(self) -> None:
        b = LogBroadcaster()
        cb = MagicMock()
        b.subscribe(cb)
        assert len(b._subscribers) == 1
        b.unsubscribe(cb)
        assert len(b._subscribers) == 0

    @pytest.mark.asyncio
    async def test_broadcast(self) -> None:
        b = LogBroadcaster()
        received = []

        def cb(msg: Any) -> None:
            received.append(msg)

        b.subscribe(cb)
        await b.broadcast({"message": "hello"})
        assert len(received) == 1
        assert received[0]["message"] == "hello"


# --- Multi-Model Routing ---


class TestMultiModelRouting:
    @pytest.mark.asyncio
    async def test_chat_with_model_selection(self) -> None:
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
    async def test_task_type_defaults(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        assert client._select_model("code") == client.settings.model_for_code
        assert client._select_model("content") == client.settings.model_for_content
        assert client._select_model("image") == client.settings.model_for_default


# --- LLM Response Cache ---


class TestLLMCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        from app.utils.api_clients import LLMClient, LLMResponse

        client = LLMClient()
        key = client._cache_key("model-x", [{"role": "user", "content": "hi"}], 0.7)
        client._llm_cache[key] = LLMResponse(content="cached", model="model-x", provider="test")
        with patch.object(client.settings, "llm_cache_enabled", True):
            result = await client.chat(
                "model-x", [{"role": "user", "content": "hi"}], temperature=0.7
            )  # noqa: E501
        assert result.content == "cached"

    def test_cache_miss(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        result = client._llm_cache.get("no-such-key")
        assert result is None

    def test_cache_clear(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        client._llm_cache["test"] = "value"  # type: ignore[assignment]
        client.clear_cache()
        assert len(client._llm_cache) == 0

    def test_cache_key_consistency(self) -> None:
        from app.utils.api_clients import LLMClient

        client = LLMClient()
        k1 = client._cache_key("m", [{"role": "user", "content": "hi"}], 0.7)
        k2 = client._cache_key("m", [{"role": "user", "content": "hi"}], 0.7)
        assert k1 == k2


# --- Parallel Execution ---


class TestParallelExecution:
    @pytest.mark.asyncio
    async def test_execute_parallel(self) -> Any:
        orchestrator = AgentOSOrchestrator()
        state: AgentOSState = {
            "project_id": "test",
            "session_id": "test-session",
            "trace_id": "test-trace",
            "prompt": "test",
            "attachments": [],
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
                {"agent": "content", "action": "write", "params": {}},  # type: ignore[list-item]
                {"agent": "marketing", "action": "email", "params": {}},  # type: ignore[list-item]
            ],
        }

        async def mock_execute(
            task: Any, session_id: Any = "", trace_id: Any = "", attachments: Any = None
        ) -> Any:
            return {"agent": task["agent"], "action": task["action"], "success": True, "result": {}}

        with (
            patch.object(orchestrator.agents["content"], "execute", mock_execute),
            patch.object(orchestrator.agents["marketing"], "execute", mock_execute),
        ):
            result = await orchestrator._execute_parallel(state)
            assert "results" in result
            assert result["current_task_index"] >= state["current_task_index"] + 1


# --- Workspace Manager ---


class TestWorkspace:
    def test_create_and_get(self) -> None:
        wm = WorkspaceManager()
        ws = wm.create_workspace("test-proj")
        assert ws.id == "test-proj"
        assert wm.get_workspace("test-proj") is ws

    def test_list_workspaces(self) -> None:
        wm = WorkspaceManager()
        wm.create_workspace("a")
        wm.create_workspace("b")
        names = [w["id"] for w in wm.list_workspaces()]
        assert "a" in names
        assert "b" in names

    def test_delete_workspace(self) -> None:
        wm = WorkspaceManager()
        wm.create_workspace("to-delete")
        assert wm.delete_workspace("to-delete") is True
        assert wm.get_workspace("to-delete") is None
        assert wm.delete_workspace("nonexistent") is False

    def test_default_exists(self) -> None:
        wm = WorkspaceManager()
        wm.ensure_default()
        assert wm.get_workspace("default") is not None
