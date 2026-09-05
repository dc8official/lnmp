from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)


class SessionStore(ABC):
    """Abstract interface for user session management and concurrency control."""

    @abstractmethod
    async def register_session(
        self,
        user_id: str,
        jti: str,
        max_sessions: int = 2,
        ttl_seconds: int = 86400,
    ) -> None:
        pass

    @abstractmethod
    async def is_session_active(self, user_id: str, jti: Optional[str]) -> bool:
        pass

    @abstractmethod
    async def invalidate_session(self, user_id: str, jti: Optional[str]) -> None:
        pass

    @abstractmethod
    async def invalidate_all_user_sessions(self, user_id: str) -> None:
        pass


class PostgresSessionStore(SessionStore):
    """
    PostgreSQL-native session driver using user_sessions table
    with indexed TTL auto-cleanup and FIFO eviction.
    """

    def __init__(self, session_factory=AsyncSessionLocal) -> None:
        self.session_factory = session_factory

    async def register_session(
        self,
        user_id: str,
        jti: str,
        max_sessions: int = 2,
        ttl_seconds: int = 86400,
    ) -> None:
        try:
            u_uuid = UUID(str(user_id))
        except (ValueError, TypeError):
            return

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        async with self.session_factory() as db:
            try:
                # 1. Clean up globally expired sessions for this user
                await db.execute(
                    delete(UserSession).where(
                        UserSession.user_id == u_uuid,
                        UserSession.expires_at <= now,
                    )
                )

                # 2. Insert new session
                new_session = UserSession(
                    user_id=u_uuid,
                    jti=jti,
                    created_at=now,
                    expires_at=expires_at,
                )
                db.add(new_session)
                await db.flush()

                # 3. FIFO session eviction if count > max_sessions
                stmt = (
                    select(UserSession.id)
                    .where(
                        UserSession.user_id == u_uuid,
                        UserSession.expires_at > now,
                    )
                    .order_by(UserSession.created_at.desc())
                )
                res = await db.execute(stmt)
                active_ids = []
                if hasattr(res, "scalars") and hasattr(res.scalars(), "all"):
                    scalars_res = res.scalars().all()
                    if hasattr(scalars_res, "__iter__"):
                        active_ids = list(scalars_res)
                elif hasattr(res, "fetchall"):
                    rows = res.fetchall()
                    if hasattr(rows, "__iter__"):
                        active_ids = [
                            row[0] if isinstance(row, (tuple, list)) else getattr(row, "id", row)
                            for row in rows
                        ]

                if len(active_ids) > max_sessions:
                    excess_ids = active_ids[max_sessions:]
                    await db.execute(
                        delete(UserSession).where(UserSession.id.in_(excess_ids))
                    )

                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("PostgresSessionStore.register_session error: %s", e)

    async def is_session_active(self, user_id: str, jti: Optional[str]) -> bool:
        if not jti:
            return False
        try:
            u_uuid = UUID(str(user_id))
        except (ValueError, TypeError):
            return False

        now = datetime.now(timezone.utc)
        async with self.session_factory() as db:
            try:
                stmt = select(UserSession.id).where(
                    UserSession.user_id == u_uuid,
                    UserSession.jti == jti,
                    UserSession.expires_at > now,
                ).limit(1)
                res = await db.execute(stmt)
                row = res.scalar_one_or_none() if hasattr(res, "scalar_one_or_none") else (res.fetchone() if hasattr(res, "fetchone") else None)
                return row is not None
            except Exception as e:
                logger.error("PostgresSessionStore.is_session_active error: %s", e)
                return False

    async def invalidate_session(self, user_id: str, jti: Optional[str]) -> None:
        if not jti:
            return
        try:
            u_uuid = UUID(str(user_id))
        except (ValueError, TypeError):
            return

        async with self.session_factory() as db:
            try:
                await db.execute(
                    delete(UserSession).where(
                        UserSession.user_id == u_uuid,
                        UserSession.jti == jti,
                    )
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("PostgresSessionStore.invalidate_session error: %s", e)

    async def invalidate_all_user_sessions(self, user_id: str) -> None:
        try:
            u_uuid = UUID(str(user_id))
        except (ValueError, TypeError):
            return

        async with self.session_factory() as db:
            try:
                await db.execute(
                    delete(UserSession).where(UserSession.user_id == u_uuid)
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.error("PostgresSessionStore.invalidate_all_user_sessions error: %s", e)


class RedisSessionStore(SessionStore):
    """
    Redis-accelerated session driver using redis.asyncio with key TTL auto-expiration.
    """

    def __init__(self, redis_client: Any) -> None:
        self.redis = redis_client

    def _get_key(self, user_id: str) -> str:
        return f"user_sessions:{user_id}"

    async def register_session(
        self,
        user_id: str,
        jti: str,
        max_sessions: int = 2,
        ttl_seconds: int = 86400,
    ) -> None:
        key = self._get_key(user_id)
        try:
            raw = await self.redis.get(key)
            sessions: List[str] = json.loads(raw) if raw else []
            sessions.append(jti)
            if len(sessions) > max_sessions:
                sessions = sessions[-max_sessions:]
            await self.redis.set(key, json.dumps(sessions), ex=ttl_seconds)
        except Exception as e:
            logger.error("RedisSessionStore.register_session error: %s", e)
            raise

    async def is_session_active(self, user_id: str, jti: Optional[str]) -> bool:
        if not jti:
            return False
        key = self._get_key(user_id)
        try:
            raw = await self.redis.get(key)
            if not raw:
                return False
            sessions: List[str] = json.loads(raw)
            return jti in sessions
        except Exception as e:
            logger.error("RedisSessionStore.is_session_active error: %s", e)
            return False

    async def invalidate_session(self, user_id: str, jti: Optional[str]) -> None:
        if not jti:
            return
        key = self._get_key(user_id)
        try:
            raw = await self.redis.get(key)
            if raw:
                sessions: List[str] = [s for s in json.loads(raw) if s != jti]
                if sessions:
                    ttl = await self.redis.ttl(key)
                    ex = max(ttl, 60) if ttl > 0 else 86400
                    await self.redis.set(key, json.dumps(sessions), ex=ex)
                else:
                    await self.redis.delete(key)
        except Exception as e:
            logger.error("RedisSessionStore.invalidate_session error: %s", e)
            raise

    async def invalidate_all_user_sessions(self, user_id: str) -> None:
        key = self._get_key(user_id)
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error("RedisSessionStore.invalidate_all_user_sessions error: %s", e)
            raise
