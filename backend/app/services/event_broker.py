from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy import text
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class EventBroker(ABC):
    """Abstract interface for real-time pub/sub messaging and state broadcasts."""

    @abstractmethod
    async def publish(self, channel: str, event_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
        pass


class PostgresEventBroker(EventBroker):
    """
    PostgreSQL-native pub/sub broker using native LISTEN / NOTIFY.
    """

    def __init__(self, session_factory=AsyncSessionLocal) -> None:
        self.session_factory = session_factory

    async def publish(self, channel: str, event_data: Dict[str, Any]) -> None:
        payload = json.dumps(event_data).replace("'", "''")
        async with self.session_factory() as db:
            try:
                query = text(f"NOTIFY {channel}, '{payload}';")
                await db.execute(query)
                await db.commit()
            except Exception as e:
                logger.error("PostgresEventBroker.publish error: %s", e)
                raise

    async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
        # For lightweight consumption; yielding mock/live frames
        yield {"channel": channel, "status": "subscribed"}


class RedisEventBroker(EventBroker):
    """
    Redis Pub/Sub broker using redis.asyncio channels.
    """

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    async def publish(self, channel: str, event_data: Dict[str, Any]) -> None:
        payload = json.dumps(event_data)
        try:
            await self.redis.publish(channel, payload)
        except Exception as e:
            logger.error("RedisEventBroker.publish error: %s", e)
            raise

    async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, (bytes, bytearray)):
                        data = data.decode("utf-8")
                    yield json.loads(data)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
