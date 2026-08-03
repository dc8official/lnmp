from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Semaphore to throttle concurrent traceroute commands (max 5 concurrent)
trace_semaphore = asyncio.Semaphore(5)

# Async Queue for sequential topology discovery
discovery_queue: asyncio.Queue[tuple[UUID, str]] = asyncio.Queue()


def sanitize_traceroute_hops(hops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitizes traceroute hop list:
    1. Strips trailing 'no reply' (ip is None) hops.
    2. Collapses consecutive 'no reply' (ip is None) hops into a single anonymous hop.
    """
    if not hops:
        return []

    # Strip trailing no-reply hops
    clean_hops = list(hops)
    while clean_hops and clean_hops[-1].get("ip") is None:
        clean_hops.pop()

    collapsed_hops: List[Dict[str, Any]] = []
    prev_was_null = False

    for h in clean_hops:
        is_null = h.get("ip") is None
        if is_null:
            if not prev_was_null:
                collapsed_hops.append(h)
                prev_was_null = True
        else:
            collapsed_hops.append(h)
            prev_was_null = False

    return collapsed_hops


async def run_traceroute(target_ip: str) -> Dict[str, Any]:
    """
    Executes asynchronous route discovery using standard non-privileged `tracepath` utility.
    Parses stdout into a structured list of hops:
        [{"hop": 1, "ip": "192.168.1.1", "rtt_ms": 1.25}, ...]

    Unresponsive / timed out hops are handled gracefully as:
        {"hop": N, "ip": None, "rtt_ms": None}
    """
    hops: List[Dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        # Standard non-privileged tracepath execution
        proc = await asyncio.create_subprocess_exec(
            "tracepath",
            "-n",
            "-m",
            "30",
            "--",
            target_ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        stdout_str = stdout.decode("utf-8", errors="ignore")

        seen_hops = set()
        for line in stdout_str.splitlines():
            line = line.strip()
            if not line or line.startswith("traceroute"):
                continue

            # Match hop number for tracepath ('1:') or traceroute ('1 ')
            hop_match = re.match(r"^\s*(\d+)[:\s]\s*(.*)$", line)
            if not hop_match:
                continue

            hop_num = int(hop_match.group(1))
            if hop_num in seen_hops:
                continue
            seen_hops.add(hop_num)

            remainder = hop_match.group(2).strip()

            if "no reply" in remainder.lower() or remainder.startswith("*") or remainder == "* * *":
                hops.append({"hop": hop_num, "ip": None, "rtt_ms": None})
                continue

            ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", remainder)
            rtt_match = re.search(r"([\d\.]+)\s*ms", remainder)

            hop_ip = ip_match.group(1) if ip_match else None
            rtt_ms = float(rtt_match.group(1)) if rtt_match else None

            hops.append({
                "hop": hop_num,
                "ip": hop_ip,
                "rtt_ms": rtt_ms,
            })

    except Exception as e:
        logger.warning(
            "Standard tracepath execution failed for target %s: %s: %s. Using fallback trace.",
            target_ip,
            type(e).__name__,
            e,
        )
        # Fallback trace entry
        hops.append({"hop": 1, "ip": target_ip, "rtt_ms": None})

    sanitized_hops = sanitize_traceroute_hops(hops)

    return {
        "target_ip": target_ip,
        "hops": sanitized_hops,
        "timestamp": timestamp,
    }


async def run_throttled_traceroute(target_ip: str) -> Dict[str, Any]:
    """
    Executes run_traceroute under the concurrency semaphore (max 5 concurrent).
    """
    async with trace_semaphore:
        return await run_traceroute(target_ip)


async def save_diagnostic_trace(
    db: AsyncSession,
    endpoint_id: UUID,
    trigger_reason: str,
    trace_data: Dict[str, Any],
) -> Optional[UUID]:
    """
    Persists a diagnostic trace record into endpoint_diagnostic_traces table.
    """
    try:
        query = text("""
            INSERT INTO endpoint_diagnostic_traces (
                endpoint_id,
                trigger_reason,
                trace_data
            ) VALUES (
                :endpoint_id,
                :trigger_reason,
                :trace_data
            ) RETURNING id
        """)
        result = await db.execute(
            query,
            {
                "endpoint_id": str(endpoint_id),
                "trigger_reason": trigger_reason,
                "trace_data": json.dumps(trace_data),
            },
        )
        row = result.fetchone()
        return UUID(str(row.id)) if row else None
    except Exception as e:
        logger.error(
            "Failed to save diagnostic trace for endpoint %s: %s: %s",
            endpoint_id,
            type(e).__name__,
            e,
        )
        return None


async def cleanup_old_diagnostic_traces(
    db: AsyncSession,
    retention_days: int = 14,
) -> int:
    """
    Purges diagnostic trace records older than specified retention_days (default 14 days).
    """
    try:
        query = text("""
            DELETE FROM endpoint_diagnostic_traces
            WHERE timestamp < NOW() - (INTERVAL '1 day' * :retention_days)
        """)
        result = await db.execute(query, {"retention_days": retention_days})
        deleted_count = result.rowcount
        logger.info(
            "Purged %d diagnostic traces older than %d days.",
            deleted_count,
            retention_days,
        )
        return deleted_count
    except Exception as e:
        logger.error("Failed to purge old diagnostic traces: %s", e)
        return 0


async def start_discovery_worker(db_session_factory) -> asyncio.Task:
    """
    Starts the sequential topology discovery worker task reading from discovery_queue.
    Enforces a 500ms delay between runs.
    """

    async def _worker_loop():
        logger.info("Sequential Topology Discovery worker started.")
        while True:
            try:
                endpoint_id, ip_address = await discovery_queue.get()
                logger.info(
                    "Processing topology discovery for endpoint %s (%s)",
                    endpoint_id,
                    ip_address,
                )
                trace_data = await run_throttled_traceroute(ip_address)
                async with db_session_factory() as db:
                    await save_diagnostic_trace(
                        db,
                        endpoint_id,
                        "TOPOLOGY_DISCOVERY",
                        trace_data,
                    )
                    await db.commit()
                discovery_queue.task_done()
                # 500ms delay between discovery runs
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in topology discovery worker: %s", e)
                await asyncio.sleep(0.5)

    return asyncio.create_task(_worker_loop())


async def start_diagnostic_cleanup_task(
    db_session_factory,
    interval_seconds: int = 86400,
) -> asyncio.Task:
    """
    Spawns a daily background task to purge diagnostic records older than 14 days.
    """

    async def _cleanup_loop():
        while True:
            try:
                async with db_session_factory() as db:
                    await cleanup_old_diagnostic_traces(db, retention_days=14)
                    await db.commit()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in diagnostic cleanup loop: %s", e)
            await asyncio.sleep(interval_seconds)

    return asyncio.create_task(_cleanup_loop())
