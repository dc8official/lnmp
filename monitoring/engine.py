from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.endpoint import Endpoint
from app.services.baseline_service import baseline_cache, start_baseline_refresh_task
from app.services.diagnostics import run_throttled_traceroute, save_diagnostic_trace
from monitoring.gap_handler import resolve_startup_state
from monitoring.ping import run_ping_cycle
from monitoring.registry import endpoint_registry, MonitoredEndpoint
from monitoring.state_machine import EndpointState, StateMachine

from app.logging_config import setup_logging
from app.config import settings

logger = setup_logging(
    service_name="netmon-engine",
    log_dir=getattr(settings.logging, "log_dir", "/var/log/netmon"),
    log_level=getattr(settings.logging, "level", "INFO"),
)

endpoint_states: dict[str, EndpointState] = {}
states_lock = asyncio.Lock()
db_write_semaphore = asyncio.Semaphore(15)

_active_background_tasks: set[asyncio.Task] = set()


def safe_create_task(coro, task_name: str = "background_task") -> asyncio.Task:
    """Safely spawn a background asyncio task with error logging and lifetime tracking."""
    task = asyncio.create_task(coro)
    _active_background_tasks.add(task)

    def _on_complete(t: asyncio.Task) -> None:
        _active_background_tasks.discard(t)
        if not t.cancelled():
            exc = t.exception()
            if exc:
                logger.error(
                    "Background task '%s' failed with exception: %s",
                    task_name,
                    exc,
                    exc_info=exc,
                )

    task.add_done_callback(_on_complete)
    return task


async def trigger_incident_diagnostic_trace(endpoint_id: UUID, ip_address: str) -> None:
    """Fires a background diagnostic traceroute upon detecting a failed ping sub-cycle."""
    try:
        trace_data = await run_throttled_traceroute(ip_address)
        async with AsyncSessionLocal() as db:
            await save_diagnostic_trace(
                db, endpoint_id, "FAILED_PING_SUBCYCLE", trace_data
            )
            await db.commit()
            logger.info(
                "Incident diagnostic trace saved for endpoint %s (%s)",
                endpoint_id,
                ip_address,
            )
    except Exception as e:
        logger.error(
            "Failed to execute incident diagnostic trace for %s: %s",
            ip_address,
            e,
        )


