from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from math import ceil
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.routers.auth import get_current_user
from app.schemas import (
    APIResponse,
    EventRecord,
    IncidentRecord,
    PaginationMeta,
    UptimeReport,
)
from app.services.uptime_calculator import (
    calculate_uptime_denominator_and_percentage,
    get_unknown_seconds_for_period,
)

router = APIRouter(prefix="/reports", tags=["reports"])

def parse_datetime_param(val: str, is_end: bool = False) -> datetime:
    # Try parsing as ISO datetime
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    
    # Try parsing as date
    try:
        d = date.fromisoformat(val)
        if is_end:
            return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        else:
            return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date/datetime format: {val}")

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
    start_date: str = Query(...),
    end_date: str = Query(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_dt = parse_datetime_param(start_date, is_end=False)
    end_dt = parse_datetime_param(end_date, is_end=True)
    _validate_date_range(start_dt, end_dt)

    query_exists = text("""
        SELECT id, created_at FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    result_exists = await db.execute(query_exists, {"endpoint_id": str(endpoint_id)})
    exists_row = result_exists.fetchone()
    if not exists_row:
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    period_start, period_end = start_dt, end_dt
    
    # Cap period_start to the creation time so we don't skew uptime statistics for time before registration
    # Ensure exists_row.created_at is timezone-aware UTC
    created_at = exists_row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    effective_start = max(period_start, created_at)
    now_utc = datetime.now(timezone.utc)
    effective_end = min(period_end, now_utc)
    total_seconds = max(0, int((effective_end - effective_start).total_seconds()))

    unknown_seconds = await get_unknown_seconds_for_period(db, effective_start, period_end)

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

    uptime_percentage = calculate_uptime_denominator_and_percentage(
        created_at=created_at,
        start_time=period_start,
        end_time=period_end,
        now_utc=now_utc,
        up_events_count=uptime_seconds // 60,
        unknown_seconds=unknown_seconds
    )

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
    start_date: str = Query(...),
    end_date: str = Query(...),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_dt = parse_datetime_param(start_date, is_end=False)
    end_dt = parse_datetime_param(end_date, is_end=True)
    _validate_date_range(start_dt, end_dt)

    query_exists = text("""
        SELECT id FROM endpoints
        WHERE id = :endpoint_id
          AND endpoint_status != 'DELETED'
    """)
    result_exists = await db.execute(query_exists, {"endpoint_id": str(endpoint_id)})
    if not result_exists.fetchone():
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    period_start, period_end = start_dt, end_dt

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
    start_date: str = Query(...),
    end_date: str = Query(...),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=250),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_dt = parse_datetime_param(start_date, is_end=False)
    end_dt = parse_datetime_param(end_date, is_end=True)
    _validate_date_range(start_dt, end_dt)
    period_start, period_end = start_dt, end_dt

    # Fetch total count of matched events
    count_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM endpoint_events
            WHERE endpoint_id = :endpoint_id
              AND start_time >= :period_start
              AND start_time <= :period_end
        """),
        {
            "endpoint_id": str(endpoint_id),
            "period_start": period_start,
            "period_end": period_end,
        },
    )
    total = count_result.scalar() or 0

    # Fetch paginated transition events
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
            LIMIT :limit OFFSET :offset
        """),
        {
            "endpoint_id": str(endpoint_id),
            "period_start": period_start,
            "period_end": period_end,
            "limit": size,
            "offset": (page - 1) * size,
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

    total_pages = ceil(total / size) if total > 0 else 1

    return APIResponse.success(
        data=events,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=size,
            total_pages=total_pages,
        ),
    )


# ---------------------------------------------------------------------------
# Batch Telemetry Export Streaming API
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

class BatchExportRequest(BaseModel):
    endpoint_ids: List[UUID]
    start_time: datetime
    end_time: datetime

async def csv_generator(endpoint_ids: List[UUID], start_time: datetime, end_time: datetime):
    # Yield CSV Header on startup
    yield "Endpoint_ID,Timestamp,Operational_State,Detailed_State,Packet_Success_Rate,Avg_RTT_ms\n"
    
    offset = 0
    limit = 1000
    
    while True:
        rows = []
        # Database connections must remain completely encapsulated within short-lived context managers
        async with AsyncSessionLocal() as session:
            # Open an asynchronous server-side cursor to PostgreSQL via stream()
            result = await session.stream(
                text("""
                    SELECT endpoint_id, start_time, operational_state, detailed_state, health_score, avg_rtt_ms
                    FROM endpoint_events
                    WHERE endpoint_id = ANY(:endpoint_ids)
                      AND start_time >= :start_time
                      AND start_time <= :end_time
                    ORDER BY start_time ASC
                    LIMIT :limit OFFSET :offset
                """),
                {
                    "endpoint_ids": [str(eid) for eid in endpoint_ids],
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": limit,
                    "offset": offset,
                }
            )
            
            async for row in result:
                rows.append(row)
                
        if not rows:
            break
            
        for row in rows:
            endpoint_id_str = str(row.endpoint_id)
            ts_str = row.start_time.isoformat().replace("+00:00", "Z") if row.start_time else ""
            op_state = row.operational_state
            det_state = row.detailed_state
            success_rate = ("%.2f" % row.health_score) if row.health_score is not None else ""
            rtt_val = ("%.2f" % row.avg_rtt_ms) if row.avg_rtt_ms is not None else ""
            
            yield "%s,%s,%s,%s,%s,%s\n" % (endpoint_id_str, ts_str, op_state, det_state, success_rate, rtt_val)
            
        if len(rows) < limit:
            break
            
        offset += limit

telemetry_router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

@telemetry_router.post("/export/batch")
async def batch_export_telemetry(
    request: BatchExportRequest,
    current_user: dict = Depends(get_current_user),
):
    logger.info("Starting batch telemetry CSV streaming export for %d endpoints", len(request.endpoint_ids))
    
    generator = csv_generator(request.endpoint_ids, request.start_time, request.end_time)
    
    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=batch_telemetry_export.csv"
        }
    )
