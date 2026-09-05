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
        payload = json.dumps(event_data)
        async with self.session_factory() as db:
            try:
                query = text("SELECT pg_notify(:channel, :payload);")
                await db.execute(query, {"channel": channel, "payload": payload})
                await db.commit()
            except Exception as e:
                logger.error("PostgresEventBroker.publish error: %s", e)
                raise

    async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        True real-time LISTEN subscription using a dedicated unpooled asyncpg connection
        with automated reconnection loop.
        """
        import asyncio
        from app.config import settings

        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        def _on_notification(connection, pid, ch, payload):
            try:
                data = json.loads(payload)
            except Exception:
                data = {"raw": payload}
            queue.put_nowait(data)

        while True:
            conn = None
            try:
                import asyncpg

                conn = await asyncpg.connect(
                    host=settings.database.host,
                    port=settings.database.port,
                    user=settings.database.user,
                    password=settings.database.password,
                    database=settings.database.name,
                )
                await conn.add_listener(channel, _on_notification)
                logger.info("PostgresEventBroker: connected & listening to '%s'", channel)
                while True:
                    event = await queue.get()
                    yield event
            except (asyncio.CancelledError, GeneratorExit):
                break
            except Exception as exc:
                logger.warning(
                    "PostgresEventBroker: listener error on channel '%s': %s. Reconnecting in 2s...",
                    channel,
                    exc,
                )
                await asyncio.sleep(2.0)
            finally:
                if conn and not conn.is_closed():
                    try:
                        await conn.remove_listener(channel, _on_notification)
                        await conn.close()
                    except Exception:
                        pass


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
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass
