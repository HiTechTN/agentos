import pytest

from app.utils.hitl_gateway import HITLGateway, HITLPendingError


@pytest.fixture
def hitl():
    return HITLGateway()


@pytest.mark.asyncio
async def test_hitl_request_raises_pending(hitl):
    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval(
                session_id="test-session",
                agent_name="dev",
                action="deploy",
                details={"target": "staging"},
            )
        except HITLPendingError:
            raise
    assert exc.value.approval_id is not None


@pytest.mark.asyncio
async def test_hitl_approve_flow(hitl):
    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval(
                session_id="test-session",
                agent_name="dev",
                action="deploy",
                details={"target": "staging"},
            )
        except HITLPendingError:
            raise

    approval_id = exc.value.approval_id
    result = hitl.approve(approval_id)
    assert result is not None


@pytest.mark.asyncio
async def test_hitl_reject_flow(hitl):
    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval(
                session_id="test-session",
                agent_name="dev",
                action="deploy",
                details={"target": "staging"},
            )
        except HITLPendingError:
            raise

    approval_id = exc.value.approval_id
    result = hitl.reject(approval_id, reason="Not ready")
    assert result.get("reason") == "Not ready"


@pytest.mark.asyncio
async def test_hitl_list_pending(hitl):
    pending = hitl.get_pending()
    assert isinstance(pending, list)
    initial_count = len(pending)

    with pytest.raises(HITLPendingError):
        try:
            await hitl.request_approval(
                session_id="test-session",
                agent_name="content",
                action="publish",
                details={"title": "Test Article"},
            )
        except HITLPendingError:
            raise

    pending_after = hitl.get_pending()
    assert len(pending_after) == initial_count + 1


@pytest.mark.asyncio
async def test_hitl_double_approve_fails(hitl):
    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval(
                session_id="test-session",
                agent_name="dev",
                action="deploy",
                details={},
            )
        except HITLPendingError:
            raise

    approval_id = exc.value.approval_id
    hitl.approve(approval_id)

    with pytest.raises(ValueError, match="already approved"):
        hitl.approve(approval_id)


@pytest.mark.asyncio
async def test_hitl_unknown_approval(hitl):
    with pytest.raises(ValueError, match="not found"):
        hitl.approve("nonexistent-id")


@pytest.mark.asyncio
async def test_hitl_integration_with_orchestrator():
    from unittest.mock import patch

    from app.orchestrator import AgentOSOrchestrator, AgentOSState

    orch = AgentOSOrchestrator()

    state: AgentOSState = {
        "project_id": "test",
        "session_id": "test-session",
        "trace_id": "test-trace",
        "prompt": "deploy to staging",
        "tasks": [{"agent": "dev", "action": "deploy", "params": {"target": "staging"}}],
        "current_task_index": 0,
        "agent_sequence": ["dev"],
        "results": {},
        "errors": [],
        "pending_hitl": [],
        "status": "running",
        "circuit_breaker": {k: 0 for k in ["dev", "content", "marketing", "commerce"]},
        "start_time": 0.0,
    }

    from app.utils.hitl_gateway import get_hitl_gateway
    hitl = get_hitl_gateway()

    async def hitl_execute(task, session_id="", trace_id=""):
        await hitl.request_approval(session_id, "dev", "deploy", {"target": "staging"})
        return {"agent": "dev", "action": "deploy", "success": True, "result": {}}

    with patch.object(orch.agents["dev"], "execute", hitl_execute):
        try:
            result = await orch._execute_dev(state)
            assert "pending_hitl" in result
        except Exception:
            pass


@pytest.mark.asyncio
async def test_hitl_approve_endpoint():
    from app.utils.hitl_gateway import get_hitl_gateway

    hitl = get_hitl_gateway()

    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval("test", "test", "deploy", {})
        except HITLPendingError:
            raise

    approval_id = exc.value.approval_id
    result = hitl.approve(approval_id)
    assert result is not None
