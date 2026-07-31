from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring.ping import PingResult, classify_ping_result

logger = logging.getLogger(__name__)


@dataclass
class EndpointState:
    """Per-endpoint in-memory state tracked by the monitoring engine."""

    endpoint_id: UUID
    active_event_id: UUID
    confirmed_operational_state: str
    confirmed_detailed_state: str
    pending_detailed_state: Optional[str] = field(default=None)
    pending_cycle_count: int = field(default=0)


class StateMachine:
    """
    Core state machine for the monitoring engine.

    Manages per-endpoint in-memory state, applies the N-cycle confirmation
    logic before committing state transitions, and executes all required
    database operations when transitions are committed.

    This class has no knowledge of scheduling, ICMP mechanics, or the HTTP API.
    """

    def __init__(self, confirmation_threshold: int = 3) -> None:
        self.confirmation_threshold = confirmation_threshold

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def initialize_endpoint(
        self,
        endpoint_id: UUID,
        db: AsyncSession,
    ) -> Optional[EndpointState]:
        """
        Called once per endpoint when the monitoring engine starts.

        Looks for the latest event in the database for this endpoint to load the state.
        """
        row = (
            await db.execute(
                text(
                    """
                    SELECT id, operational_state, detailed_state
                    FROM endpoint_events
                    WHERE endpoint_id = :endpoint_id
                    ORDER BY start_time DESC
                    LIMIT 1
                    """
                ),
                {"endpoint_id": str(endpoint_id)},
            )
        ).fetchone()

        if row is None:
            return None

        return EndpointState(
            endpoint_id=endpoint_id,
            active_event_id=row.id,
            confirmed_operational_state=row.operational_state,
            confirmed_detailed_state=row.detailed_state,
            pending_detailed_state=None,
            pending_cycle_count=0,
        )

    async def create_initial_event(
        self,
        endpoint_id: UUID,
        result: PingResult,
        db: AsyncSession,
        baseline: Optional[Tuple[float, float]] = None,
    ) -> EndpointState:
        """
        Called on the first ping cycle for an endpoint when no existing
        event was found. Creates the first event row and returns the initial
        EndpointState.
        """
        baseline_mean = baseline[0] if baseline else None
        baseline_stddev = baseline[1] if baseline else None
        operational_state, detailed_state = classify_ping_result(
            result, baseline_mean=baseline_mean, baseline_stddev=baseline_stddev
        )
        start_time = datetime.now().astimezone()
        health_score = result.health_score

        row = (
            await db.execute(
                text(
                    """
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
                        end_time,
                        duration_seconds,
                        monitoring_cycle_count
                    ) VALUES (
                        :endpoint_id,
                        :operational_state,
                        :detailed_state,
                        :success_count,
                        :failed_count,
                        :health_score,
                        :avg_rtt_ms,
                        false,
                        :start_time,
                        :end_time,
                        0,
                        1
                    ) RETURNING id
                    """
                ),
                {
                    "endpoint_id": str(endpoint_id),
                    "operational_state": operational_state,
                    "detailed_state": detailed_state,
                    "success_count": result.success_count,
                    "failed_count": result.failed_count,
                    "health_score": health_score,
                    "avg_rtt_ms": result.avg_rtt_ms,
                    "start_time": start_time,
                    "end_time": start_time,
                },
            )
        ).fetchone()

        logger.info(
            "Created initial event %s for endpoint %s (state=%s)",
            row.id,
            endpoint_id,
            detailed_state,
        )

        return EndpointState(
            endpoint_id=endpoint_id,
            active_event_id=row.id,
            confirmed_operational_state=operational_state,
            confirmed_detailed_state=detailed_state,
            pending_detailed_state=None,
            pending_cycle_count=0,
        )

    async def process_cycle(
        self,
        state: EndpointState,
        result: PingResult,
        db: AsyncSession,
        baseline: Optional[Tuple[float, float]] = None,
    ) -> EndpointState:
        """
        The core method, called on every monitoring cycle for an endpoint
        that already has an EndpointState.

        Applies the N-cycle confirmation logic, updates the database, and
        returns the updated EndpointState.
        """
        # Step 1: Classify the new result with baseline evaluation.
        baseline_mean = baseline[0] if baseline else None
        baseline_stddev = baseline[1] if baseline else None
        new_operational_state, new_detailed_state = classify_ping_result(
            result, baseline_mean=baseline_mean, baseline_stddev=baseline_stddev
        )

        # Step 2: Determine what to do based on state comparison.

        # CASE A: No change — endpoint remains in the confirmed state.
        if new_detailed_state == state.confirmed_detailed_state:
            next_state = EndpointState(
                endpoint_id=state.endpoint_id,
                active_event_id=state.active_event_id,
                confirmed_operational_state=state.confirmed_operational_state,
                confirmed_detailed_state=state.confirmed_detailed_state,
                pending_detailed_state=None,
                pending_cycle_count=0,
            )

        # CASE B: A potential transition is occurring.

        # Sub-case B1: The pending state is continuing.
        elif new_detailed_state == state.pending_detailed_state:
            new_pending_count = state.pending_cycle_count + 1

            # Not yet at the confirmation threshold — keep accumulating.
            if new_pending_count < self.confirmation_threshold:
                next_state = EndpointState(
                    endpoint_id=state.endpoint_id,
                    active_event_id=state.active_event_id,
                    confirmed_operational_state=state.confirmed_operational_state,
                    confirmed_detailed_state=state.confirmed_detailed_state,
                    pending_detailed_state=new_detailed_state,
                    pending_cycle_count=new_pending_count,
                )
            else:
                # Transition confirmed!
                next_state = EndpointState(
                    endpoint_id=state.endpoint_id,
                    active_event_id=state.active_event_id,
                    confirmed_operational_state=new_operational_state,
                    confirmed_detailed_state=new_detailed_state,
                    pending_detailed_state=None,
                    pending_cycle_count=0,
                )
                logger.info(
                    "Committed transition for endpoint %s: %s -> %s",
                    state.endpoint_id,
                    state.confirmed_detailed_state,
                    new_detailed_state,
                )

                # V1.5 State Transition Hooks: Differential RCA and Recovery
                if state.confirmed_operational_state != new_operational_state:
                    import asyncio
                    from app.services.rca_engine import run_differential_rca, handle_endpoint_recovery

                    if new_operational_state == "DOWN":
                        # Fetch enable_rca configuration
                        rca_check = await db.execute(
                            text("SELECT enable_rca FROM endpoints WHERE id = :id"),
                            {"id": str(state.endpoint_id)},
                        )
                        rca_row = rca_check.fetchone()
                        if rca_row and getattr(rca_row, "enable_rca", True):
                            asyncio.create_task(run_differential_rca(state.endpoint_id))
                    elif new_operational_state == "UP":
                        ep_check = await db.execute(
                            text("SELECT host(ip_address) AS ip_address FROM endpoints WHERE id = :id"),
                            {"id": str(state.endpoint_id)},
                        )
                        ep_row = ep_check.fetchone()
                        if ep_row and ep_row.ip_address:
                            asyncio.create_task(
                                handle_endpoint_recovery(state.endpoint_id, str(ep_row.ip_address))
                            )

        # Sub-case B2: No transition was pending, or the pending state has
        # changed to a third state. Reset the pending tracker.
        else:
            next_state = EndpointState(
                endpoint_id=state.endpoint_id,
                active_event_id=state.active_event_id,
                confirmed_operational_state=state.confirmed_operational_state,
                confirmed_detailed_state=state.confirmed_detailed_state,
                pending_detailed_state=new_detailed_state,
                pending_cycle_count=1,
            )

        # Step 3: Insert the record for this cycle to the database.
        execution_time = datetime.now().astimezone()

        row = (
            await db.execute(
                text(
                    """
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
                        end_time,
                        duration_seconds,
                        monitoring_cycle_count
                    ) VALUES (
                        :endpoint_id,
                        :operational_state,
                        :detailed_state,
                        :success_count,
                        :failed_count,
                        :health_score,
                        :avg_rtt_ms,
                        false,
                        :start_time,
                        :end_time,
                        0,
                        1
                    ) RETURNING id
                    """
                ),
                {
                    "endpoint_id": str(state.endpoint_id),
                    "operational_state": next_state.confirmed_operational_state,
                    "detailed_state": next_state.confirmed_detailed_state,
                    "success_count": result.success_count,
                    "failed_count": result.failed_count,
                    "health_score": result.health_score,
                    "avg_rtt_ms": result.avg_rtt_ms,
                    "start_time": execution_time,
                    "end_time": execution_time,
                },
            )
        ).fetchone()

        next_state.active_event_id = row.id
        return next_state
