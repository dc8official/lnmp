from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.diagnostics import run_throttled_traceroute

logger = logging.getLogger(__name__)

# Async Queue for sequential midnight baseline discovery
discovery_route_queue: asyncio.Queue[tuple[UUID, str]] = asyncio.Queue()


def is_local_subnet(target_ip_str: str) -> bool:
    """
    Determines if target IP resides in the local subnet/VLAN of the monitoring server.
    """
    try:
        target = ipaddress.ip_address(target_ip_str)
        if target.is_loopback:
            return True
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address and addr.netmask:
                    try:
                        net = ipaddress.ip_network(
                            f"{addr.address}/{addr.netmask}", strict=False
                        )
                        if target in net:
                            return True
                    except Exception:
                        pass
    except Exception:
        pass
    return False


async def refresh_baseline_route(
    endpoint_id: UUID,
    target_ip: str,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Executes asynchronous traceroute, parses hops, detects Layer 2 segment status,
    and upserts the single latest online route record in `endpoint_baseline_routes`.
    """
    trace_res = await run_throttled_traceroute(target_ip)
    raw_hops: List[Dict[str, Any]] = trace_res.get("hops", [])

    # Format hops into structured JSON array
    formatted_hops: List[Dict[str, Any]] = []
    for h in raw_hops:
        formatted_hops.append({
            "hop": h.get("hop"),
            "ip": h.get("ip"),
            "rtt_ms": h.get("rtt_ms"),
        })

    total_hops = len(formatted_hops)

    # Layer 2 Detection: total hops == 1 OR target IP in local subnet/VLAN
    is_l2 = (total_hops == 1) or is_local_subnet(target_ip)

    upsert_route_sql = text("""
        INSERT INTO endpoint_baseline_routes (
            endpoint_id, updated_at, total_hops, hops
        ) VALUES (
            :endpoint_id, NOW(), :total_hops, :hops
        )
        ON CONFLICT (endpoint_id) DO UPDATE SET
            updated_at = NOW(),
            total_hops = EXCLUDED.total_hops,
            hops = EXCLUDED.hops
    """)

    update_l2_sql = text("""
        UPDATE endpoints
        SET is_l2_segment = :is_l2_segment,
            updated_at = NOW()
        WHERE id = :endpoint_id
    """)

    async def _execute_queries(session: AsyncSession):
        await session.execute(
            upsert_route_sql,
            {
                "endpoint_id": str(endpoint_id),
                "total_hops": total_hops,
                "hops": json.dumps(formatted_hops),
            },
        )
        await session.execute(
            update_l2_sql,
            {
                "endpoint_id": str(endpoint_id),
                "is_l2_segment": is_l2,
            },
        )

    if db is not None:
        await _execute_queries(db)
    else:
        async with AsyncSessionLocal() as session:
            await _execute_queries(session)
            await session.commit()

    logger.info(
        "Refreshed baseline route for endpoint %s (%s): total_hops=%d, is_l2_segment=%s",
        endpoint_id,
        target_ip,
        total_hops,
        is_l2,
    )

    return {
        "endpoint_id": str(endpoint_id),
        "target_ip": target_ip,
        "total_hops": total_hops,
        "is_l2_segment": is_l2,
        "hops": formatted_hops,
    }


async def enqueue_scheduled_discovery(db: AsyncSession) -> int:
    """
    Enqueues active 'UP' endpoints with `enable_scheduled_discovery == True` for baseline discovery.
    """
    query = text("""
        SELECT e.id, host(e.ip_address) AS ip_address
        FROM endpoints e
        LEFT JOIN LATERAL (
            SELECT operational_state
            FROM endpoint_events
            WHERE endpoint_id = e.id
            ORDER BY start_time DESC
            LIMIT 1
        ) ev ON TRUE
        WHERE e.endpoint_status != 'DELETED'
          AND e.enable_scheduled_discovery = TRUE
          AND COALESCE(ev.operational_state, 'UP') = 'UP'
    """)
    result = await db.execute(query)
    rows = result.fetchall()
    count = 0
    for r in rows:
        await discovery_route_queue.put((UUID(str(r.id)), str(r.ip_address)))
        count += 1
    logger.info("Enqueued %d endpoints for scheduled baseline discovery.", count)
    return count


async def start_midnight_discovery_worker(db_session_factory) -> asyncio.Task:
    """
    Sequential Midnight Discovery Worker task:
    1. Reads queued targets from `discovery_route_queue` and processes them sequentially with 500ms delay.
    2. Runs scheduled midnight job daily.
    """

    async def _queue_consumer():
        while True:
            try:
                endpoint_id, ip_address = await discovery_route_queue.get()
                logger.info(
                    "Processing baseline route discovery for endpoint %s (%s)",
                    endpoint_id,
                    ip_address,
                )
                try:
                    async with db_session_factory() as db:
                        await refresh_baseline_route(endpoint_id, ip_address, db=db)
                        await db.commit()
                except Exception as e:
                    logger.error(
                        "Error refreshing baseline route for %s: %s",
                        ip_address,
                        e,
                    )
                finally:
                    discovery_route_queue.task_done()

                # Mandatory 500ms delay between targets
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in baseline route discovery queue consumer: %s", e)
                await asyncio.sleep(0.5)

    async def _midnight_scheduler():
        while True:
            try:
                now = datetime.now()
                # Compute seconds until next 00:00 (midnight)
                seconds_until_midnight = (
                    24 * 3600 - (now.hour * 3600 + now.minute * 60 + now.second)
                )
                if seconds_until_midnight <= 0:
                    seconds_until_midnight = 86400
                await asyncio.sleep(seconds_until_midnight)

                logger.info("Midnight reached. Triggering scheduled baseline discovery.")
                async with db_session_factory() as db:
                    await enqueue_scheduled_discovery(db)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in midnight scheduler loop: %s", e)
                await asyncio.sleep(3600)

    consumer_task = asyncio.create_task(_queue_consumer())
    scheduler_task = asyncio.create_task(_midnight_scheduler())

    # Combined supervisor task
    async def _supervisor():
        try:
            await asyncio.gather(consumer_task, scheduler_task)
        except asyncio.CancelledError:
            consumer_task.cancel()
            scheduler_task.cancel()

    return asyncio.create_task(_supervisor())
