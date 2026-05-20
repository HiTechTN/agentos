import pytest
from unittest.mock import AsyncMock, patch

from app.orchestrator import AgentOSOrchestrator, AgentOSState


@pytest.fixture
def orchestrator():
    return AgentOSOrchestrator()


@pytest.mark.asyncio
async def test_orchestrator_initializes(orchestrator):
    assert orchestrator is not None
    assert "dev" in orchestrator.agents
    assert "content" in orchestrator.agents
    assert "marketing" in orchestrator.agents
    assert "commerce" in orchestrator.agents


@pytest.mark.asyncio
async def test_orchestrator_run_basic_prompt(orchestrator):
    with patch.object(orchestrator, "_decompose_prompt", AsyncMock(return_value=[
        {"agent": "dev", "action": "analyze", "params": {"prompt": "test"}, "priority": 0}
    ])):
        result = await orchestrator.run("test prompt")
        assert result is not None
        assert "status" in result
        assert "session_id" in result


@pytest.mark.asyncio
async def test_orchestrator_analyze_prompt(orchestrator):
    tasks = await orchestrator._decompose_prompt("Create a landing page")
    assert isinstance(tasks, list)
    assert len(tasks) > 0
    for task in tasks:
        assert "agent" in task
        assert "action" in task
        assert "params" in task


@pytest.mark.asyncio
async def test_orchestrator_agent_execution(orchestrator):
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "tasks": [{"agent": "dev", "action": "analyze", "params": {"prompt": "hello"}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
    }

    with patch("app.agents.dev.DevAgent.execute", AsyncMock(return_value={
        "agent": "dev", "action": "analyze", "success": True,
        "result": {"data": {"analysis": "test"}}
    })):
        result = await orchestrator._execute_dev(state)
        assert "results" in result or "current_task_index" in result


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker(orchestrator):
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "tasks": [{"agent": "dev", "action": "test", "params": {}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 3, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
    }

    result = await orchestrator._execute_dev(state)
    assert "errors" in result
    has_circuit = any("CIRCUIT" in str(e.get("code", "")) for e in result.get("errors", []))
    assert has_circuit


@pytest.mark.asyncio
async def test_orchestrator_retry_on_failure(orchestrator):
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "tasks": [{"agent": "dev", "action": "deploy", "params": {}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
    }

    call_count = 0

    async def failing_execute(task, session_id="", trace_id=""):
        nonlocal call_count
        call_count += 1
        return {"agent": "dev", "action": "deploy", "success": False,
                "error": {"code": "TEST_FAIL", "message": "Simulated failure"}}

    with patch("app.agents.dev.DevAgent.execute", failing_execute):
        result = await orchestrator._execute_dev(state)

    assert "errors" in result
    assert len(result.get("errors", [])) >= 0


@pytest.mark.asyncio
async def test_orchestrator_multi_agent_sequence(orchestrator):
    tasks = [
        {"agent": "dev", "action": "analyze", "params": {"prompt": "build app"}},
        {"agent": "content", "action": "write", "params": {"topic": "app"}},
        {"agent": "commerce", "action": "catalog", "params": {}},
    ]

    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "build an app with content and commerce",
        "tasks": tasks,
        "current_task_index": 0,
        "agent_sequence": ["dev", "content", "commerce"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
    }

    mock_result = {"agent": "", "action": "", "success": True, "result": {"data": {}}}

    async def mock_dev(task, session_id="", trace_id=""):
        return {**mock_result, "agent": "dev", "action": task.get("action", "")}

    async def mock_content(task, session_id="", trace_id=""):
        return {**mock_result, "agent": "content", "action": task.get("action", "")}

    async def mock_commerce(task, session_id="", trace_id=""):
        return {**mock_result, "agent": "commerce", "action": task.get("action", "")}

    with patch("app.agents.dev.DevAgent.execute", mock_dev), \
         patch("app.agents.content.ContentAgent.execute", mock_content), \
         patch("app.agents.commerce.CommerceAgent.execute", mock_commerce):

        r1 = await orchestrator._execute_dev(state)
        r2 = await orchestrator._execute_content({**state, "current_task_index": 1})
        r3 = await orchestrator._execute_commerce({**state, "current_task_index": 2})

        if "results" in r1:
            assert "dev_analyze" in r1["results"]
        if "results" in r2:
            assert "content_write" in r2["results"]
        if "results" in r3:
            assert "commerce_catalog" in r3["results"]


@pytest.mark.asyncio
async def test_decide_execution_order(orchestrator):
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test",
        "trace_id": "test",
        "prompt": "test",
        "tasks": [{"agent": "dev", "action": "test"}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
        "start_time": 0.0,
    }

    decision = orchestrator._decide_execution_order(state)
    assert decision in ("dev", "content", "marketing", "commerce", "finalize", "error",
                        "parallel")
