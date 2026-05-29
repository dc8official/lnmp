from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
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

        Looks for an existing open event in the database for this endpoint.
        If found, loads it as the current state. If not found, returns None
        so the engine can call create_initial_event on the next ping cycle.
        """
        row = (
            await db.execute(
                text(
                    """
                    SELECT id, operational_state, detailed_state
                    FROM endpoint_events
                    WHERE endpoint_id = :endpoint_id
                      AND end_time IS NULL
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
    ) -> EndpointState:
        """
        Called on the first ping cycle for an endpoint when no existing open
        event was found. Creates the first event row and returns the initial
        EndpointState.
        """
        operational_state, detailed_state = classify_ping_result(result)
        start_time = datetime.now(timezone.utc)
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
    ) -> EndpointState:
        """
        The core method, called on every monitoring cycle for an endpoint
        that already has an EndpointState.

        Applies the N-cycle confirmation logic, updates the database, and
        returns the updated EndpointState.
        """
        # Step 1: Classify the new result.
        new_operational_state, new_detailed_state = classify_ping_result(result)

        # Step 2: Always increment the active event, regardless of transition
        # state.
        await self._increment_active_event(
            event_id=state.active_event_id,
            avg_rtt_ms=result.avg_rtt_ms,
            db=db,
        )

        # Step 3: Determine what to do based on state comparison.

        # CASE A: No change — endpoint remains in the confirmed state.
        if new_detailed_state == state.confirmed_detailed_state:
            return EndpointState(
                endpoint_id=state.endpoint_id,
                active_event_id=state.active_event_id,
                confirmed_operational_state=state.confirmed_operational_state,
                confirmed_detailed_state=state.confirmed_detailed_state,
                pending_detailed_state=None,
                pending_cycle_count=0,
            )

        # CASE B: A potential transition is occurring.

        # Sub-case B1: The pending state is continuing.
        if new_detailed_state == state.pending_detailed_state:
            new_pending_count = state.pending_cycle_count + 1

            # Not yet at the confirmation threshold — keep accumulating.
            if new_pending_count < self.confirmation_threshold:
                return EndpointState(
                    endpoint_id=state.endpoint_id,
                    active_event_id=state.active_event_id,
                    confirmed_operational_state=state.confirmed_operational_state,
                    confirmed_detailed_state=state.confirmed_detailed_state,
                    pending_detailed_state=new_detailed_state,
                    pending_cycle_count=new_pending_count,
                )

            # Step 4: Commit the transition.
            transition_time = datetime.now(timezone.utc)

            # 4b. Close the current active event.
            await self._close_event(
                event_id=state.active_event_id,
                end_time=transition_time,
                db=db,
            )

            # 4c. Open the new event.
            new_event_id = await self._open_event(
                endpoint_id=state.endpoint_id,
                result=result,
                operational_state=new_operational_state,
                detailed_state=new_detailed_state,
                start_time=transition_time,
                db=db,
            )

            logger.info(
                "Committed transition for endpoint %s: %s -> %s (new event %s)",
                state.endpoint_id,
                state.confirmed_detailed_state,
                new_detailed_state,
                new_event_id,
            )

            # 4d. Return the new confirmed state.
            return EndpointState(
                endpoint_id=state.endpoint_id,
                active_event_id=new_event_id,
                confirmed_operational_state=new_operational_state,
                confirmed_detailed_state=new_detailed_state,
                pending_detailed_state=None,
                pending_cycle_count=0,
            )

        # Sub-case B2: No transition was pending, or the pending state has
        # changed to a third state. Reset the pending tracker.
        return EndpointState(
            endpoint_id=state.endpoint_id,
            active_event_id=state.active_event_id,
            confirmed_operational_state=state.confirmed_operational_state,
            confirmed_detailed_state=state.confirmed_detailed_state,
            pending_detailed_state=new_detailed_state,
            pending_cycle_count=1,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _increment_active_event(
        self,
        event_id: UUID,
        avg_rtt_ms: Optional[float],
        db: AsyncSession,
    ) -> None:
        """
        Increments monitoring_cycle_count by 1 on the active event.
        Updates avg_rtt_ms only when the new value is not None; if None,
        the existing database value is preserved via COALESCE.
        """
        await db.execute(
            text(
                """
                UPDATE endpoint_events
                SET
                    monitoring_cycle_count = monitoring_cycle_count + 1,
                    avg_rtt_ms = COALESCE(:avg_rtt_ms, avg_rtt_ms)
                WHERE id = :event_id
                """
            ),
            {"event_id": str(event_id), "avg_rtt_ms": avg_rtt_ms},
        )

    async def _close_event(
        self,
        event_id: UUID,
        end_time: datetime,
        db: AsyncSession,
    ) -> None:
        """
        Closes the active event by setting end_time and calculating
        duration_seconds as the difference between end_time and start_time
        in whole seconds.
        """
        await db.execute(
            text(
                """
                UPDATE endpoint_events
                SET
                    end_time = :end_time,
                    duration_seconds = EXTRACT(
                        EPOCH FROM (:end_time - start_time)
                    )::BIGINT
                WHERE id = :event_id
                """
            ),
            {"event_id": str(event_id), "end_time": end_time},
        )

    async def _open_event(
        self,
        endpoint_id: UUID,
        result: PingResult,
        operational_state: str,
        detailed_state: str,
        start_time: datetime,
        db: AsyncSession,
    ) -> UUID:
        """
        Inserts a new open event row and returns its UUID.

        monitoring_cycle_count starts at 1 because this method is called from
        process_cycle, which already called _increment_active_event on the
        old event for this cycle. The new event's first cycle is the one that
        committed the transition.
        """
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
                },
            )
        ).fetchone()

        return row.id



