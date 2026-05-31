from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

async def open_monitoring_gap(
    db: AsyncSession,
    event_type: str,
    description: Optional[str] = None,
) -> UUID:
    gap_start = datetime.now(timezone.utc)
    
    query_insert = text("""
        INSERT INTO monitoring_service_events (
            event_type,
            description,
            start_time
        ) VALUES (
            :event_type,
            :description,
            :start_time
        ) RETURNING id
    """)
    insert_result = await db.execute(
        query_insert,
        {
            "event_type": event_type,
            "description": description,
            "start_time": gap_start,
        }
    )
    row = insert_result.fetchone()
    gap_id = row.id if row else None
    
    query_update = text("""
        UPDATE endpoint_events
        SET
            end_time = :gap_time,
            duration_seconds = EXTRACT(
                EPOCH FROM (:gap_time - start_time)
            )::BIGINT
        WHERE end_time IS NULL
    """)
    update_result = await db.execute(
        query_update,
        {
            "gap_time": gap_start,
        }
    )
    closed_count = update_result.rowcount
    
    logger.info("Monitoring gap opened (type=%s): %s endpoint events closed at %s", event_type, closed_count, gap_start)
    
    return UUID(str(gap_id))

async def close_monitoring_gap(
    db: AsyncSession,
    gap_id: UUID,
) -> None:
    end_time = datetime.now(timezone.utc)
    
    query = text("""
        UPDATE monitoring_service_events
        SET
            end_time = :end_time,
            duration_seconds = EXTRACT(
                EPOCH FROM (:end_time - start_time)
            )::BIGINT
        WHERE id = :gap_id
    """)
    await db.execute(
        query,
        {
            "end_time": end_time,
            "gap_id": str(gap_id),
        }
    )
    
    logger.info("Monitoring gap %s closed at %s", gap_id, end_time)

async def resolve_startup_state(db: AsyncSession) -> None:
    query_select = text("""
        SELECT id, start_time, event_type
        FROM monitoring_service_events
        WHERE end_time IS NULL
        ORDER BY start_time DESC
        LIMIT 1
    """)
    select_result = await db.execute(query_select)
    row = select_result.fetchone()

    if row:
        logger.warning(
            "Startup: found unresolved monitoring gap from %s "
            "(type=%s). Closing.",
            row.start_time,
            row.event_type,
        )
        gap_close_time = row.start_time
        await close_monitoring_gap(db, UUID(str(row.id)))
    else:
        gap_close_time = datetime.now(timezone.utc)

    query_update = text("""
        UPDATE endpoint_events
        SET
            end_time = :close_time,
            duration_seconds = EXTRACT(
                EPOCH FROM (:close_time - start_time)
            )::BIGINT
        WHERE end_time IS NULL
    """)
    update_result = await db.execute(
        query_update,
        {"close_time": gap_close_time},
    )
    closed_count = update_result.rowcount

    if closed_count > 0:
        logger.warning(
            "Startup cleanup: closed %d orphaned open "
            "endpoint events at %s.",
            closed_count,
            gap_close_time,
        )
    else:
        logger.info(
            "Startup: no open endpoint events found. "
            "Clean state."
        )

async def get_active_gap(
    db: AsyncSession,
) -> Optional[tuple[UUID, datetime]]:
    query = text("""
        SELECT id, start_time
        FROM monitoring_service_events
        WHERE end_time IS NULL
        ORDER BY start_time DESC
        LIMIT 1
    """)
    result = await db.execute(query)
    row = result.fetchone()
    
    if row:
        return (UUID(str(row.id)), row.start_time)
    return None
