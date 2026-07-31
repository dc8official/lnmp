from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.baseline_route import refresh_baseline_route
from app.services.diagnostics import run_throttled_traceroute

logger = logging.getLogger(__name__)


async def run_differential_rca(
    endpoint_id: UUID,
    db: Optional[AsyncSession] = None,
) -> Optional[Dict[str, Any]]:
    """
    Executes comparative differential Root Cause Analysis (RCA) for a DOWN endpoint.
    Compares live failure traceroute against the last-known-online baseline route.
    """

    async def _execute_rca(session: AsyncSession) -> Optional[Dict[str, Any]]:
        # 1. Fetch endpoint info
        ep_query = text("""
            SELECT id, host(ip_address) AS ip_address, enable_rca, is_l2_segment
            FROM endpoints
            WHERE id = :endpoint_id AND endpoint_status != 'DELETED'
        """)
        ep_res = await session.execute(ep_query, {"endpoint_id": str(endpoint_id)})
        ep_row = ep_res.fetchone()

        if not ep_row:
            logger.warning("Endpoint %s not found for RCA.", endpoint_id)
            return None

        target_ip = str(ep_row.ip_address)
        enable_rca = bool(ep_row.enable_rca)
        is_l2_segment = bool(ep_row.is_l2_segment)

        if not enable_rca:
            logger.info("RCA disabled for endpoint %s. Skipping.", endpoint_id)
            return None

        # 2. Fetch baseline route snapshot
        bl_query = text("""
            SELECT total_hops, hops
            FROM endpoint_baseline_routes
            WHERE endpoint_id = :endpoint_id
        """)
        bl_res = await session.execute(bl_query, {"endpoint_id": str(endpoint_id)})
        bl_row = bl_res.fetchone()

        baseline_hops: List[Dict[str, Any]] = []
        if bl_row and bl_row.hops:
            b_hops = bl_row.hops
            if isinstance(b_hops, str):
                try:
                    b_hops = json.loads(b_hops)
                except Exception:
                    b_hops = []
            if isinstance(b_hops, list):
                baseline_hops = b_hops

        # 3. Execute live failure traceroute
        failure_trace = await run_throttled_traceroute(target_ip)
        live_hops: List[Dict[str, Any]] = failure_trace.get("hops", [])

        valid_live_hops = [h for h in live_hops if h.get("ip")]
        live_hop_count = len(valid_live_hops)

        failed_hop_number: Optional[int] = None
        failed_hop_ip: Optional[str] = None
        last_known_good_hop_ip: Optional[str] = None
        rca_summary: str = ""

        # 4. Evaluation Logic (Layer 2 vs Layer 3)
        if is_l2_segment or (len(live_hops) <= 1 and len(baseline_hops) <= 1):
            failed_hop_number = 1
            failed_hop_ip = target_ip
            last_known_good_hop_ip = None
            rca_summary = (
                "Direct Layer 2 Attachment (Same Subnet). "
                "No intermediate L3 routers detected. "
                "Failure isolated to local host, NIC, or local L2 switch port."
            )
        else:
            # Layer 3 Multi-Hop: Compare live failure hops against baseline
            diverged = False
            for idx, b_hop in enumerate(baseline_hops):
                hop_num = b_hop.get("hop", idx + 1)
                b_ip = b_hop.get("ip")

                # Corresponding live hop
                l_hop = live_hops[idx] if idx < len(live_hops) else None
                l_ip = l_hop.get("ip") if l_hop else None

                # Divergence / Timeout check
                if l_hop is None or l_ip is None or l_ip != b_ip:
                    failed_hop_number = hop_num
                    failed_hop_ip = b_ip
                    if idx > 0 and baseline_hops[idx - 1].get("ip"):
                        last_known_good_hop_ip = baseline_hops[idx - 1].get("ip")
                        rca_summary = (
                            f"Transit failure at Hop {hop_num} ({failed_hop_ip}). "
                            f"Path confirmed operational through Hop {hop_num - 1} ({last_known_good_hop_ip})."
                        )
                    else:
                        last_known_good_hop_ip = None
                        rca_summary = (
                            f"Transit failure at Hop {hop_num} ({failed_hop_ip}). "
                            f"No prior operational hop."
                        )
                    diverged = True
                    break

            if not diverged and baseline_hops:
                # Target endpoint itself is the failure point
                last_b_hop = baseline_hops[-1]
                failed_hop_number = last_b_hop.get("hop", len(baseline_hops))
                failed_hop_ip = last_b_hop.get("ip", target_ip)
                if len(baseline_hops) > 1 and baseline_hops[-2].get("ip"):
                    last_known_good_hop_ip = baseline_hops[-2].get("ip")
                    rca_summary = (
                        f"Transit failure at Hop {failed_hop_number} ({failed_hop_ip}). "
                        f"Path confirmed operational through Hop {failed_hop_number - 1} ({last_known_good_hop_ip})."
                    )
                else:
                    last_known_good_hop_ip = None
                    rca_summary = f"Transit failure at Hop {failed_hop_number} ({failed_hop_ip})."

        # 5. Persist RCA Incident Record
        insert_incident_sql = text("""
            INSERT INTO endpoint_rca_incidents (
                endpoint_id,
                incident_timestamp,
                status_at_execution,
                failed_hop_number,
                failed_hop_ip,
                last_known_good_hop_ip,
                rca_summary,
                baseline_snapshot,
                failure_trace_snapshot,
                is_resolved
            ) VALUES (
                :endpoint_id,
                NOW(),
                'DOWN',
                :failed_hop_number,
                :failed_hop_ip,
                :last_known_good_hop_ip,
                :rca_summary,
                :baseline_snapshot,
                :failure_trace_snapshot,
                FALSE
            ) RETURNING id
        """)

        res = await session.execute(
            insert_incident_sql,
            {
                "endpoint_id": str(endpoint_id),
                "failed_hop_number": failed_hop_number,
                "failed_hop_ip": failed_hop_ip,
                "last_known_good_hop_ip": last_known_good_hop_ip,
                "rca_summary": rca_summary,
                "baseline_snapshot": json.dumps(baseline_hops),
                "failure_trace_snapshot": json.dumps(live_hops),
            },
        )
        row = res.fetchone()
        incident_id = str(row.id) if row else None

        logger.info(
            "Recorded RCA incident %s for endpoint %s: %s",
            incident_id,
            endpoint_id,
            rca_summary,
        )

        return {
            "incident_id": incident_id,
            "endpoint_id": str(endpoint_id),
            "failed_hop_number": failed_hop_number,
            "failed_hop_ip": failed_hop_ip,
            "last_known_good_hop_ip": last_known_good_hop_ip,
            "rca_summary": rca_summary,
            "baseline_snapshot": baseline_hops,
            "failure_trace_snapshot": live_hops,
        }

    if db is not None:
        return await _execute_rca(db)
    else:
        async with AsyncSessionLocal() as session:
            result = await _execute_rca(session)
            await session.commit()
            return result


async def handle_endpoint_recovery(
    endpoint_id: UUID,
    target_ip: str,
    db: Optional[AsyncSession] = None,
) -> None:
    """
    Recovery Hook: When an endpoint transitions back from 'DOWN' to 'UP',
    automatically sets active incidents to `is_resolved = True` and refreshes baseline route.
    """

    async def _execute_recovery(session: AsyncSession):
        resolve_sql = text("""
            UPDATE endpoint_rca_incidents
            SET is_resolved = TRUE
            WHERE endpoint_id = :endpoint_id
              AND is_resolved = FALSE
        """)
        res = await session.execute(resolve_sql, {"endpoint_id": str(endpoint_id)})
        resolved_count = res.rowcount
        logger.info(
            "Endpoint %s recovered to UP. Resolved %d active RCA incidents.",
            endpoint_id,
            resolved_count,
        )
        await refresh_baseline_route(endpoint_id, target_ip, db=session)

    if db is not None:
        await _execute_recovery(db)
    else:
        async with AsyncSessionLocal() as session:
            await _execute_recovery(session)
            await session.commit()