async def monitor_endpoint(
    endpoint_id: UUID,
    ip_address: str,
    state_machine: StateMachine,
) -> None:
    # 0–2000ms randomized startup jitter to distribute probe start times
    startup_jitter = random.uniform(0.0, 2.0)
    await asyncio.sleep(startup_jitter)

    async with AsyncSessionLocal() as db:
        state = await state_machine.initialize_endpoint(endpoint_id, db)
        await db.commit()

    async with states_lock:
        endpoint_states[str(endpoint_id)] = state

    # Fractional First-Minute Handling:
    # When a brand-new endpoint is registered and detected mid-minute (state is None),
    # immediately fire a single baseline validation ping, write it to database,
    # and sleep until the next top-of-the-minute boundary.
    if state is None:
        now_utc = datetime.now().astimezone()
        if now_utc.second != 0 or now_utc.microsecond != 0:
            logger.info(
                "Endpoint %s is brand-new and detected mid-minute at %s. Firing baseline validation ping.",
                str(endpoint_id),
                now_utc,
            )
            try:
                result = await run_ping_cycle(
                    ip_address=ip_address,
                    count=1,
                    interval=8.0,
                    timeout=2.0,
                    privileged=True,
                )

                baseline = baseline_cache.get_baseline(endpoint_id)
                async with AsyncSessionLocal() as db:
                    new_state = await state_machine.create_initial_event(
                        endpoint_id, result, db, baseline=baseline
                    )
                    await db.commit()

                async with states_lock:
                    endpoint_states[str(endpoint_id)] = new_state
                    state = new_state

            except Exception as e:
                logger.error(
                    "Error in baseline validation ping for %s: %s: %s",
                    ip_address,
                    type(e).__name__,
                    e,
                )

            # Sleep until the next top-of-the-minute boundary
            now_utc = datetime.now().astimezone()
            remaining_seconds = (
                60.0 - now_utc.second - (now_utc.microsecond / 1_000_000.0)
            )
            logger.info(
                "Sleeping for %.4f seconds until the next top-of-the-minute boundary.",
                remaining_seconds,
            )
            await asyncio.sleep(remaining_seconds)

    while True:
        try:
            # 5 pings @ 8.0s = ~32.0s duration, guaranteeing ~28.0s headroom window before next boundary
            result = await run_ping_cycle(
                ip_address=ip_address,
                count=5,
                interval=8.0,
                timeout=2.0,
                privileged=True,
            )

            baseline = baseline_cache.get_baseline(endpoint_id)

            async with db_write_semaphore:
                async with AsyncSessionLocal() as db:
                    current_state = endpoint_states.get(str(endpoint_id))

                    if current_state is None:
                        new_state = await state_machine.create_initial_event(
                            endpoint_id, result, db, baseline=baseline
                        )
                    else:
                        new_state = await state_machine.process_cycle(
                            current_state, result, db, baseline=baseline
                        )

                    # Check operational toggles directly from in-memory EndpointRegistry
                    # to eliminate in-cycle database lock contention during packet drops
                    if result.failed_count > 0:
                        toggles = endpoint_registry.get_toggles(endpoint_id)
                        if toggles.get("allow_incident_trace", True):
                            task = safe_create_task(
                                trigger_incident_diagnostic_trace(
                                    endpoint_id, ip_address
                                ),
                                "incident_diagnostic_trace",
                            )
                            endpoint_registry.register_diagnostic_task(
                                endpoint_id, task
                            )

                    await db.commit()

            async with states_lock:
                endpoint_states[str(endpoint_id)] = new_state

        except asyncio.CancelledError:
            logger.info("Monitoring task for endpoint %s cancelled.", endpoint_id)
            break
        except Exception as e:
            logger.error(
                "Error in monitoring cycle for %s: %s: %s",
                ip_address,
                type(e).__name__,
                e,
            )

        # Absolute Minute Loop Alignment:
        # Dynamically compute the exact remaining seconds required to hit the top of the next absolute minute.
        now_utc = datetime.now().astimezone()
        remaining_seconds = (
            60.0 - now_utc.second - (now_utc.microsecond / 1_000_000.0)
        )
        if remaining_seconds <= 0:
            remaining_seconds += 60.0

        await asyncio.sleep(remaining_seconds)


async def main() -> None:
    logger.info("lnmp monitoring engine starting.")
    async with AsyncSessionLocal() as db:
        await resolve_startup_state(db)
        await baseline_cache.refresh_from_db(db)
        await db.commit()

    await start_baseline_refresh_task(AsyncSessionLocal, interval_seconds=3600)

    state_machine = StateMachine(confirmation_threshold=3)

    while True:
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(Endpoint).where(
                    Endpoint.endpoint_status == "ACTIVE",
                    Endpoint.monitoring_enabled == True,  # noqa: E712
                )
                result = await db.execute(stmt)
                active_endpoints = result.scalars().all()

            db_active_map = {ep.id: ep for ep in active_endpoints}

            # Sync in-memory endpoint registry
            for ep in active_endpoints:
                def _spawn(target: MonitoredEndpoint):
                    return monitor_endpoint(
                        target.id,
                        target.ip_address,
                        state_machine,
                    )

                await endpoint_registry.add_endpoint(ep, spawn_coro_fn=_spawn)

            # Evict removed or deactivated endpoints
            current_registered = endpoint_registry.list_active_endpoints()
            for reg_ep in current_registered:
                if reg_ep.id not in db_active_map:
                    logger.info(
                        "Deactivating monitoring for removed endpoint %s",
                        reg_ep.id,
                    )
                    await endpoint_registry.remove_endpoint(reg_ep.id)
                    async with states_lock:
                        endpoint_states.pop(str(reg_ep.id), None)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(
                "Error in master orchestration loop: %s: %s",
                type(e).__name__,
                e,
            )

        await asyncio.sleep(30)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitoring engine stopped.")
