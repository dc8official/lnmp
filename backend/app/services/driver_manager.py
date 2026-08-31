from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.system_setting import SystemSetting
from app.services.event_broker import EventBroker, PostgresEventBroker, RedisEventBroker
from app.services.session_store import (
    PostgresSessionStore,
    RedisSessionStore,
    SessionStore,
)

logger = logging.getLogger(__name__)


class StorageDriverManager:
    """
    Manages dual-driver storage and event pub/sub brokers.
    Dynamically routes between PostgreSQL-Native and Redis-Accelerated drivers
    with automated health-checking and graceful fallback.
    """

    def __init__(self) -> None:
        self._session_store: Optional[SessionStore] = None
        self._event_broker: Optional[EventBroker] = None
        self._redis_client = None
        self._driver_mode: str = "postgres"  # "postgres" | "redis"

    async def initialize(self) -> None:
        """Initializes drivers based on system settings and Redis connectivity."""
        redis_enabled = False
        redis_host = "127.0.0.1"
        redis_port = 6379
        redis_db = 0

        # Check system_settings if available
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(SystemSetting).where(
                    SystemSetting.setting_key == "performance_mode"
                )
                res = await db.execute(stmt)
                row = res.scalar_one_or_none()
                if row and str(row.setting_value).lower() in ("true", "1", "redis"):
                    redis_enabled = True
        except Exception:
            pass

        # Check config settings if performance_mode is configured
        if hasattr(settings, "redis") and getattr(settings.redis, "enabled", False):
            redis_enabled = True
            redis_host = getattr(settings.redis, "host", "127.0.0.1")
            redis_port = getattr(settings.redis, "port", 6379)
            redis_db = getattr(settings.redis, "db", 0)

        if redis_enabled:
            try:
                import redis.asyncio as aioredis

                client = aioredis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    socket_connect_timeout=2.0,
                )
                await client.ping()
                self._redis_client = client
                self._session_store = RedisSessionStore(client)
                self._event_broker = RedisEventBroker(client)
                self._driver_mode = "redis"
                logger.info(
                    "StorageDriverManager: Redis-Accelerated driver initialized successfully at %s:%d/%d",
                    redis_host,
                    redis_port,
                    redis_db,
                )
                return
            except Exception as e:
                logger.warning(
                    "StorageDriverManager: Redis unreachable (%s). Falling back gracefully to PostgreSQL-Native driver.",
                    e,
                )

        # Fallback to PostgreSQL-Native driver
        self._session_store = PostgresSessionStore(AsyncSessionLocal)
        self._event_broker = PostgresEventBroker(AsyncSessionLocal)
        self._driver_mode = "postgres"
        logger.info("StorageDriverManager: PostgreSQL-Native driver active.")

    def get_session_store(self) -> SessionStore:
        if self._session_store is None:
            self._session_store = PostgresSessionStore(AsyncSessionLocal)
        return self._session_store

    def get_event_broker(self) -> EventBroker:
        if self._event_broker is None:
            self._event_broker = PostgresEventBroker(AsyncSessionLocal)
        return self._event_broker

    @property
    def driver_mode(self) -> str:
        return self._driver_mode


# Global storage driver manager singleton
driver_manager = StorageDriverManager()
