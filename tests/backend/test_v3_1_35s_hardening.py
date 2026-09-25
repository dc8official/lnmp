import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest

from app.services.uptime_calculator import calculate_uptime_denominator_and_percentage
from monitoring.ping import PingResult
from monitoring.state_machine import EndpointState, StateMachine


@pytest.mark.anyio
async def test_state_machine_24h_event_rollover():
    """Verify STAB-01: StateMachine rolls over continuous events exceeding 24 hours."""
    sm = StateMachine(confirmation_threshold=1)
    ep_id = uuid4()
    old_event_id = uuid4()
    new_event_id = uuid4()

    state = EndpointState(
        endpoint_id=ep_id,
        active_event_id=old_event_id,
        confirmed_operational_state="UP",
        confirmed_detailed_state="UP",
        pending_detailed_state=None,
        pending_cycle_count=0,
        hostname="server-lts.corp",
        ip_address="192.168.1.50",
    )

    ping_result = PingResult(
        success_count=5,
        failed_count=0,
        avg_rtt_ms=12.5,
    )

    # Mock DB: duration check returns 86500 seconds (> 86400s / 24 hours)
    mock_db = AsyncMock()
    mock_dur_res = MagicMock()
    mock_dur_row = MagicMock()
    mock_dur_row.dur = 86500
    mock_dur_res.fetchone.return_value = mock_dur_row

    # New event insertion mock returns new_event_id
    mock_new_event_row = MagicMock()
    mock_new_event_row.id = new_event_id
    mock_insert_res = MagicMock()
    mock_insert_res.fetchone.return_value = mock_new_event_row

    # Return mock_dur_res on first query (dur check), mock_insert_res on subsequent queries
    mock_db.execute.side_effect = [
        mock_dur_res,       # SELECT EXTRACT(EPOCH FROM ...)
        MagicMock(),        # UPDATE endpoint_events SET end_time = ...
        mock_insert_res,    # INSERT INTO endpoint_events ... RETURNING id
    ]

    next_state = await sm.process_cycle(state, ping_result, mock_db)

    # State remained UP, but active_event_id rotated to the new event
    assert next_state.confirmed_detailed_state == "UP"
    assert next_state.active_event_id == new_event_id
    assert mock_db.execute.call_count == 3


@pytest.mark.anyio
async def test_state_machine_under_24h_no_rollover():
    """Verify STAB-01: StateMachine updates in-place when event is under 24 hours."""
    sm = StateMachine(confirmation_threshold=1)
    ep_id = uuid4()
    active_event_id = uuid4()

    state = EndpointState(
        endpoint_id=ep_id,
        active_event_id=active_event_id,
        confirmed_operational_state="UP",
        confirmed_detailed_state="UP",
        pending_detailed_state=None,
        pending_cycle_count=0,
        hostname="server-lts.corp",
        ip_address="192.168.1.50",
    )

    ping_result = PingResult(
        success_count=5,
        failed_count=0,
        avg_rtt_ms=10.0,
    )

    # Mock DB: duration check returns 3600 seconds (< 86400s)
    mock_db = AsyncMock()
    mock_dur_res = MagicMock()
    mock_dur_row = MagicMock()
    mock_dur_row.dur = 3600
    mock_dur_res.fetchone.return_value = mock_dur_row

    mock_update_res = MagicMock()
    mock_update_res.rowcount = 1

    mock_db.execute.side_effect = [
        mock_dur_res,       # SELECT EXTRACT(EPOCH FROM ...)
        mock_update_res,    # UPDATE endpoint_events SET duration_seconds = ...
    ]

    next_state = await sm.process_cycle(state, ping_result, mock_db)

    # State remained UP, active_event_id was preserved
    assert next_state.confirmed_detailed_state == "UP"
    assert next_state.active_event_id == active_event_id
    assert mock_db.execute.call_count == 2


def test_clamped_uptime_multi_day_open_event():
    """Verify BUG-01 / DAT-01: calculate_uptime_denominator_and_percentage reports 100.0% for healthy active events."""
    now_utc = datetime.now(timezone.utc)
    created_at = now_utc - timedelta(days=30)
    start_time = now_utc - timedelta(hours=24)
    end_time = now_utc

    # Endpoint has an event that started 5 days ago and is still open (active).
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
