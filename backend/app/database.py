from __future__ import annotations

import logging
import sys
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Async engine – used by all application database operations
# ---------------------------------------------------------------------------
async_engine = create_async_engine(
    settings.db_url,
    echo=(settings.logging.level == "DEBUG"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# ---------------------------------------------------------------------------
# Sync engine – intended exclusively for Alembic migrations.
# Do NOT use this engine anywhere else in the application.
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    settings.sync_db_url,
    echo=False,
)

# ---------------------------------------------------------------------------
# Async session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Declarative base class – imported by all ORM model files
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a managed async database session for use in FastAPI routes.

    Commits on clean exit, rolls back on exception, and always closes
    the session in the finally block.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Startup health check
# ---------------------------------------------------------------------------
async def check_database_connection() -> None:
    """Verify database connectivity at application startup.

    Executes a simple ``SELECT 1`` query. Logs an INFO message on
    success; prints a descriptive error to stderr and exits with code 1
    on failure.
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established successfully.")
    except Exception as exc:
        print(
            f"[FATAL] Could not connect to the database: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
