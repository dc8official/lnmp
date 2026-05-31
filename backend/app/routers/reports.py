from __future__ import annotations
from datetime import date, datetime, timezone
from math import ceil
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.auth import get_current_user
from app.schemas import (
    APIResponse,
    EventRecord,
    IncidentRecord,
    PaginationMeta,
    UptimeReport,
)

router = APIRouter(prefix="/reports", tags=["reports"])

def _build_period(
    start_date: date,
    end_date: date,
) -> tuple[datetime, datetime]:
    period_start = datetime(start_date.year, start_date.month,
                            start_date.day, 0, 0, 0,
                            tzinfo=timezone.utc)
    period_end   = datetime(end_date.year, end_date.month,
                            end_date.day, 23, 59, 59,
                            tzinfo=timezone.utc)
    return period_start, period_end

def _validate_date_range(
    start_date: date,
    end_date: date,
) -> None:
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date."
        )
    if (end_date - start_date).days > 730:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 730 days."
        )

def _worse_state(state_a: str, state_b: str) -> str:
    priority = {
        "DOWN": 4,
        "DOWN-UNSTABLE": 3,
        "UP-UNSTABLE": 2,
        "UP": 1,
    }
    if priority.get(state_b, 0) > priority.get(state_a, 0):
        return state_b
    return state_a

