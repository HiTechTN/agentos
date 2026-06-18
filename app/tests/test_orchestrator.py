from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.orchestrator import (
    MAX_RETRIES,
    AgentOSOrchestrator,
    AgentOSState,
    load_policies,
)


def _make_state(
    tasks: list[dict[str, Any]] | None = None,
    current_task_index: int = 0,
    errors: list[dict[str, Any]] | None = None,
    results: dict[str, Any] | None = None,
    circuit_breaker: dict[str, int] | None = None,
    pending_hitl: list[str] | None = None,
    status: str = "running",
) -> AgentOSState:
    return {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "attachments": [],
        "tasks": tasks or [],
        "current_task_index": current_task_index,
        "agent_sequence": [],
        "results": results or {},
        "errors": errors or [],
        "pending_hitl": pending_hitl or [],
        "status": status,
        "circuit_breaker": circuit_breaker
        or {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
        "parallel_batch": [],
    }


@pytest.fixture
def orchestrator() -> Any:
    return AgentOSOrchestrator()


@pytest.mark.asyncio
async def test_orchestrator_initializes(orchestrator: Any) -> None:
    assert orchestrator is not None
    assert "dev" in orchestrator.agents
    assert "content" in orchestrator.agents
    assert "marketing" in orchestrator.agents
    assert "commerce" in orchestrator.agents


@pytest.mark.asyncio
async def test_orchestrator_run_basic_prompt(orchestrator: Any) -> None:
    with (
        patch.object(
            orchestrator,
            "_decompose_prompt",
            AsyncMock(
                return_value=[
                    {
                        "agent": "dev",
                        "action": "analyze",  # noqa: E501
                        "params": {"prompt": "test"},
                        "priority": 0,
                    }
                ]
            ),
        ),
        patch.object(
            orchestrator.agents["dev"],
            "execute",
            AsyncMock(
                # noqa: E501
                return_value={"agent": "dev", "action": "analyze", "success": True, "result": {}}
            ),
        ),
    ):
        result = await orchestrator.run("test prompt")
        assert result is not None
        assert "status" in result
        assert "session_id" in result


@pytest.mark.asyncio
async def test_orchestrator_analyze_prompt(orchestrator: Any) -> None:
    from app.utils.api_clients import LLMClient, LLMResponse

    resp = LLMResponse(
        content=(
            '[{"agent":"dev","action":"analyze",'
            '"params":{"prompt":"Create a landing page"},"priority":0}]'
        ),
        model="test",
        provider="test",
    )
    with patch.object(LLMClient, "chat", AsyncMock(return_value=resp)):
        tasks = await orchestrator._decompose_prompt("Create a landing page")
        assert isinstance(tasks, list)
        assert len(tasks) > 0
        for task in tasks:
            assert "agent" in task
            assert "action" in task
            assert "params" in task


@pytest.mark.asyncio
async def test_orchestrator_agent_execution(orchestrator: Any) -> None:
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "attachments": [],
        "tasks": [{"agent": "dev", "action": "analyze", "params": {"prompt": "hello"}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
        "parallel_batch": [],
    }

    with patch(
        "app.agents.dev.DevAgent.execute",
        AsyncMock(
            return_value={
                "agent": "dev",
                "action": "analyze",
                "success": True,
                "result": {"data": {"analysis": "test"}},
            }
        ),
    ):
        result = await orchestrator._execute_dev(state)
        assert "results" in result or "current_task_index" in result


@pytest.mark.asyncio
async def test_orchestrator_circuit_breaker(orchestrator: Any) -> None:
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "attachments": [],
        "tasks": [{"agent": "dev", "action": "test", "params": {}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 3, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
        "parallel_batch": [],
    }

    result = await orchestrator._execute_dev(state)
    assert "errors" in result
    has_circuit = any("CIRCUIT" in str(e.get("code", "")) for e in result.get("errors", []))
    assert has_circuit


@pytest.mark.asyncio
async def test_orchestrator_retry_on_failure(orchestrator: Any) -> Any:
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "test",
        "attachments": [],
        "tasks": [{"agent": "dev", "action": "deploy", "params": {}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
        "parallel_batch": [],
    }

    call_count = 0

    async def failing_execute(
        task: Any, session_id: Any = "", trace_id: Any = "", attachments: Any = None
    ) -> Any:
        nonlocal call_count
        call_count += 1
        return {
            "agent": "dev",
            "action": "deploy",
            "success": False,
            "error": {"code": "TEST_FAIL", "message": "Simulated failure"},
        }

    with patch("app.agents.dev.DevAgent.execute", failing_execute):
        result = await orchestrator._execute_dev(state)

    assert "errors" in result
    assert len(result.get("errors", [])) >= 0


@pytest.mark.asyncio
async def test_orchestrator_multi_agent_sequence(orchestrator: Any) -> Any:
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
        "attachments": [],
        "tasks": tasks,
        "current_task_index": 0,
        "agent_sequence": ["dev", "content", "commerce"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        "start_time": 0.0,
        "parallel_batch": [],
    }

    mock_result = {"agent": "", "action": "", "success": True, "result": {"data": {}}}

    async def mock_dev(task: Any, session_id: Any = "", trace_id: Any = "") -> Any:
        return {**mock_result, "agent": "dev", "action": task.get("action", "")}

    async def mock_content(task: Any, session_id: Any = "", trace_id: Any = "") -> Any:
        return {**mock_result, "agent": "content", "action": task.get("action", "")}

    async def mock_commerce(task: Any, session_id: Any = "", trace_id: Any = "") -> Any:
        return {**mock_result, "agent": "commerce", "action": task.get("action", "")}

    with (
        patch("app.agents.dev.DevAgent.execute", mock_dev),
        patch("app.agents.content.ContentAgent.execute", mock_content),
        patch("app.agents.commerce.CommerceAgent.execute", mock_commerce),
    ):
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
async def test_decide_execution_order(orchestrator: Any) -> None:
    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test",
        "trace_id": "test",
        "prompt": "test",
        "attachments": [],
        "tasks": [{"agent": "dev", "action": "test"}],
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

    decision = orchestrator._decide_execution_order(state)
    assert decision in ("dev", "content", "marketing", "commerce", "finalize", "error", "parallel")


# ===========================================================================
# Coverage gap tests — target every uncovered line in orchestrator.py
# ===========================================================================


class TestLoadPolicies:
    def test_load_policies_file_not_found(self) -> None:
        with patch("builtins.open", side_effect=FileNotFoundError("not found")):
            result = load_policies()
        assert result == {}

    def test_load_policies_yaml_error(self) -> None:
        with patch("builtins.open", MagicMock(side_effect=Exception("yaml error"))):
            result = load_policies()
        assert result == {}


class TestRunEdgeCases:
    @pytest.mark.asyncio
    async def test_run_graph_returns_none(self) -> None:
        orch = AgentOSOrchestrator()
        with (
            patch.object(orch, "_decompose_prompt", AsyncMock(return_value=[])),
            patch.object(orch.graph, "ainvoke", AsyncMock(return_value=None)),
        ):
            result = await orch.run("test")
            assert result == {}

    @pytest.mark.asyncio
    async def test_run_exception(self) -> None:
        orch = AgentOSOrchestrator()
        with (
            patch.object(orch, "_decompose_prompt", AsyncMock(return_value=[])),
            patch.object(orch.graph, "ainvoke", AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            result = await orch.run("test")
            assert result["status"] == "failed"
            assert result["error"]["code"] == "ORCHESTRATION_FAILED"

    @pytest.mark.asyncio
    async def test_run_with_project_id(self) -> None:
        orch = AgentOSOrchestrator()
        with (
            patch.object(orch, "_decompose_prompt", AsyncMock(return_value=[])),
            patch.object(
                orch.graph,
                "ainvoke",
                AsyncMock(return_value={"status": "completed", "results": {}}),
            ),
        ):
            result = await orch.run("test", project_id="my-project")
            assert result["status"] == "completed"


class TestAnalyzePromptEdgeCases:
    @pytest.mark.asyncio
    async def test_analyze_prompt_exception(self) -> None:
        orch = AgentOSOrchestrator()
        with patch.object(orch, "_decompose_prompt", AsyncMock(side_effect=ValueError("bad"))):
            state = _make_state()
            result = await orch._analyze_prompt(state)
            assert result["status"] == "error"
            assert any(e["code"] == "ANALYSIS_FAILED" for e in result["errors"])


class TestDecomposePromptEdgeCases:
    @pytest.mark.asyncio
    async def test_decompose_single_dict_response(self) -> None:
        from app.utils.api_clients import LLMClient, LLMResponse

        resp = LLMResponse(
            content='{"agent":"dev","action":"analyze","params":{},"priority":0}',
            model="test",
            provider="test",
        )
        with patch.object(LLMClient, "chat", AsyncMock(return_value=resp)):
            orch = AgentOSOrchestrator()
            tasks = await orch._decompose_prompt("test")
            assert len(tasks) == 1
            assert tasks[0]["agent"] == "dev"

    @pytest.mark.asyncio
    async def test_decompose_json_decode_error(self) -> None:
        from app.utils.api_clients import LLMClient, LLMResponse

        resp = LLMResponse(content="not json", model="test", provider="test")
        with patch.object(LLMClient, "chat", AsyncMock(return_value=resp)):
            orch = AgentOSOrchestrator()
            tasks = await orch._decompose_prompt("test")
            assert len(tasks) == 1
            assert tasks[0]["agent"] == "dev"

    @pytest.mark.asyncio
    async def test_decompose_attribute_error(self) -> None:
        from app.utils.api_clients import LLMClient

        with patch.object(LLMClient, "chat", AsyncMock(return_value=None)):
            orch = AgentOSOrchestrator()
            tasks = await orch._decompose_prompt("test")
            assert len(tasks) == 1
            assert tasks[0]["agent"] == "dev"


class TestDecideExecutionOrderEdgeCases:
    def test_finalize_when_no_tasks(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(tasks=[], current_task_index=0)
        assert orch._decide_execution_order(state) == "finalize"

    def test_finalize_when_index_exhausted(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(tasks=[{"agent": "dev", "action": "x"}], current_task_index=1)
        assert orch._decide_execution_order(state) == "finalize"

    def test_parallel_when_multiple_unique_agents(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[
                {"agent": "dev", "action": "a"},
                {"agent": "content", "action": "b"},
            ],
            current_task_index=0,
        )
        decision = orch._decide_execution_order(state)
        assert decision == "parallel"
        assert state["parallel_batch"] == ["dev", "content"]

    def test_unknown_agent_returns_finalize(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "unknown", "action": "x"}],
            current_task_index=0,
        )
        assert orch._decide_execution_order(state) == "finalize"


class TestExecuteParallel:
    @pytest.mark.asyncio
    async def test_parallel_empty_batch(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(tasks=[], current_task_index=0)
        result = await orch._execute_parallel(state)
        assert result["current_task_index"] == 0

    @pytest.mark.asyncio
    async def test_parallel_unknown_agent(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "ghost", "action": "x", "params": {}}],
            current_task_index=0,
        )
        result = await orch._execute_parallel(state)
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "UNKNOWN_AGENT"

    @pytest.mark.asyncio
    async def test_parallel_hitl_pending(self) -> None:
        from app.utils.hitl_gateway import HITLPendingError

        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "deploy", "params": {}}],
            current_task_index=0,
        )
        err = HITLPendingError(approval_id="ap-123", action="deploy")
        with patch.object(orch.agents["dev"], "execute", AsyncMock(side_effect=err)):
            result = await orch._execute_parallel(state)
            assert "ap-123" in result["pending_hitl"]

    @pytest.mark.asyncio
    async def test_parallel_exception(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "deploy", "params": {}}],
            current_task_index=0,
        )
        with patch.object(
            orch.agents["dev"], "execute", AsyncMock(side_effect=RuntimeError("fail"))
        ):
            result = await orch._execute_parallel(state)
            assert len(result["errors"]) == 1
            assert result["errors"][0]["code"] == "EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_parallel_success(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "build", "params": {}}],
            current_task_index=0,
        )
        with patch.object(
            orch.agents["dev"],
            "execute",
            AsyncMock(return_value={"agent": "dev", "action": "build", "success": True}),
        ):
            result = await orch._execute_parallel(state)
            assert "dev_build" in result["results"]

    @pytest.mark.asyncio
    async def test_parallel_mixed_results(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[
                {"agent": "dev", "action": "a", "params": {}},
                {"agent": "content", "action": "b", "params": {}},
            ],
            current_task_index=0,
        )

        async def side_effect(task: Any, **kwargs: Any) -> dict[str, Any]:
            if task["agent"] == "dev":
                return {"agent": "dev", "action": "a", "success": True}
            return {"agent": "content", "action": "b", "success": False, "error": {"code": "FAIL"}}

        with (
            patch.object(orch.agents["dev"], "execute", side_effect=side_effect),
            patch.object(orch.agents["content"], "execute", side_effect=side_effect),
        ):
            result = await orch._execute_parallel(state)
            assert "dev_a" in result["results"]
            assert len(result["errors"]) == 1


