from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.timezone_utils import get_local_timezone

def calculate_uptime_denominator_and_percentage(
    created_at: datetime,
    start_time: datetime,
    end_time: datetime,
    now_utc: datetime,
    up_events_count: int,
    unknown_seconds: int = 0
) -> float:
    # Ensure all datetime objects are timezone-aware in the local timezone
    local_tz = get_local_timezone()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=local_tz)
    else:
        created_at = created_at.astimezone(local_tz)

    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=local_tz)
    else:
        start_time = start_time.astimezone(local_tz)

    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=local_tz)
    else:
        end_time = end_time.astimezone(local_tz)

    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=local_tz)
    else:
        now_utc = now_utc.astimezone(local_tz)

    # Calculate true operational lifespan within the queried block
    effective_start = max(start_time, created_at)
    effective_end = min(end_time, now_utc)

    total_seconds = max(0, int((effective_end - effective_start).total_seconds()))
    denominator = total_seconds - unknown_seconds

    if denominator <= 0:
        return 100.0  # Return 100% availability if no elapsing time exists yet
    
    uptime_seconds = up_events_count * 60
    percentage = (uptime_seconds / denominator) * 100.0
    return max(0.0, min(100.0, round(percentage, 2)))

async def get_unknown_seconds_for_period(
    db: AsyncSession,
    effective_start: datetime,
    period_end: datetime
) -> int:
    # Ensure all datetime objects are timezone-aware in local timezone
    local_tz = get_local_timezone()
    if effective_start.tzinfo is None:
        effective_start = effective_start.replace(tzinfo=local_tz)
    else:
        effective_start = effective_start.astimezone(local_tz)

    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=local_tz)
    else:
        period_end = period_end.astimezone(local_tz)

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
            row_start_time = row_start_time.replace(tzinfo=local_tz)
        else:
            row_start_time = row_start_time.astimezone(local_tz)

        row_end_time = row.end_time
        if row_end_time is not None:
            if row_end_time.tzinfo is None:
                row_end_time = row_end_time.replace(tzinfo=local_tz)
            else:
                row_end_time = row_end_time.astimezone(local_tz)

        gap_start = max(row_start_time, effective_start)
        gap_end = min(
            row_end_time if row_end_time is not None else period_end,
            period_end
        )
        unknown_seconds += max(
            0, int((gap_end - gap_start).total_seconds())
        )
    return unknown_seconds
