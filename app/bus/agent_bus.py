"""Redis Pub/Sub message bus for agent-to-agent communication.

Agents publish structured messages to named topics and subscribe
to receive messages from other agents, enabling decoupled interactions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from redis.asyncio.client import PubSub, Redis

logger = logging.getLogger(__name__)


@dataclass
class BusMessage:
    """A message sent through the agent bus.

    Attributes:
        id: Unique message identifier (UUID hex string).
        sender: Name of the sending agent.
        recipient: Name of the target agent or ``"broadcast"``.
        topic: Logical channel the message is published to.
        payload: Arbitrary JSON-serialisable data.
        timestamp: Unix timestamp of message creation.
        ttl: Time-to-live in seconds (default 300).
    """

    sender: str
    recipient: str
    topic: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    ttl: int = 300


class AgentBus:
    """Message bus backed by Redis Pub/Sub for agent communication.

    Provides publish, subscribe, and broadcast primitives.  Connection
    errors are caught and logged — the bus degrades gracefully.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        """Initialise the bus with a Redis connection URL.

        Args:
            redis_url: Redis connection string.
        """
        self._redis_url: str = redis_url
        self._redis: Redis | None = None
        self._pubsub: PubSub | None = None
        self._connect()

    def _connect(self) -> None:
        """Create the Redis connection from the configured URL."""
        try:
            self._redis = Redis.from_url(self._redis_url)
        except Exception:
            logger.exception("Failed to connect to Redis at %s", self._redis_url)
            self._redis = None

    async def publish(self, message: BusMessage) -> None:
        """Serialise and publish a message to its topic channel.

        Args:
            message: The message to publish.
        """
        if self._redis is None:
            logger.warning("Redis unavailable — dropping publish to %s", message.topic)
            return
        payload = json.dumps(
            {
                "id": message.id,
                "sender": message.sender,
                "recipient": message.recipient,
                "topic": message.topic,
                "payload": message.payload,
                "timestamp": message.timestamp,
                "ttl": message.ttl,
            }
        )
        try:
            await self._redis.publish(f"agentbus:{message.topic}", payload)
        except Exception:
            logger.exception("Failed to publish message to %s", message.topic)

    async def subscribe(self, topic: str) -> asyncio.Queue[bytes]:
        """Subscribe to a topic and return an async queue of raw messages.

        Args:
            topic: The topic name to subscribe to.

        Returns:
            An asyncio.Queue that receives JSON-encoded message bytes.
        """
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        if self._redis is None:
            logger.warning("Redis unavailable — subscribe to %s is a no-op", topic)
            return queue

        try:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(f"agentbus:{topic}")
        except Exception:
            logger.exception("Failed to subscribe to %s", topic)
            return queue

        async def _listener() -> None:
            assert self._pubsub is not None
            try:
                async for message in self._pubsub.listen():
                    if message["type"] == "message":
                        await queue.put(message["data"])
            except Exception:
                logger.exception("Listener for %s failed", topic)

        asyncio.ensure_future(_listener())
        return queue

    async def broadcast(self, message: BusMessage) -> None:
        """Publish a message to all subscribers of its topic.

        Forces the recipient field to ``"broadcast"`` before publishing.

        Args:
            message: The message to broadcast.
        """
        message.recipient = "broadcast"
        await self.publish(message)

    async def close(self) -> None:
        """Close the Redis connection and underlying PubSub subscription."""
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception:
                logger.exception("Failed to close PubSub")
            finally:
                self._pubsub = None
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                logger.exception("Failed to close Redis connection")
            finally:
                self._redis = None
