from __future__ import annotations
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from monitoring.gap_handler import (
    open_monitoring_gap,
    close_monitoring_gap,
    resolve_startup_state,
    get_active_gap,
)


@pytest.mark.anyio
async def test_resolve_startup_state_applies_chunk_pruning():
    """Verify that resolve_startup_state executes TimescaleDB override and bounds cleanup to 7-day window."""
    mock_db = AsyncMock()
    
    # Track all executed SQL statements and params
    executed_statements = []

    async def fake_execute(statement, params=None):
        executed_statements.append((str(statement), params or {}))
        result = MagicMock()
        result.fetchone.return_value = None  # No existing unclosed gap
        result.rowcount = 42
        return result

    mock_db.execute.side_effect = fake_execute

    await resolve_startup_state(mock_db)

    # We expect 3 statements:
    # 1. DO block setting timescaledb.max_tuples_decompressed_per_dml_transaction = 0
    # 2. SELECT from monitoring_service_events
    # 3. UPDATE endpoint_events with chunk pruning filter
    assert len(executed_statements) == 3

    # Check statement 1 (TimescaleDB override)
    stmt_override, _ = executed_statements[0]
    assert "timescaledb.max_tuples_decompressed_per_dml_transaction" in stmt_override
    assert "set_config" in stmt_override

    # Check statement 2 (SELECT monitoring_service_events)
    stmt_select, _ = executed_statements[1]
    assert "SELECT id, start_time, event_type" in stmt_select
    assert "FROM monitoring_service_events" in stmt_select

    # Check statement 3 (UPDATE endpoint_events with partition filter)
    stmt_update, params_update = executed_statements[2]
    assert "UPDATE endpoint_events" in stmt_update
    assert "WHERE end_time IS NULL" in stmt_update
    assert "AND start_time >= :window_start" in stmt_update

    assert "close_time" in params_update
    assert "window_start" in params_update

    close_time = params_update["close_time"]
    window_start = params_update["window_start"]
    delta = close_time - window_start
    assert delta.total_seconds() == pytest.approx(7 * 86400, abs=1)


@pytest.mark.anyio
async def test_resolve_startup_state_with_active_gap():
    """Verify that resolve_startup_state closes active gap and computes window from gap start_time."""
    mock_db = AsyncMock()
    executed_statements = []

    gap_id = uuid4()
    gap_start = datetime(2026, 9, 10, 14, 30, 0, tzinfo=timezone.utc)

    gap_row = MagicMock()
    gap_row.id = gap_id
    gap_row.start_time = gap_start
    gap_row.event_type = "power_failure"

    step = 0

    async def fake_execute(statement, params=None):
        nonlocal step
        executed_statements.append((str(statement), params or {}))
        result = MagicMock()
        if "SELECT id, start_time, event_type" in str(statement):
            result.fetchone.return_value = gap_row
        else:
            result.fetchone.return_value = None
        result.rowcount = 10
        step += 1
        return result

    mock_db.execute.side_effect = fake_execute

    await resolve_startup_state(mock_db)

    # Statements:
    # 1. DO block (TimescaleDB override)
    # 2. SELECT monitoring_service_events
    # 3. UPDATE monitoring_service_events (close_monitoring_gap)
    # 4. UPDATE endpoint_events (chunk pruning with gap_start as close_time)
    assert len(executed_statements) == 4

    stmt_close_gap, params_close_gap = executed_statements[2]
    assert "UPDATE monitoring_service_events" in stmt_close_gap
    assert params_close_gap["gap_id"] == str(gap_id)

    stmt_update_events, params_update_events = executed_statements[3]
    assert "UPDATE endpoint_events" in stmt_update_events
    assert "AND start_time >= :window_start" in stmt_update_events
    assert params_update_events["close_time"] == gap_start
    assert params_update_events["window_start"] == gap_start - timedelta(days=7)


@pytest.mark.anyio
async def test_open_monitoring_gap_applies_chunk_pruning():
    """Verify that open_monitoring_gap bounds event closure with start_time >= :window_start."""
    mock_db = AsyncMock()
    executed_statements = []

    dummy_gap_id = uuid4()
    insert_row = MagicMock()
    insert_row.id = dummy_gap_id

    async def fake_execute(statement, params=None):
        executed_statements.append((str(statement), params or {}))
        result = MagicMock()
        result.fetchone.return_value = insert_row
        result.rowcount = 5
        return result

    mock_db.execute.side_effect = fake_execute

    returned_id = await open_monitoring_gap(
        mock_db,
        event_type="scheduled_maintenance",
        description="Core switch firmware upgrade",
    )

    assert returned_id == dummy_gap_id
    assert len(executed_statements) == 2

    # Statement 1: INSERT into monitoring_service_events
    stmt_insert, params_insert = executed_statements[0]
    assert "INSERT INTO monitoring_service_events" in stmt_insert
    assert params_insert["event_type"] == "scheduled_maintenance"

    # Statement 2: UPDATE endpoint_events with chunk pruning
    stmt_update, params_update = executed_statements[1]
    assert "UPDATE endpoint_events" in stmt_update
    assert "WHERE end_time IS NULL" in stmt_update
    assert "AND start_time >= :window_start" in stmt_update

    assert "gap_time" in params_update
    assert "window_start" in params_update
    delta = params_update["gap_time"] - params_update["window_start"]
    assert delta.total_seconds() == pytest.approx(7 * 86400, abs=1)


@pytest.mark.anyio
async def test_resolve_startup_state_timescaledb_override_graceful_fallback():
    """Verify that if TimescaleDB override fails (e.g. extension not present), startup continues cleanly."""
    mock_db = AsyncMock()
    executed_statements = []

    async def fake_execute(statement, params=None):
        if "timescaledb.max_tuples_decompressed_per_dml_transaction" in str(statement):
            raise Exception("permission denied or extension not available")
        executed_statements.append((str(statement), params or {}))
        result = MagicMock()
        result.fetchone.return_value = None
        result.rowcount = 0
        return result

    mock_db.execute.side_effect = fake_execute

    # Must NOT raise exception despite the DO block throwing
    await resolve_startup_state(mock_db)

    # SELECT and UPDATE must still execute successfully
    assert len(executed_statements) == 2
    assert "FROM monitoring_service_events" in executed_statements[0][0]
    assert "UPDATE endpoint_events" in executed_statements[1][0]
