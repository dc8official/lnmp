from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone
from math import ceil
from typing import Any, List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.models.endpoint_event import EndpointEvent
from app.repositories.endpoint_repo import EndpointRepository
from app.repositories.report_repo import ReportRepository
from app.routers.auth import get_current_user
from app.schemas import (
    APIResponse,
    EventRecord,
    PaginationMeta,
    UptimeReport,
)
from app.services.uptime_calculator import (
    calculate_uptime_denominator_and_percentage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def parse_datetime_param(val: str, is_end: bool = False) -> datetime:
    try:
        if "T" in val or " " in val:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        else:
            d = date.fromisoformat(val)
            if is_end:
                return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
            return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail=f"Invalid ISO 8601 date format: {val}"
        )


def _validate_date_range(
    start_date: Union[date, datetime],
    end_date: Union[date, datetime],
) -> None:
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date.",
        )
    diff_days = (end_date - start_date).total_seconds() / 86400.0
    if diff_days > 730:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 730 days.",
        )


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

    ep_repo = EndpointRepository(db)
    endpoint = await ep_repo.get_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    created_at = endpoint.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)

    effective_start = max(start_dt, created_at)
    now_utc = datetime.now(timezone.utc)
    effective_end = min(end_dt, now_utc)
    total_seconds = max(0, int((effective_end - effective_start).total_seconds()))

    rep_repo = ReportRepository(db)
    unknown_seconds = await rep_repo.get_unknown_seconds(effective_start, end_dt)
    events = await rep_repo.get_uptime_events(endpoint_id, effective_start, end_dt)

    uptime_seconds = 0
    downtime_seconds = 0
    for ev in events:
        duration = 60
        if ev.operational_state == "UP":
            uptime_seconds += duration
        else:
            downtime_seconds += duration

    uptime_percentage = calculate_uptime_denominator_and_percentage(
        created_at=created_at,
        start_time=start_dt,
        end_time=end_dt,
        now_utc=now_utc,
        up_events_count=uptime_seconds // 60,
        unknown_seconds=unknown_seconds,
    )

    incident_count = 0
    prev_state = None
    for ev in events:
        if ev.operational_state == "DOWN" and prev_state != "DOWN":
            incident_count += 1
        prev_state = ev.operational_state

    return APIResponse.success(
        data=UptimeReport(
            endpoint_id=endpoint_id,
            period_start=start_dt,
            period_end=end_dt,
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

    ep_repo = EndpointRepository(db)
    endpoint = await ep_repo.get_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="Endpoint not found.")

    rep_repo = ReportRepository(db)
    limit = page_size
    offset = (page - 1) * page_size

    incidents, total = await rep_repo.get_incidents(
        endpoint_id=endpoint_id,
        start_dt=start_dt,
        end_dt=end_dt,
        limit=limit,
        offset=offset,
    )
    total_pages = ceil(total / page_size) if total > 0 else 1

    return APIResponse.success(
        data=incidents,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get("/events/{endpoint_id}", response_model=APIResponse)
async def get_endpoint_events(
    endpoint_id: UUID,
    start_date: str = Query(...),
    end_date: str = Query(...),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=1500),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_dt = parse_datetime_param(start_date, is_end=False)
    end_dt = parse_datetime_param(end_date, is_end=True)
    _validate_date_range(start_dt, end_dt)

    rep_repo = ReportRepository(db)
    limit = size
    offset = (page - 1) * size

    event_rows, total = await rep_repo.get_events(
        endpoint_id=endpoint_id,
        start_dt=start_dt,
        end_dt=end_dt,
        limit=limit,
        offset=offset,
    )

    events = [
        EventRecord(
            id=ev.id,
            endpoint_id=ev.endpoint_id,
            operational_state=ev.operational_state,
            detailed_state=ev.detailed_state,
            health_score=float(ev.health_score),
            avg_rtt_ms=(
                float(ev.avg_rtt_ms) if ev.avg_rtt_ms is not None else None
            ),
            is_split_event=ev.is_split_event,
            start_time=ev.start_time,
            end_time=ev.end_time,
            duration_seconds=ev.duration_seconds,
            monitoring_cycle_count=ev.monitoring_cycle_count,
        )
        for ev in event_rows
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
class BatchExportRequest(BaseModel):
    endpoint_ids: List[UUID]
    start_time: datetime
    end_time: datetime

    model_config = ConfigDict(from_attributes=True)


def sanitize_csv_field(val: Any) -> str:
    s = str(val) if val is not None else ""
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


async def csv_generator(
    endpoint_ids: List[UUID], start_time: datetime, end_time: datetime
):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Endpoint_ID",
        "Timestamp",
        "Operational_State",
        "Detailed_State",
        "Packet_Success_Rate",
        "Avg_RTT_ms",
    ])
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    offset = 0
    limit = 1000

    try:
        while True:
            rows = []
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(EndpointEvent)
                    .where(
                        EndpointEvent.endpoint_id.in_(endpoint_ids),
                        EndpointEvent.start_time >= start_time,
                        EndpointEvent.start_time <= end_time,
                    )
                    .order_by(EndpointEvent.start_time.asc())
                    .limit(limit)
                    .offset(offset)
                )
                result = await session.execute(stmt)
                rows = result.scalars().all()

            if not rows:
                break

            for ev in rows:
                endpoint_id_str = sanitize_csv_field(str(ev.endpoint_id))
                ts_str = sanitize_csv_field(
                    ev.start_time.isoformat().replace("+00:00", "Z")
                    if ev.start_time
                    else ""
                )
                op_state = sanitize_csv_field(ev.operational_state)
                det_state = sanitize_csv_field(ev.detailed_state)
                success_rate = sanitize_csv_field(
                    ("%.2f" % ev.health_score)
                    if ev.health_score is not None
                    else ""
                )
                rtt_val = sanitize_csv_field(
                    ("%.2f" % ev.avg_rtt_ms)
                    if ev.avg_rtt_ms is not None
                    else ""
                )

                writer.writerow([
                    endpoint_id_str,
                    ts_str,
                    op_state,
                    det_state,
                    success_rate,
                    rtt_val,
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

            if len(rows) < limit:
                break

            offset += limit
    finally:
        output.close()


telemetry_router = APIRouter(prefix="/api/v1/telemetry", tags=["telemetry"])


@telemetry_router.post("/export/batch")
async def batch_export_telemetry(
    request: BatchExportRequest,
    current_user: dict = Depends(get_current_user),
):
    logger.info(
        "Starting batch telemetry CSV streaming export for %d endpoints",
        len(request.endpoint_ids),
    )

    generator = csv_generator(
        request.endpoint_ids, request.start_time, request.end_time
    )

    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=batch_telemetry_export.csv"
        },
    )
