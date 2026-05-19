import pytest

from app.utils.hitl_gateway import HITLGateway, HITLPendingError, HITLRejectedError


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
    assert "approval_id" in str(exc.value.approval_id)


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
    from app.orchestrator import AgentOSOrchestrator, AgentOSState

    orch = AgentOSOrchestrator()
    hitl = orch.hitl_gateway

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

    result = await orch._execute_dev(state)
    assert "pending_hitl" in result
    assert len(result.get("pending_hitl", [])) > 0


@pytest.mark.asyncio
async def test_hitl_approve_endpoint():
    from app.main import app
    from httpx import AsyncClient, ASGITransport

    from app.utils.hitl_gateway import get_hitl_gateway

    hitl = get_hitl_gateway()

    with pytest.raises(HITLPendingError) as exc:
        try:
            await hitl.request_approval("test", "test", "deploy", {})
        except HITLPendingError:
            raise

    approval_id = exc.value.approval_id
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/hitl/approve", json={"approval_id": approval_id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
