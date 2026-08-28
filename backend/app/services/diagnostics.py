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


def sanitize_traceroute_hops(
    hops: List[Dict[str, Any]],
    target_ip: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Sanitizes traceroute hop list:
    1. Strips trailing 'no reply' (ip is None) hops when no target_ip is provided.
    2. Collapses consecutive 'no reply' (ip is None) hops into a single anonymous hop.
    3. Ensures the destination target_ip is preserved as the terminal hop if provided.
    """
    if not hops:
        if target_ip:
            return [{"hop": 1, "ip": target_ip, "rtt_ms": None}]
        return []

    # If target_ip is not provided, strip trailing no-reply hops
    clean_hops = list(hops)
    if not target_ip:
        while clean_hops and clean_hops[-1].get("ip") is None:
            clean_hops.pop()

    collapsed_hops: List[Dict[str, Any]] = []
    prev_was_null = False

    for h in clean_hops:
        is_null = h.get("ip") is None
        if is_null:
            if not prev_was_null:
                collapsed_hops.append({"hop": h.get("hop"), "ip": None, "rtt_ms": None})
                prev_was_null = True
        else:
            collapsed_hops.append(h)
            prev_was_null = False

    # If target_ip is provided, ensure it is the terminal hop in the route
    if target_ip:
        last_hop = collapsed_hops[-1] if collapsed_hops else None
        if not last_hop or last_hop.get("ip") != target_ip:
            next_hop_num = ((last_hop.get("hop") or len(collapsed_hops)) + 1) if last_hop else 1
            collapsed_hops.append({
                "hop": next_hop_num,
                "ip": target_ip,
                "rtt_ms": None,
            })

    return collapsed_hops


def _parse_trace_output(stdout_str: str) -> List[Dict[str, Any]]:
    """
    Parses stdout from either traceroute or tracepath into structured hops.
    """
    hops: List[Dict[str, Any]] = []
    seen_hops = set()

    for line in stdout_str.splitlines():
        line = line.strip()
        if not line or line.startswith("traceroute"):
            continue

        # Match hop number for tracepath ('1:') or traceroute ('1 ')
        hop_match = re.match(r"^\s*(\d+)[:\s]\s*(.*)$", line)
        if not hop_match:
            continue

        try:
            hop_num = int(hop_match.group(1))
        except ValueError:
            continue

        if hop_num in seen_hops:
            continue
        seen_hops.add(hop_num)

        remainder = hop_match.group(2).strip()

        if "no reply" in remainder.lower() or remainder.startswith("*") or remainder == "* * *":
            hops.append({"hop": hop_num, "ip": None, "rtt_ms": None})
            continue

        ip_match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", remainder)
        rtt_match = re.search(r"([\d\.]+)\s*ms", remainder)

        hop_ip = ip_match.group(1) if ip_match else None
        rtt_ms = float(rtt_match.group(1)) if rtt_match else None

        hops.append({
            "hop": hop_num,
            "ip": hop_ip,
            "rtt_ms": rtt_ms,
        })

    return hops


async def run_traceroute(target_ip: str) -> Dict[str, Any]:
    """
    Executes asynchronous route discovery:
    1. Attempts ICMP Echo mode `traceroute -I` (best for WAN/carrier discovery).
    2. Falls back to fast unprivileged UDP `traceroute`.
    3. Falls back to `tracepath` if traceroute is not installed.
    """
    hops: List[Dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()
    stdout_str = ""

    # 1. Try ICMP traceroute (-I) with 1 probe per hop, 1s timeout
    try:
        proc = await asyncio.create_subprocess_exec(
            "traceroute",
            "-n",
            "-q",
            "1",
            "-w",
            "1",
            "-m",
            "30",
            "-I",
            "--",
            target_ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
        if proc.returncode == 0:
            stdout_str = stdout.decode("utf-8", errors="ignore")
    except Exception:
        stdout_str = ""

    # 2. Try standard fast unprivileged traceroute if ICMP mode returned empty/failed
    if not stdout_str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "traceroute",
                "-n",
                "-q",
                "1",
                "-w",
                "1",
                "-m",
                "30",
                "--",
                target_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            if proc.returncode == 0:
                stdout_str = stdout.decode("utf-8", errors="ignore")
        except Exception:
            stdout_str = ""

    # 3. Fallback to tracepath if traceroute is unavailable
    if not stdout_str:
        try:
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
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20.0)
            stdout_str = stdout.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(
                "Route discovery execution failed for target %s: %s: %s",
                target_ip,
                type(e).__name__,
                e,
            )
            stdout_str = ""

    if stdout_str:
        hops = _parse_trace_output(stdout_str)

    sanitized_hops = sanitize_traceroute_hops(hops, target_ip=target_ip)

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
                CAST(:endpoint_id AS uuid),
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
    audit_retention_days: int = 90,
) -> int:
    """
    Purges diagnostic trace records older than specified retention_days (default 14 days),
    audit logs older than audit_retention_days (default 90 days), and resolved RCA incidents (default 90 days).
    """
    total_purged = 0
    try:
        # 1. Purge diagnostic traces
        query_traces = text("""
            DELETE FROM endpoint_diagnostic_traces
            WHERE timestamp < NOW() - (INTERVAL '1 day' * :retention_days)
        """)
        res_traces = await db.execute(query_traces, {"retention_days": retention_days})
        traces_count = res_traces.rowcount or 0
        total_purged += traces_count
        if traces_count > 0:
            logger.info("Purged %d diagnostic traces older than %d days.", traces_count, retention_days)

        # 2. Purge old audit logs
        query_audit = text("""
            DELETE FROM audit_logs
            WHERE timestamp < NOW() - (INTERVAL '1 day' * :audit_days)
        """)
        res_audit = await db.execute(query_audit, {"audit_days": audit_retention_days})
        audit_count = res_audit.rowcount or 0
        total_purged += audit_count
        if audit_count > 0:
            logger.info("Purged %d audit logs older than %d days.", audit_count, audit_retention_days)

        # 3. Purge old resolved RCA incidents
        query_rca = text("""
            DELETE FROM endpoint_rca_incidents
            WHERE is_resolved = TRUE AND incident_timestamp < NOW() - (INTERVAL '1 day' * :rca_days)
        """)
        res_rca = await db.execute(query_rca, {"rca_days": audit_retention_days})
        rca_count = res_rca.rowcount or 0
        total_purged += rca_count
        if rca_count > 0:
            logger.info("Purged %d resolved RCA incidents older than %d days.", rca_count, audit_retention_days)

        return total_purged
    except Exception as e:
        logger.error("Failed to execute database retention cleanup: %s", e)
        return total_purged


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
