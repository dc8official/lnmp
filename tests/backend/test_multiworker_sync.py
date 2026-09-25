from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.user_session import UserSession
from app.services.session_store import (
    migrate_sessions_pg_to_redis,
    migrate_sessions_redis_to_pg,
)
from app.services.settings_sync import (
    CHANNEL_SETTINGS_SYNC,
    broadcast_settings_reload,
    start_settings_sync_listener,
)


@pytest.mark.anyio
async def test_broadcast_settings_reload():
    """Verifies broadcast_settings_reload publishes to PostgreSQL LISTEN/NOTIFY channel."""
    with patch("app.services.settings_sync.PostgresEventBroker") as MockBroker:
        mock_broker_instance = AsyncMock()
        MockBroker.return_value = mock_broker_instance

        await broadcast_settings_reload(action="DRIVER_RELOAD")

        mock_broker_instance.publish.assert_awaited_once()
        args, _ = mock_broker_instance.publish.call_args
        channel, payload = args
        assert channel == CHANNEL_SETTINGS_SYNC
        assert payload["action"] == "DRIVER_RELOAD"
        assert payload["sender_pid"] == os.getpid()


@pytest.mark.anyio
async def test_settings_sync_listener_reinitializes_on_other_pid():
    """Verifies listener re-initializes driver_manager when receiving reload from another PID."""
    events = [
        {"action": "DRIVER_RELOAD", "sender_pid": 999999},  # Different PID
    ]

    async def mock_subscribe(channel):
        for ev in events:
            yield ev

    mock_broker = MagicMock()
    mock_broker.subscribe = mock_subscribe

    with patch("app.services.settings_sync.PostgresEventBroker", return_value=mock_broker), \
         patch("app.services.driver_manager.driver_manager.initialize", new_callable=AsyncMock) as mock_init:

        task = asyncio.create_task(start_settings_sync_listener())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_init.assert_awaited_once()


@pytest.mark.anyio
async def test_settings_sync_listener_ignores_self_pid():
    """Verifies listener ignores reload events broadcast by its own process PID."""
    events = [
        {"action": "DRIVER_RELOAD", "sender_pid": os.getpid()},  # Self PID
    ]

    async def mock_subscribe(channel):
        for ev in events:
            yield ev

    mock_broker = MagicMock()
    mock_broker.subscribe = mock_subscribe

    with patch("app.services.settings_sync.PostgresEventBroker", return_value=mock_broker), \
         patch("app.services.driver_manager.driver_manager.initialize", new_callable=AsyncMock) as mock_init:

        task = asyncio.create_task(start_settings_sync_listener())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_init.assert_not_awaited()


@pytest.mark.anyio
async def test_migrate_sessions_pg_to_redis():
    """Verifies active unexpired sessions are migrated from PostgreSQL to Redis with TTL."""
    user_id = uuid4()
    now = datetime.now(timezone.utc)
    sess1 = UserSession(
        id=uuid4(),
        user_id=user_id,
        jti="jti-test-token-1",
        created_at=now,
        expires_at=now + timedelta(seconds=3600),
    )
    sess2 = UserSession(
        id=uuid4(),
        user_id=user_id,
        jti="jti-test-token-2",
        created_at=now,
        expires_at=now + timedelta(seconds=7200),
    )

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [sess1, sess2]
    mock_db.execute.return_value = mock_res

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_db

    mock_redis = AsyncMock()

    count = await migrate_sessions_pg_to_redis(mock_factory, mock_redis)
    assert count == 2

    mock_redis.set.assert_awaited_once()
    key, val = mock_redis.set.call_args[0]
    kwargs = mock_redis.set.call_args[1]

    assert key == f"user_sessions:{user_id}"
    assert json.loads(val) == ["jti-test-token-1", "jti-test-token-2"]
    assert kwargs.get("ex") > 0


@pytest.mark.anyio
async def test_migrate_sessions_redis_to_pg():
    """Verifies active sessions in Redis are migrated into PostgreSQL user_sessions."""
    user_id = uuid4()
    redis_key = f"user_sessions:{user_id}".encode("utf-8")

    mock_redis = AsyncMock()

    async def mock_scan_iter(match=None):
        yield redis_key

    mock_redis.scan_iter = mock_scan_iter
    mock_redis.get.return_value = json.dumps(["jti-redis-token-1", "jti-redis-token-2"]).encode("utf-8")
    mock_redis.ttl.return_value = 3600

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # None existing
    mock_db.execute.return_value = mock_res

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = mock_db

    count = await migrate_sessions_redis_to_pg(mock_redis, mock_factory)
    assert count == 2
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_awaited_once()
