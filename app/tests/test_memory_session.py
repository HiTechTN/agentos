from unittest.mock import patch

import pytest

from app.memory.session import SessionManager, get_session_manager


@pytest.mark.asyncio
async def test_session_create_json_fallback():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project", "test-workflow")
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert session_id in sm._sessions
    assert sm._sessions[session_id]["project_id"] == "test-project"
    assert sm._sessions[session_id]["workflow_id"] == "test-workflow"
    assert sm._sessions[session_id]["status"] == "pending"


@pytest.mark.asyncio
async def test_session_create_default_workflow():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project")
    session = await sm.get(session_id)
    assert session is not None
    assert session["workflow_id"].startswith("wf-")


@pytest.mark.asyncio
async def test_session_get_json_fallback():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project", "test-workflow")
    session = await sm.get(session_id)
    assert session is not None
    assert session["id"] == session_id
    assert session["project_id"] == "test-project"
    assert session["workflow_id"] == "test-workflow"
    assert session["context"] == {}


@pytest.mark.asyncio
async def test_session_get_nonexistent():
    sm = SessionManager()
    sm._use_json_fallback = True
    session = await sm.get("nonexistent-id")
    assert session is None


@pytest.mark.asyncio
async def test_session_update_context_and_status():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project", "test-workflow")
    updated = await sm.update(session_id, context={"key": "value"}, status="running")
    assert updated is True
    session = await sm.get(session_id)
    assert session["context"] == {"key": "value"}
    assert session["status"] == "running"


@pytest.mark.asyncio
async def test_session_update_status_only():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project")
    await sm.update(session_id, status="completed")
    session = await sm.get(session_id)
    assert session["status"] == "completed"
    assert session["context"] == {}


@pytest.mark.asyncio
async def test_session_update_context_only():
    sm = SessionManager()
    sm._use_json_fallback = True
    session_id = await sm.create("test-project")
    await sm.update(session_id, context={"answer": 42})
    session = await sm.get(session_id)
    assert session["context"] == {"answer": 42}
    assert session["status"] == "pending"


@pytest.mark.asyncio
async def test_session_update_nonexistent():
    sm = SessionManager()
    sm._use_json_fallback = True
    result = await sm.update("nonexistent-id", status="running")
    assert result is False


@pytest.mark.asyncio
async def test_session_init_db_failure_triggers_fallback():
    sm = SessionManager()
    with patch.object(sm, "_init_db", side_effect=Exception("DB unavailable")):
        session_id = await sm.create("test-project", "test-workflow")
    assert isinstance(session_id, str)
    session = await sm.get(session_id)
    assert session is not None
    assert session["project_id"] == "test-project"


@pytest.mark.asyncio
async def test_session_singleton():
    s1 = get_session_manager()
    s2 = get_session_manager()
    assert s1 is s2