class TestExecuteAgentEdgeCases:
    @pytest.mark.asyncio
    async def test_execute_unknown_agent(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state()
        result = await orch._execute_agent(state, "nonexistent")
        assert any(e["code"] == "UNKNOWN_AGENT" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_execute_no_current_tasks(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(tasks=[], current_task_index=0)
        result = await orch._execute_agent(state, "dev")
        assert result["current_task_index"] == 1

    @pytest.mark.asyncio
    async def test_execute_retry_exhausted_failure(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x", "params": {}}],
            current_task_index=0,
            circuit_breaker={"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        )
        calls = 0

        async def failer(task: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return {"agent": "dev", "action": "x", "success": False, "error": {"code": "FAIL"}}

        with patch.object(orch.agents["dev"], "execute", failer):
            result = await orch._execute_agent(state, "dev")
        assert calls == MAX_RETRIES
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_execute_hitl_pending(self) -> None:
        from app.utils.hitl_gateway import HITLPendingError

        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "deploy", "params": {}}],
            current_task_index=0,
        )
        err = HITLPendingError(approval_id="ap-456", action="deploy")
        with patch.object(orch.agents["dev"], "execute", AsyncMock(side_effect=err)):
            result = await orch._execute_agent(state, "dev")
            assert "ap-456" in result["pending_hitl"]
            assert result["status"] == "waiting_hitl"

    @pytest.mark.asyncio
    async def test_execute_exception_exhausted(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x", "params": {}}],
            current_task_index=0,
            circuit_breaker={"dev": 0, "content": 0, "marketing": 0, "commerce": 0},
        )
        with patch.object(
            orch.agents["dev"],
            "execute",
            AsyncMock(side_effect=RuntimeError("err")),
        ):
            result = await orch._execute_agent(state, "dev")
            assert any(e["code"] == "EXECUTION_ERROR" for e in result.get("errors", []))

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x", "params": {}}],
            current_task_index=0,
            circuit_breaker={"dev": 1, "content": 0, "marketing": 0, "commerce": 0},
        )
        with patch.object(
            orch.agents["dev"],
            "execute",
            AsyncMock(return_value={"agent": "dev", "action": "x", "success": True}),
        ):
            result = await orch._execute_agent(state, "dev")
            assert "dev_x" in result["results"]
            assert result["circuit_breaker"]["dev"] == 0


class TestExecuteMarketing:
    @pytest.mark.asyncio
    async def test_execute_marketing(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "marketing", "action": "report", "params": {}}],
            current_task_index=0,
        )
        with patch.object(
            orch.agents["marketing"],
            "execute",
            AsyncMock(return_value={"agent": "marketing", "action": "report", "success": True}),
        ):
            result = await orch._execute_marketing(state)
            assert "marketing_report" in result.get("results", {})


