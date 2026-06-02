"""Tests for the agent message bus."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bus.agent_bus import AgentBus, BusMessage


@pytest.fixture
def mock_redis():
    with patch("app.bus.agent_bus.Redis") as mock_cls:
        instance = MagicMock()
        instance.publish = AsyncMock()
        instance.aclose = AsyncMock()
        mock_cls.from_url.return_value = instance
        yield instance


@pytest.fixture
def bus(mock_redis):
    return AgentBus(redis_url="redis://localhost:6379/0")


@pytest.mark.asyncio
async def test_publish_calls_redis(bus, mock_redis):
    msg = BusMessage(
        sender="agent_a",
        recipient="agent_b",
        topic="test_topic",
        payload={"key": "value"},
    )
    await bus.publish(msg)
    mock_redis.publish.assert_called_once()
    args, _ = mock_redis.publish.call_args
    assert args[0] == "agentbus:test_topic"


@pytest.mark.asyncio
async def test_broadcast_sets_recipient(bus, mock_redis):
    msg = BusMessage(
        sender="agent_a",
        recipient="agent_b",
        topic="test_topic",
        payload={"key": "value"},
    )
    await bus.broadcast(msg)
    assert msg.recipient == "broadcast"
    mock_redis.publish.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_creates_queue(bus, mock_redis):
    pubsub_mock = MagicMock()
    pubsub_mock.subscribe = AsyncMock()
    pubsub_mock.listen = AsyncMock()
    mock_redis.pubsub = MagicMock(return_value=pubsub_mock)
    queue = await bus.subscribe("test_topic")
    assert isinstance(queue, asyncio.Queue)
    pubsub_mock.subscribe.assert_called_once_with("agentbus:test_topic")


@pytest.mark.asyncio
async def test_close_calls_redis_close(bus, mock_redis):
    pubsub_mock = MagicMock()
    pubsub_mock.unsubscribe = AsyncMock()
    pubsub_mock.close = AsyncMock()
    bus._pubsub = pubsub_mock
    await bus.close()
    pubsub_mock.unsubscribe.assert_called_once()
    pubsub_mock.close.assert_called_once()
    mock_redis.aclose.assert_called_once()
    assert bus._redis is None
    assert bus._pubsub is None


@pytest.mark.asyncio
async def test_publish_no_redis(bus):
    bus._redis = None
    msg = BusMessage(
        sender="agent_a",
        recipient="agent_b",
        topic="test_topic",
        payload={},
    )
    await bus.publish(msg)


def test_bus_message_creation():
    msg = BusMessage(
        sender="agent_a",
        recipient="agent_b",
        topic="test_topic",
        payload={"data": 42},
    )
    assert msg.sender == "agent_a"
    assert msg.recipient == "agent_b"
    assert msg.topic == "test_topic"
    assert msg.payload == {"data": 42}
    assert msg.ttl == 300
    assert isinstance(msg.id, str)
    assert len(msg.id) > 0
    assert isinstance(msg.timestamp, float)


def test_bus_message_ttl():
    msg = BusMessage(sender="a", recipient="b", topic="t", payload={})
    assert msg.ttl == 300

    msg2 = BusMessage(sender="a", recipient="b", topic="t", payload={}, ttl=60)
    assert msg2.ttl == 60
