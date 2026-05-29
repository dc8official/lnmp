from __future__ import annotations
import asyncio
import logging
from uuid import UUID
from sqlalchemy import text
from app.database import AsyncSessionLocal
from monitoring.gap_handler import resolve_startup_state
from monitoring.ping import run_ping_cycle
from monitoring.scheduler import run_daily_split_scheduler
from monitoring.state_machine import EndpointState, StateMachine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("netmon-engine")

endpoint_states: dict[str, EndpointState] = {}
states_lock = asyncio.Lock()


async def monitor_endpoint(
    endpoint_id: UUID,
    ip_address: str,
    state_machine: StateMachine,
) -> None:
    async with AsyncSessionLocal() as db:
        state = await state_machine.initialize_endpoint(endpoint_id, db)
        await db.commit()

    async with states_lock:
        endpoint_states[str(endpoint_id)] = state

    while True:
        cycle_start = asyncio.get_event_loop().time()
        
        try:
            result = await run_ping_cycle(
                ip_address=ip_address,
                count=10,
                interval=6.0,
                timeout=2.0,
                privileged=True,
            )

            async with AsyncSessionLocal() as db:
                current_state = endpoint_states.get(str(endpoint_id))

                if current_state is None:
                    new_state = await state_machine.create_initial_event(
                        endpoint_id, result, db
                    )
                else:
                    new_state = await state_machine.process_cycle(
                        current_state, result, db
                    )

                await db.commit()

            async with states_lock:
                endpoint_states[str(endpoint_id)] = new_state

        except Exception as e:
            logger.error(
                "Error in monitoring cycle for %s: %s: %s",
                ip_address,
                type(e).__name__,
                e,
            )

        elapsed = asyncio.get_event_loop().time() - cycle_start
        sleep_time = max(0.0, 60.0 - elapsed)
        await asyncio.sleep(sleep_time)


async def on_split_complete(
    mapping: dict[UUID, UUID],
) -> None:
    async with states_lock:
        for endpoint_id, new_event_id in mapping.items():
            key = str(endpoint_id)
            old_state = endpoint_states.get(key)
            if old_state is not None:
                endpoint_states[key] = EndpointState(
                    endpoint_id=old_state.endpoint_id,
                    active_event_id=new_event_id,
                    confirmed_operational_state=old_state.confirmed_operational_state,
                    confirmed_detailed_state=old_state.confirmed_detailed_state,
                    pending_detailed_state=None,
                    pending_cycle_count=0,
                )

    logger.info(
        "Daily split: updated %d in-memory endpoint states.",
        len(mapping),
    )


async def main() -> None:
    logger.info("noop monitoring engine starting.")
    async with AsyncSessionLocal() as db:
        await resolve_startup_state(db)
        await db.commit()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT id, ip_address FROM endpoints "
                "WHERE endpoint_status = 'ACTIVE' "
                "AND monitoring_enabled = TRUE"
            )
        )
        active_endpoints = result.fetchall()

    if not active_endpoints:
        logger.warning(
            "No active endpoints found. Engine running with no monitoring tasks."
        )

    state_machine = StateMachine(confirmation_threshold=3)

    tasks = []

    tasks.append(
        asyncio.create_task(
            run_daily_split_scheduler(on_split_complete)
        )
    )

    for row in active_endpoints:
        endpoint_id = UUID(str(row.id))
        ip_address = str(row.ip_address)
        tasks.append(
            asyncio.create_task(
                monitor_endpoint(
                    endpoint_id,
                    ip_address,
                    state_machine,
                )
            )
        )

    logger.info(
        "Engine running: %d endpoint tasks, 1 scheduler task.",
        len(active_endpoints),
    )

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Monitoring engine stopped.")
