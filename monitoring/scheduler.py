from __future__ import annotations
import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

def seconds_until_next_midnight() -> float:
    now = datetime.now(timezone.utc)
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        0, 0, 0,
        tzinfo=timezone.utc,
    )
    return (next_midnight - now).total_seconds()

async def execute_daily_split(
    db: AsyncSession,
) -> dict[UUID, UUID]:
    split_moment = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    close_time = split_moment - timedelta(seconds=1)
    open_time = split_moment

    query_open = text("""
        SELECT
            ee.id,
            ee.endpoint_id,
            ee.operational_state,
            ee.detailed_state,
            ee.success_count,
            ee.failed_count,
            ee.health_score,
            ee.avg_rtt_ms
        FROM endpoint_events ee
        JOIN endpoints e ON ee.endpoint_id = e.id
        WHERE ee.end_time IS NULL
          AND e.endpoint_status = 'ACTIVE'
          AND e.monitoring_enabled = TRUE
    """)
    
    result = await db.execute(query_open)
    rows = result.fetchall()

    if not rows:
        logger.info("Daily split: no open events found. Nothing to split.")
        return {}

    updates = {}

    query_close = text("""
        UPDATE endpoint_events
        SET
            end_time = :close_time,
            duration_seconds = EXTRACT(
                EPOCH FROM (:close_time - start_time)
            )::BIGINT
        WHERE id = :event_id
    """)

    query_insert = text("""
        INSERT INTO endpoint_events (
            endpoint_id,
            operational_state,
            detailed_state,
            success_count,
            failed_count,
            health_score,
            avg_rtt_ms,
            is_split_event,
            start_time,
            monitoring_cycle_count
        ) VALUES (
            :endpoint_id,
            :operational_state,
            :detailed_state,
            :success_count,
            :failed_count,
            :health_score,
            :avg_rtt_ms,
            true,
            :open_time,
            0
        ) RETURNING id
    """)

    for row in rows:
        await db.execute(
            query_close,
            {
                "event_id": str(row.id),
                "close_time": close_time,
            }
        )

        insert_result = await db.execute(
            query_insert,
            {
                "endpoint_id": str(row.endpoint_id),
                "operational_state": row.operational_state,
                "detailed_state": row.detailed_state,
                "success_count": row.success_count,
                "failed_count": row.failed_count,
                "health_score": row.health_score,
                "avg_rtt_ms": row.avg_rtt_ms,
                "open_time": open_time,
            }
        )
        
        new_event_row = insert_result.fetchone()
        if new_event_row:
            new_event_id = new_event_row.id
            updates[UUID(str(row.endpoint_id))] = UUID(str(new_event_id))

    logger.info(f"Daily split complete: {len(rows)} events split at {open_time}")
    
    return updates

async def run_daily_split_scheduler(
    on_split_complete: Callable[[dict[UUID, UUID]], Awaitable[None]],
) -> None:
    while True:
        wait_seconds = seconds_until_next_midnight()
        logger.info(
            "Daily split scheduled in %.0f seconds (%.1f hours)",
            wait_seconds,
            wait_seconds / 3600,
        )
        await asyncio.sleep(wait_seconds)

        try:
            async with AsyncSessionLocal() as db:
                updates = await execute_daily_split(db)
                await db.commit()

            if updates:
                await on_split_complete(updates)

        except Exception as e:
            logger.error(
                "Daily split failed with error: %s: %s",
                type(e).__name__,
                e,
            )
