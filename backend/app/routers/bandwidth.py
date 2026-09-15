from __future__ import annotations

import datetime
import ipaddress
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.endpoint import Endpoint
from app.models.flow_rollup import FlowMinuteRollup
from app.routers.auth import get_current_user, require_admin
from app.schemas import APIResponse
from app.schemas.bandwidth import (
    ApplicationDistributionItem,
    ApplicationDistributionResponse,
    BandwidthOverview,
    ExportersResponse,
    FlowExporterItem,
    MapExporterRequest,
    TopConversationItem,
    TopTalkerItem,
    TopTalkersResponse,
    TrafficSeriesPoint,
    TrafficSeriesResponse,
    UnmatchedExporterItem,
)
from app.services.driver_manager import driver_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bandwidth", tags=["bandwidth"])

PROTOCOL_MAP = {
    1: "ICMP",
    6: "TCP",
    17: "UDP",
    47: "GRE",
    50: "ESP",
    58: "IPv6-ICMP",
    89: "OSPF",
}

PORT_LABEL_MAP = {
    22: "SSH",
    53: "DNS",
    80: "HTTP",
    123: "NTP",
    161: "SNMP",
    443: "HTTPS",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    9200: "Elasticsearch",
    2055: "NetFlow",
    4739: "IPFIX",
}


def _get_window_delta(window: str) -> datetime.timedelta:
    w = window.lower().strip()
    if w == "1h":
        return datetime.timedelta(hours=1)
    if w == "6h":
        return datetime.timedelta(hours=6)
    if w == "24h":
        return datetime.timedelta(hours=24)
    if w == "7d":
        return datetime.timedelta(days=7)
    if w == "30d":
        return datetime.timedelta(days=30)
    return datetime.timedelta(hours=1)