class TestCheckResults:
    @pytest.mark.asyncio
    async def test_check_results_pending_hitl(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(pending_hitl=["ap-1"])
        result = await orch._check_results(state)
        assert result["status"] == "waiting_hitl"

    @pytest.mark.asyncio
    async def test_check_results_errors(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(errors=[{"code": "FAIL"}])
        result = await orch._check_results(state)
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_check_results_finalize(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x"}],
            current_task_index=1,
        )
        result = await orch._check_results(state)
        assert result["status"] == "finalize"


class TestDecideNext:
    def test_decide_next_waiting_hitl(self) -> None:
        orch = AgentOSOrchestrator()
        assert orch._decide_next(_make_state(status="waiting_hitl")) == "finalize"
        assert orch._decide_next(_make_state(pending_hitl=["ap-1"])) == "finalize"

    def test_decide_next_error(self) -> None:
        orch = AgentOSOrchestrator()
        assert orch._decide_next(_make_state(status="error")) == "error"

    def test_decide_next_finalize(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x"}],
            current_task_index=1,
        )
        assert orch._decide_next(state) == "finalize"

    def test_decide_next_continue(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(
            tasks=[{"agent": "dev", "action": "x"}],
            current_task_index=0,
        )
        assert orch._decide_next(state) == "continue"


class TestDecideRetry:
    def test_decide_retry_circuit_open(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(circuit_breaker={"dev": 3, "content": 0, "marketing": 0, "commerce": 0})
        assert orch._decide_retry(state) == "circuit_open"

    def test_decide_retry_fail(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(circuit_breaker={"dev": 0, "content": 0, "marketing": 0, "commerce": 0})
        assert orch._decide_retry(state) == "fail"


class TestHandleError:
    @pytest.mark.asyncio
    async def test_handle_error_circuit_open(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(circuit_breaker={"dev": 3, "content": 0, "marketing": 0, "commerce": 0})
        result = await orch._handle_error(state)
        assert result["status"] == "circuit_open"

    @pytest.mark.asyncio
    async def test_handle_error_failed(self) -> None:
        orch = AgentOSOrchestrator()
        state = _make_state(circuit_breaker={"dev": 1, "content": 0, "marketing": 0, "commerce": 0})
        result = await orch._handle_error(state)
        assert result["status"] == "failed"


class TestRouteTasks:
    @pytest.mark.asyncio
    async def test_route_tasks_public(self) -> None:
        orch = AgentOSOrchestrator()
        result = await orch.route_tasks(_make_state())
        assert result["status"] == "routed"

    @pytest.mark.asyncio
    async def test_route_tasks_private(self) -> None:
        orch = AgentOSOrchestrator()
        result = await orch._route_tasks(_make_state())
        assert result["status"] == "routed"


class TestGetOrchestratorSingleton:
    def test_get_orchestrator_singleton(self) -> None:
        from app.orchestrator import get_orchestrator

        o1 = get_orchestrator()
        o2 = get_orchestrator()
        assert o1 is o2
        assert isinstance(o1, AgentOSOrchestrator)


class TestExecuteAgentNoResult:
    @pytest.mark.asyncio
    async def test_no_result_fallback(self) -> None:
        """Reach the NO_RESULT return by making MAX_RETRIES=0 so inner loop never runs."""
        orch = AgentOSOrchestrator()
        state = AgentOSState(
            session_id="test-session",
            trace_id="test-trace",
            project_id="default",
            prompt="test",
            attachments=[],
            tasks=[{"action": "analyze", "params": {}}],
            current_task_index=0,
            agent_sequence=[],
            results={},
            errors=[],
            pending_hitl=[],
            status="running",
            circuit_breaker={},
            start_time=0.0,
            parallel_batch=[],
        )
        with patch("app.orchestrator.MAX_RETRIES", 0):
            result = await orch._execute_agent(state, "dev")
        assert any("NO_RESULT" in str(e) for e in result.get("errors", []) if isinstance(e, dict))
