"""Tests for v2.0/v3.0 features."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.orchestrator import AgentOSOrchestrator


@pytest.fixture
def orch():
    return AgentOSOrchestrator()


# ── Parallel execution ──────────────────────────────


@pytest.mark.asyncio
async def test_parallel_execution(orch):
    tasks = [
        {"agent": "content", "action": "write", "params": {}},
        {"agent": "marketing", "action": "segment", "params": {}},
        {"agent": "commerce", "action": "catalog", "params": {}},
    ]
    state = {
        "project_id": "t",
        "session_id": "s",
        "trace_id": "t",
        "prompt": "build app",
        "tasks": tasks,
        "current_task_index": 0,
        "agent_sequence": [],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
        "start_time": 0.0,
        "parallel_batch": tasks,
    }
    mock = {"agent": "", "action": "", "success": True, "result": {"data": {}}}

    async def mc(t, session_id="", trace_id=""):
        return {**mock, "agent": "content", "action": t.get("action", "")}

    async def mm(t, session_id="", trace_id=""):
        return {**mock, "agent": "marketing", "action": t.get("action", "")}

    async def mcom(t, session_id="", trace_id=""):
        return {**mock, "agent": "commerce", "action": t.get("action", "")}

    with (
        patch("app.agents.content.ContentAgent.execute", mc),
        patch("app.agents.marketing.MarketingAgent.execute", mm),
        patch("app.agents.commerce.CommerceAgent.execute", mcom),
    ):
        r = await orch._execute_parallel(state)
    assert r["current_task_index"] == 3


# ── Metrics ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_metrics():
    from app.utils.metrics import get_metrics

    m = get_metrics()
    m.inc("c", 1)
    assert m._counters.get("c", 0) >= 1
    m.timing("t", 1.5)
    assert len(m._timings.get("t", [])) >= 1
    assert "c" in m.render_prometheus()


# ── Telemetry ───────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetry_span():
    from app.utils.telemetry import get_telemetry

    t = get_telemetry()
    async with t.trace("test_span", "trace-1") as span:
        span.set_attribute("k", "v")
    spans = t.get_spans()
    assert len(spans) == 1
    assert spans[0]["name"] == "test_span"


# ── Notifications ───────────────────────────────────


@pytest.mark.asyncio
async def test_notifications():
    from app.utils.notifications import get_notifications

    n = get_notifications()
    assert await n.send("console", "S", "B") is True
    assert await n.send("slack", "S", "B") is True


# ── Scheduler ───────────────────────────────────────


@pytest.mark.asyncio
async def test_scheduler():
    from app.scheduler import ScheduledTask, get_scheduler

    s = get_scheduler()
    tid = await s.add_task("t1", "*/5 * * * *", "prompt", "default")
    assert tid is not None
    assert any(t["id"] == tid for t in s.list_tasks())
    assert s.remove_task(tid) is True
    assert not any(t["id"] == tid for t in s.list_tasks())

    task = ScheduledTask("t2", "* * * * *", "p", "default", "console", "tid2")
    task.last_run = 0.0
    assert task.should_run(time.time()) is True


# ── Workspace ───────────────────────────────────────


@pytest.mark.asyncio
async def test_workspace():
    from app.memory.workspace import get_workspace_manager

    wm = get_workspace_manager()
    ws = wm.create_workspace("test-ws")
    assert ws.id == "test-ws"
    assert wm.get_workspace("test-ws") is not None
    assert wm.delete_workspace("test-ws") is True
    assert wm.get_workspace("test-ws") is None
    wm.ensure_default()
    assert wm.get_workspace("default") is not None
    assert isinstance(wm.list_workspaces(), list)


# ── LLM Cache ───────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_cache():
    from app.utils.api_clients import LLMClient, LLMResponse

    client = LLMClient()
    k1 = client._cache_key("gpt-4o", [{"role": "user", "content": "hi"}], 0.7)
    k2 = client._cache_key("gpt-4o", [{"role": "user", "content": "hi"}], 0.7)
    k3 = client._cache_key("gpt-4o", [{"role": "user", "content": "bye"}], 0.7)
    assert k1 == k2 and k1 != k3

    msgs = [{"role": "user", "content": "cached"}]
    mock_resp = type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "resp"})()})]})()
    mock_openai = AsyncMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_resp)

    with (
        patch.object(client, "_get_openai_client", return_value=mock_openai),
        patch.object(client.settings, "llm_cache_enabled", True),
    ):
        first = await client.chat("gpt-4o", msgs, temperature=0.3)
        second = await client.chat("gpt-4o", msgs, temperature=0.3)
    assert first.content == second.content
    assert mock_openai.chat.completions.create.call_count == 1  # cached on second call


# ── Multi-model routing ─────────────────────────────


@pytest.mark.asyncio
async def test_model_routing():
    from app.config.settings import get_settings

    s = get_settings()
    assert s.model_for_code == "anthropic/claude-sonnet-20241022"
    assert s.model_for_content == "openai/gpt-4o-2024-11-20"
    assert s.model_for_analysis == "mistralai/mixtral-8x22b-instruct"
    assert s.model_for_commerce == "openai/gpt-4o-2024-11-20"


# ── Routing decision ────────────────────────────────


@pytest.mark.asyncio
async def test_routing_decides_parallel(orch):
    state = {
        k: v
        for k, v in {
            "project_id": "t",
            "session_id": "s",
            "trace_id": "t",
            "prompt": "test",
            "tasks": [
                {"agent": "content", "action": "w"},
                {"agent": "marketing", "action": "s"},
            ],
            "current_task_index": 0,
            "agent_sequence": [],
            "results": {},
            "errors": [],
            "pending_hitl": [],
            "status": "running",
            "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
            "start_time": 0.0,
            "parallel_batch": [],
        }.items()
    }
    decision = orch._decide_execution_order(state)
    assert decision == "parallel"


# ── Logging pub/sub ─────────────────────────────────


@pytest.mark.asyncio
async def test_logging_broadcaster():
    from app.utils.logging import get_broadcaster, get_logger

    log = get_logger("test")
    b = get_broadcaster()
    received = []

    def cb(msg):
        received.append(msg)

    b.subscribe(cb)
    log.log_action("test", "test", "completed")
    assert len(received) >= 0


# ── Orchestrator HITL propagation ───────────────────


@pytest.mark.asyncio
async def test_hitl_propagation(orch):
    from app.utils.hitl_gateway import HITLPendingError

    state = {
        "project_id": "t",
        "session_id": "s",
        "trace_id": "t",
        "prompt": "test",
        "tasks": [{"agent": "dev", "action": "deploy", "params": {}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
        "start_time": 0.0,
        "parallel_batch": [],
    }

    async def hitl_execute(task, session_id="", trace_id=""):
        raise HITLPendingError(approval_id="test-approval-id", action="deploy")

    with patch.object(orch.agents["dev"], "execute", hitl_execute):
        r = await orch._execute_dev(state)
    assert "pending_hitl" in r
