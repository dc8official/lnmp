from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Set, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_topology_graph(db: AsyncSession) -> Dict[str, Any]:
    """
    Constructs the network topology tree by parsing traceroutes and manual_parent_id overrides.
    Categorizes nodes as 'monitored' or 'transit'.
    Applies Root Cause Analysis (RCA): infers transit node state as 'INFERRED_DOWN' if
    100% of downstream monitored children behind that transit node are DOWN.
    """
    # 1. Fetch monitored endpoints with their latest operational state
    endpoints_query = text("""
        SELECT
            e.id,
            e.hostname,
            host(e.ip_address) AS ip_address,
            e.device_type,
            e.location,
            e.endpoint_status,
            e.allow_topology_discovery,
            e.manual_parent_id,
            COALESCE(ev.operational_state, 'UP') AS operational_state,
            COALESCE(ev.detailed_state, 'UP') AS detailed_state
        FROM endpoints e
        LEFT JOIN LATERAL (
            SELECT operational_state, detailed_state
            FROM endpoint_events
            WHERE endpoint_id = e.id
            ORDER BY start_time DESC
            LIMIT 1
        ) ev ON TRUE
        WHERE e.endpoint_status != 'DELETED'
    """)

    ep_result = await db.execute(endpoints_query)
    ep_rows = ep_result.fetchall()

    monitored_by_id: Dict[str, Dict[str, Any]] = {}
    monitored_by_ip: Dict[str, str] = {}  # ip -> endpoint_id_str

    for row in ep_rows:
        ep_id = str(row.id)
        ip = str(row.ip_address)
        monitored_by_id[ep_id] = {
            "id": ep_id,
            "label": row.hostname or ip,
            "ip_address": ip,
            "node_type": "monitored",
            "status": row.detailed_state or row.operational_state or "UP",
            "device_type": row.device_type or "ENDPOINT",
            "endpoint_id": ep_id,
            "manual_parent_id": str(row.manual_parent_id) if row.manual_parent_id else None,
        }
        monitored_by_ip[ip] = ep_id

    # 2. Fetch latest diagnostic trace per endpoint
    traces_query = text("""
        SELECT DISTINCT ON (endpoint_id)
            endpoint_id,
            trace_data
        FROM endpoint_diagnostic_traces
        ORDER BY endpoint_id, timestamp DESC
    """)
    tr_result = await db.execute(traces_query)
    tr_rows = tr_result.fetchall()

    traces_by_ep: Dict[str, List[Dict[str, Any]]] = {}
    for row in tr_rows:
        ep_id = str(row.endpoint_id)
        raw_data = row.trace_data
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                raw_data = {}
        if isinstance(raw_data, dict) and "hops" in raw_data:
            traces_by_ep[ep_id] = raw_data["hops"]

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Set[Tuple[str, str]] = set()

    # Add all monitored nodes first
    for ep_id, ep_data in monitored_by_id.items():
        nodes[ep_id] = {
            "id": ep_id,
            "label": ep_data["label"],
            "ip_address": ep_data["ip_address"],
            "node_type": "monitored",
            "status": ep_data["status"],
            "device_type": ep_data["device_type"],
            "endpoint_id": ep_id,
        }

    # Helper maps for RCA downstream resolution
    transit_children: Dict[str, Set[str]] = {}  # node_id -> set of child node_ids

    # 3. Process edges and transit nodes
    for ep_id, ep_data in monitored_by_id.items():
        manual_parent = ep_data.get("manual_parent_id")
        if manual_parent and manual_parent in nodes:
            # Manual parent override takes priority
            edges.add((manual_parent, ep_id))
            if manual_parent not in transit_children:
                transit_children[manual_parent] = set()
            transit_children[manual_parent].add(ep_id)
            continue

        # Parse hops from diagnostic traceroute
        hops = traces_by_ep.get(ep_id, [])
        valid_hops = [h for h in hops if h.get("ip")]

        if not valid_hops:
            continue

        previous_node_id: Optional[str] = None

        for idx, hop in enumerate(valid_hops):
            hop_ip = hop["ip"]
            # Check if this hop IP corresponds to a monitored endpoint
            hop_ep_id = monitored_by_ip.get(hop_ip)

            if hop_ep_id:
                current_node_id = hop_ep_id
            else:
                # Transit node
                current_node_id = f"transit:{hop_ip}"
                if current_node_id not in nodes:
                    nodes[current_node_id] = {
                        "id": current_node_id,
                        "label": f"Transit ({hop_ip})",
                        "ip_address": hop_ip,
                        "node_type": "transit",
                        "status": "UP",
                        "device_type": "TRANSIT_ROUTER",
                        "endpoint_id": None,
                    }

            if previous_node_id and previous_node_id != current_node_id:
                edges.add((previous_node_id, current_node_id))
                if previous_node_id not in transit_children:
                    transit_children[previous_node_id] = set()
                transit_children[previous_node_id].add(current_node_id)

            previous_node_id = current_node_id

        # Connect last hop in trace to destination endpoint if different
        if previous_node_id and previous_node_id != ep_id:
            edges.add((previous_node_id, ep_id))
            if previous_node_id not in transit_children:
                transit_children[previous_node_id] = set()
            transit_children[previous_node_id].add(ep_id)

    # 4. Root Cause Analysis (RCA) - Infer Transit Failure (INFERRED_DOWN)
    def get_all_downstream_monitored_children(start_node: str, visited: Set[str]) -> Set[str]:
        monitored_children: Set[str] = set()
        visited.add(start_node)
        for child in transit_children.get(start_node, set()):
            if child in visited:
                continue
            if nodes.get(child, {}).get("node_type") == "monitored":
                monitored_children.add(child)
            else:
                monitored_children.update(get_all_downstream_monitored_children(child, visited))
        return monitored_children

    for node_id, node_info in list(nodes.items()):
        if node_info["node_type"] == "transit":
            downstream_monitored = get_all_downstream_monitored_children(node_id, set())
            if downstream_monitored:
                # Check if 100% of downstream monitored children are in a DOWN operational state
                all_down = all(
                    nodes[child_id]["status"] in ("DOWN", "DOWN-UNSTABLE")
                    for child_id in downstream_monitored
                    if child_id in nodes
                )
                if all_down:
                    node_info["status"] = "INFERRED_DOWN"

    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": src, "target": tgt} for src, tgt in edges],
    }
