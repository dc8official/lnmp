import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.models.endpoint_event import EndpointEvent
from app.repositories.report_repo import ReportRepository
from app.services.uptime_calculator import calculate_uptime_denominator_and_percentage


def test_clamped_uptime_multi_day_open_event():
    """Verify BUG-01: calculate_uptime_denominator_and_percentage reports 100.0% for healthy active events."""
    now_utc = datetime.now(timezone.utc)
    created_at = now_utc - timedelta(days=30)
    start_time = now_utc - timedelta(hours=24)
    end_time = now_utc

    # Clamped to the 24-hour window, uptime_seconds = 86400 (24h * 3600s).
    uptime_seconds = 86400

    result = calculate_uptime_denominator_and_percentage(
        created_at=created_at,
        start_time=start_time,
        end_time=end_time,
        now_utc=now_utc,
        up_events_count=1,
        gap_intervals=[],
        uptime_seconds=uptime_seconds,
    )

    assert result == 100.0


@pytest.mark.anyio
async def test_report_repo_get_uptime_events_boundary_overlap():
    """Verify BUG-01b: get_uptime_events includes boundary-overlapping open events."""
    mock_db = AsyncMock()
    repo = ReportRepository(mock_db)

    ep_id = uuid4()
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(hours=24)
    end_dt = now

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [
        EndpointEvent(
            id=uuid4(),
            endpoint_id=ep_id,
            start_time=now - timedelta(days=3),  # Started 3 days ago
            end_time=None,                       # Still open
            operational_state="UP",
            detailed_state="UP",
        )
    ]
    mock_res = MagicMock()
    mock_res.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_res

    events = await repo.get_uptime_events(ep_id, start_dt, end_dt)
    assert len(events) == 1
    assert events[0].operational_state == "UP"

    # Verify query where clause includes start_time <= end_dt and end_time IS NULL / >= start_dt
    query_str = str(mock_db.execute.call_args[0][0])
    assert "start_time <=" in query_str or "start_time <" in query_str
    assert "end_time IS NULL" in query_str or "end_time is null" in query_str.lower()


@pytest.mark.anyio
async def test_endpoint_repo_list_with_stats_no_ambiguous_columns():
    """Verify list_with_stats query does not contain duplicate column aliases causing Ambiguous column name errors."""
    from app.repositories.endpoint_repo import EndpointRepository
    mock_db = AsyncMock()
    repo = EndpointRepository(mock_db)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    mock_res = MagicMock()
    mock_res.all.return_value = []
    mock_db.execute.return_value = mock_res

    rows = await repo.list_with_stats(since_utc=since, now_utc=now)
    assert rows == []

    # Verify query column labels in the select statement
    stmt = mock_db.execute.call_args[0][0]
    col_names = [c.name if hasattr(c, "name") else str(c) for c in stmt.selected_columns]
    uptime_sec_count = col_names.count("uptime_seconds")
    assert uptime_sec_count == 1, f"Expected 1 'uptime_seconds' column, got {uptime_sec_count}"

