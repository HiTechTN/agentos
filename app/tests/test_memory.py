import pytest

from app.memory.cache import Cache, get_cache
from app.memory.session import SessionManager, get_session_manager


@pytest.mark.asyncio
async def test_cache_set_get():
    cache = Cache()
    await cache.set("test_key", {"hello": "world"}, ttl=60)
    value = await cache.get("test_key")
    assert value == {"hello": "world"}


@pytest.mark.asyncio
async def test_cache_delete():
    cache = Cache()
    await cache.set("delete_test", "value", ttl=60)
    await cache.delete("delete_test")
    value = await cache.get("delete_test")
    assert value is None


@pytest.mark.asyncio
async def test_cache_flush():
    cache = Cache()
    await cache.set("flush_test1", "v1", ttl=60)
    await cache.set("flush_test2", "v2", ttl=60)
    await cache.flush()
    assert await cache.get("flush_test1") is None
    assert await cache.get("flush_test2") is None


@pytest.mark.asyncio
async def test_cache_default_ttl():
    cache = Cache()
    await cache.set("ttl_test", "value")
    value = await cache.get("ttl_test")
    assert value == "value"


@pytest.mark.asyncio
async def test_session_create():
    sm = SessionManager()
    session_id = await sm.create("test-project", "test-workflow")
    assert session_id is not None
    assert len(session_id) > 0


@pytest.mark.asyncio
async def test_session_get():
    sm = SessionManager()
    session_id = await sm.create("test-project", "test-workflow")
    session = await sm.get(session_id)
    assert session is not None
    assert session["project_id"] == "test-project"
    assert session["workflow_id"] == "test-workflow"


@pytest.mark.asyncio
async def test_session_update():
    sm = SessionManager()
    session_id = await sm.create("test-project")
    updated = await sm.update(session_id, context={"key": "value"}, status="completed")
    assert updated is True


@pytest.mark.asyncio
async def test_session_nonexistent():
    sm = SessionManager()
    session = await sm.get("nonexistent-id")
    assert session is None


@pytest.mark.asyncio
async def test_session_status_update():
    sm = SessionManager()
    session_id = await sm.create("test-project")
    await sm.update(session_id, status="running")
    session = await sm.get(session_id)
    assert session["status"] == "running"


@pytest.mark.asyncio
async def test_session_singleton():
    s1 = get_session_manager()
    s2 = get_session_manager()
    assert s1 is s2


@pytest.mark.asyncio
async def test_cache_singleton():
    c1 = get_cache()
    c2 = get_cache()
    assert c1 is c2