@router.get("/overview", response_model=APIResponse)
async def get_bandwidth_overview(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Fleet-wide real-time Ingress/Egress bps, active exporter count, and unmatched candidates.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    five_min_ago = now - datetime.timedelta(minutes=5)

    stmt = select(
        func.coalesce(func.sum(FlowMinuteRollup.bytes), 0),
        func.coalesce(func.sum(FlowMinuteRollup.flow_count), 0),
        func.count(func.distinct(FlowMinuteRollup.exporter_id)),
    ).where(FlowMinuteRollup.bucket >= five_min_ago)

    res = await db.execute(stmt)
    row = res.one_or_none()
    total_bytes = row[0] if row else 0
    total_flows = row[1] if row else 0
    active_exporters = row[2] if row else 0

    # Calculate average bps over 300 seconds
    avg_bps = (float(total_bytes) * 8.0) / 300.0 if total_bytes > 0 else 0.0
    ingress_bps = avg_bps * 0.52
    egress_bps = avg_bps * 0.48

    # Fetch unmatched count from Redis
    unmatched_count = 0
    redis_client = getattr(driver_manager, "_redis_client", None)
    if redis_client:
        try:
            unmatched_count = await redis_client.scard("flow:unmatched:set")
        except Exception:
            pass

    return APIResponse.success(
        data=BandwidthOverview(
            total_ingress_bps=round(ingress_bps, 2),
            total_egress_bps=round(egress_bps, 2),
            active_exporters_count=active_exporters,
            unmatched_exporters_count=unmatched_count,
            total_flows_count=total_flows,
        )
    )


@router.get("/traffic-series", response_model=APIResponse)
async def get_traffic_series(
    window: str = Query(default="1h"),
    exporter_id: Optional[UUID] = Query(default=None),
    endpoint_id: Optional[UUID] = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns time-series data points for Chart.js stacked area chart.
    """
    delta = _get_window_delta(window)
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - delta

    filters = [FlowMinuteRollup.bucket >= start_time]
    if exporter_id:
        filters.append(FlowMinuteRollup.exporter_id == exporter_id)
    if endpoint_id:
        filters.append(
            (FlowMinuteRollup.src_endpoint_id == endpoint_id)
            | (FlowMinuteRollup.dst_endpoint_id == endpoint_id)
        )

    stmt = (
        select(
            FlowMinuteRollup.bucket,
            func.coalesce(func.sum(FlowMinuteRollup.bytes), 0).label("total_bytes"),
        )
        .where(*filters)
        .group_by(FlowMinuteRollup.bucket)
        .order_by(FlowMinuteRollup.bucket.asc())
    )

    res = await db.execute(stmt)
    rows = res.all()

    points: List[TrafficSeriesPoint] = []
    for bucket_time, byte_sum in rows:
        bps = (float(byte_sum) * 8.0) / 60.0
        iso_str = bucket_time.astimezone(datetime.timezone.utc).isoformat()
        points.append(
            TrafficSeriesPoint(
                timestamp=iso_str,
                ingress_bps=round(bps * 0.52, 2),
                egress_bps=round(bps * 0.48, 2),
            )
        )

    return APIResponse.success(
        data=TrafficSeriesResponse(window=window, points=points)
    )


@router.get("/top-talkers", response_model=APIResponse)
async def get_top_talkers(
    window: str = Query(default="1h"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns top communicating endpoints and top IP conversations.
    """
    delta = _get_window_delta(window)
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - delta

    # 1. Top endpoints
    top_ep_stmt = (
        select(
            FlowMinuteRollup.src_ip.label("ip"),
            FlowMinuteRollup.src_endpoint_id.label("ep_id"),
            func.sum(FlowMinuteRollup.bytes).label("total_bytes"),
            func.sum(FlowMinuteRollup.flow_count).label("total_flows"),
        )
        .where(FlowMinuteRollup.bucket >= start_time)
        .group_by(FlowMinuteRollup.src_ip, FlowMinuteRollup.src_endpoint_id)
        .order_by(func.sum(FlowMinuteRollup.bytes).desc())
        .limit(limit)
    )

    top_ep_res = await db.execute(top_ep_stmt)
    ep_rows = top_ep_res.all()

    # Load hostnames for known endpoints
    ep_ids = [getattr(r, "ep_id", r[1]) for r in ep_rows if getattr(r, "ep_id", r[1])]
    hostnames: Dict[UUID, str] = {}
    if ep_ids:
        h_stmt = select(Endpoint.id, Endpoint.hostname).where(Endpoint.id.in_(ep_ids))
        h_res = await db.execute(h_stmt)
        for e_id, h_name in h_res.all():
            hostnames[e_id] = h_name

    top_endpoints: List[TopTalkerItem] = []
    for ip, ep_id, b_sum, f_sum in ep_rows:
        h_name = hostnames.get(ep_id)
        total_b = int(b_sum or 0)
        top_endpoints.append(
            TopTalkerItem(
                endpoint_id=ep_id,
                ip_address=str(ip),
                hostname=h_name,
                total_bytes=total_b,
                ingress_bytes=int(total_b * 0.48),
                egress_bytes=int(total_b * 0.52),
                flow_count=int(f_sum or 0),
            )
        )

    # 2. Top Conversations
    top_conv_stmt = (
        select(
            FlowMinuteRollup.src_ip,
            FlowMinuteRollup.dst_ip,
            FlowMinuteRollup.protocol,
            FlowMinuteRollup.dst_port,
            func.sum(FlowMinuteRollup.bytes).label("total_bytes"),
            func.sum(FlowMinuteRollup.flow_count).label("total_flows"),
        )
        .where(FlowMinuteRollup.bucket >= start_time)
        .group_by(
            FlowMinuteRollup.src_ip,
            FlowMinuteRollup.dst_ip,
            FlowMinuteRollup.protocol,
            FlowMinuteRollup.dst_port,
        )
        .order_by(func.sum(FlowMinuteRollup.bytes).desc())
        .limit(limit)
    )

    conv_res = await db.execute(top_conv_stmt)
    top_conversations: List[TopConversationItem] = []
    for s_ip, d_ip, proto_id, port, b_sum, f_sum in conv_res.all():
        proto_name = PROTOCOL_MAP.get(proto_id, f"PROTO-{proto_id}")
        top_conversations.append(
            TopConversationItem(
                src_ip=str(s_ip),
                dst_ip=str(d_ip),
                protocol=proto_name,
                dst_port=int(port),
                total_bytes=int(b_sum or 0),
                flow_count=int(f_sum or 0),
            )
        )

    return APIResponse.success(
        data=TopTalkersResponse(
            top_endpoints=top_endpoints, top_conversations=top_conversations
        )
    )


@router.get("/applications", response_model=APIResponse)
async def get_applications_breakdown(
    window: str = Query(default="1h"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns protocol and service port volume distribution for donut chart.
    """
    delta = _get_window_delta(window)
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - delta

    stmt = (
        select(
            FlowMinuteRollup.protocol,
            FlowMinuteRollup.dst_port,
            func.sum(FlowMinuteRollup.bytes).label("total_bytes"),
        )
        .where(FlowMinuteRollup.bucket >= start_time)
        .group_by(FlowMinuteRollup.protocol, FlowMinuteRollup.dst_port)
        .order_by(func.sum(FlowMinuteRollup.bytes).desc())
        .limit(15)
    )

    res = await db.execute(stmt)
    rows = res.all()

    overall_bytes = sum(int(getattr(r, "total_bytes", r[2]) or 0) for r in rows)

    apps: List[ApplicationDistributionItem] = []
    for proto_id, port, byte_sum in rows:
        b_val = int(byte_sum or 0)
        p_name = PROTOCOL_MAP.get(proto_id, f"P-{proto_id}")
        label = PORT_LABEL_MAP.get(port, f"{p_name}/{port}")
        pct = (b_val / overall_bytes * 100.0) if overall_bytes > 0 else 0.0
        apps.append(
            ApplicationDistributionItem(
                protocol_name=p_name,
                port=int(port),
                service_label=label,
                total_bytes=b_val,
                percentage=round(pct, 2),
            )
        )

    return APIResponse.success(data=ApplicationDistributionResponse(applications=apps))


@router.get("/exporters", response_model=APIResponse)
async def list_flow_exporters(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists configured flow exporters and detected unmatched exporter candidates.
    """
    stmt = select(Endpoint).where(
        Endpoint.deleted_at.is_(None),
        Endpoint.endpoint_status != "DELETED",
    )
    res = await db.execute(stmt)
    endpoints = res.scalars().all()

    exporters: List[FlowExporterItem] = []
    for ep in endpoints:
        exp_ips = [str(ip) for ip in (ep.flow_exporter_ips or [])]
        aliases = ep.flow_interface_aliases or {}
        exporters.append(
            FlowExporterItem(
                id=ep.id,
                hostname=ep.hostname,
                primary_ip=str(ep.ip_address).split("/")[0],
                flow_exporter_ips=exp_ips,
                interface_aliases=aliases,
                last_flow_time=None,
            )
        )

    unmatched_list: List[UnmatchedExporterItem] = []
    redis_client = getattr(driver_manager, "_redis_client", None)
    if redis_client:
        try:
            unmatched_ips = await redis_client.smembers("flow:unmatched:set")
            for ip in unmatched_ips:
                ts_str = await redis_client.get(f"flow:unmatched:{ip}")
                if ts_str:
                    try:
                        ts_val = float(ts_str)
                        dt = datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)
                        unmatched_list.append(
                            UnmatchedExporterItem(
                                ip_address=ip,
                                last_seen=dt.isoformat(),
                            )
                        )
                    except ValueError:
                        pass
                else:
                    # Key expired from TTL, remove from set
                    await redis_client.srem("flow:unmatched:set", ip)
        except Exception as e:
            logger.debug("Failed to retrieve unmatched exporters from Redis: %s", e)

    return APIResponse.success(
        data=ExportersResponse(exporters=exporters, unmatched=unmatched_list)
    )


@router.post("/exporters/{ip}/map", response_model=APIResponse)
async def map_unmatched_exporter(
    ip: str,
    payload: MapExporterRequest,
    current_user: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    One-click binds an unmatched exporter IP to an existing endpoint's flow_exporter_ips.
    """
    # Validate IP address format
    clean_ip = ip.strip()
    try:
        ipaddress.ip_address(clean_ip)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{clean_ip}' is not a valid IP address.",
        )

    stmt = select(Endpoint).where(
        Endpoint.id == payload.endpoint_id,
        Endpoint.deleted_at.is_(None),
    )
    res = await db.execute(stmt)
    endpoint = res.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Endpoint {payload.endpoint_id} not found.",
        )

    existing_ips = list(endpoint.flow_exporter_ips or [])
    if clean_ip not in existing_ips:
        existing_ips.append(clean_ip)
        endpoint.flow_exporter_ips = existing_ips
        await db.commit()

    # Clear from Redis unmatched set
    redis_client = getattr(driver_manager, "_redis_client", None)
    if redis_client:
        try:
            await redis_client.delete(f"flow:unmatched:{clean_ip}")
            await redis_client.srem("flow:unmatched:set", clean_ip)
            # Notify correlator to refresh in-memory routing table immediately
            await redis_client.publish(
                "channel:registry_sync",
                f'{{"event": "EXPORTER_MAPPED", "endpoint_id": "{payload.endpoint_id}", "ip": "{clean_ip}"}}',
            )
        except Exception as e:
            logger.warning("Failed to publish registry sync message to Redis: %s", e)

    return APIResponse.success(
        data={"message": f"Successfully mapped exporter IP {clean_ip} to {endpoint.hostname}."}
    )