@router.get("/uptime/{endpoint_id}", response_model=APIResponse)
async def get_uptime_report(
    endpoint_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(start_date, end_date)

    query_exists = text("""
        SELECT id, created_at FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    result_exists = await db.execute(query_exists, {"endpoint_id": str(endpoint_id)})
    exists_row = result_exists.fetchone()
    if not exists_row:
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    period_start, period_end = _build_period(start_date, end_date)
    
    # Cap period_start to the creation time so we don't skew uptime statistics for time before registration
    # Ensure exists_row.created_at is timezone-aware UTC
    created_at = exists_row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    effective_start = max(period_start, created_at)
    total_seconds = max(1, int((period_end - effective_start).total_seconds()))

    query_gaps = text("""
        SELECT start_time, end_time
        FROM monitoring_service_events
        WHERE start_time < :period_end
          AND (end_time > :effective_start OR end_time IS NULL)
    """)
    result_gaps = await db.execute(query_gaps, {
        "effective_start": effective_start,
        "period_end": period_end,
    })
    gap_rows = result_gaps.fetchall()

    unknown_seconds = 0
    for row in gap_rows:
        row_start_time = row.start_time
        if row_start_time.tzinfo is None:
            row_start_time = row_start_time.replace(tzinfo=timezone.utc)
        row_end_time = row.end_time
        if row_end_time is not None and row_end_time.tzinfo is None:
            row_end_time = row_end_time.replace(tzinfo=timezone.utc)

        gap_start = max(row_start_time, effective_start)
        gap_end = min(
            row_end_time if row_end_time is not None else period_end,
            period_end
        )
        unknown_seconds += max(
            0, int((gap_end - gap_start).total_seconds())
        )

    query_events = text("""
        SELECT operational_state, start_time, end_time
        FROM endpoint_events
        WHERE endpoint_id = :endpoint_id
          AND start_time >= :effective_start
          AND start_time <= :period_end
        ORDER BY start_time ASC
    """)
    result_events = await db.execute(query_events, {
        "endpoint_id": str(endpoint_id),
        "effective_start": effective_start,
        "period_end": period_end,
    })
    event_rows = result_events.fetchall()

    uptime_seconds = 0
    downtime_seconds = 0

    for row in event_rows:
        duration = 60
        if row.operational_state == 'UP':
            uptime_seconds += duration
        else:
            downtime_seconds += duration

    denominator = total_seconds - unknown_seconds
    if denominator <= 0:
        uptime_percentage = 0.0
    else:
        uptime_percentage = round(
            (uptime_seconds / denominator) * 100, 2
        )
    uptime_percentage = max(0.0, min(100.0, uptime_percentage))

    incident_count = 0
    prev_state = None
    for row in event_rows:
        if row.operational_state == 'DOWN' and prev_state != 'DOWN':
            incident_count += 1
        prev_state = row.operational_state

    return APIResponse.success(
        data=UptimeReport(
            endpoint_id=endpoint_id,
            period_start=period_start,
            period_end=period_end,
            total_seconds=total_seconds,
            uptime_seconds=uptime_seconds,
            downtime_seconds=downtime_seconds,
            unknown_seconds=unknown_seconds,
            uptime_percentage=uptime_percentage,
            incident_count=incident_count,
        )
    )

@router.get("/incidents/{endpoint_id}", response_model=APIResponse)
async def get_incident_report(
    endpoint_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(start_date, end_date)

    query_exists = text("""
        SELECT id FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    result_exists = await db.execute(query_exists, {"endpoint_id": str(endpoint_id)})
    if not result_exists.fetchone():
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    period_start, period_end = _build_period(start_date, end_date)

    query_events = text("""
        SELECT
            operational_state,
            detailed_state,
            start_time,
            end_time
        FROM endpoint_events
        WHERE endpoint_id = :endpoint_id
          AND start_time >= :period_start
          AND start_time <= :period_end
        ORDER BY start_time ASC
    """)
    result_events = await db.execute(query_events, {
        "endpoint_id": str(endpoint_id),
        "period_start": period_start,
        "period_end": period_end,
    })
    event_rows = result_events.fetchall()

    incidents = []
    current_incident = None

    for row in event_rows:
        if row.operational_state == 'DOWN':
            if current_incident is None:
                current_incident = {
                    "start": row.start_time,
                    "end": row.end_time,
                    "peak": row.detailed_state,
                    "count": 1,
                }
            else:
                current_incident["end"] = row.end_time
                current_incident["count"] += 1
                current_incident["peak"] = _worse_state(
                    current_incident["peak"],
                    row.detailed_state,
                )
        else:
            if current_incident is not None:
                incidents.append(current_incident)
                current_incident = None

    if current_incident is not None:
        incidents.append(current_incident)

    for inc in incidents:
        inc["duration_seconds"] = inc["count"] * 60

    total = len(incidents)
    total_pages = ceil(total / page_size) if total > 0 else 1
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_incidents = incidents[start_idx:end_idx]

    records = [
        IncidentRecord(
            endpoint_id=endpoint_id,
            incident_start=inc["start"],
            incident_end=inc["end"],
            duration_seconds=inc["duration_seconds"],
            peak_detailed_state=inc["peak"],
            contributing_event_count=inc["count"],
        )
        for inc in page_incidents
    ]

    return APIResponse.success(
        data=records,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )

@router.get("/events/{endpoint_id}")
async def get_endpoint_events(
    endpoint_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _validate_date_range(start_date, end_date)
    period_start, period_end = _build_period(
        start_date, end_date
    )

    result = await db.execute(
        text("""
            SELECT id, endpoint_id, operational_state,
                   detailed_state, health_score, avg_rtt_ms,
                   is_split_event, start_time, end_time,
                   duration_seconds, monitoring_cycle_count
            FROM endpoint_events
            WHERE endpoint_id = :endpoint_id
              AND start_time >= :period_start
              AND start_time <= :period_end
            ORDER BY start_time ASC
        """),
        {
            "endpoint_id": str(endpoint_id),
            "period_start": period_start,
            "period_end": period_end,
        },
    )
    rows = result.fetchall()

    events = [
        EventRecord(
            id=UUID(str(row.id)),
            endpoint_id=UUID(str(row.endpoint_id)),
            operational_state=row.operational_state,
            detailed_state=row.detailed_state,
            health_score=float(row.health_score),
            avg_rtt_ms=float(row.avg_rtt_ms)
                       if row.avg_rtt_ms is not None
                       else None,
            is_split_event=row.is_split_event,
            start_time=row.start_time,
            end_time=row.end_time,
            duration_seconds=row.duration_seconds,
            monitoring_cycle_count=row.monitoring_cycle_count,
        )
        for row in rows
    ]

    return APIResponse.success(
        data=events,
        meta=PaginationMeta(
            total=len(events),
            page=1,
            page_size=len(events),
            total_pages=1,
        ),
    )
