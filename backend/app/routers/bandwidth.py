from __future__ import annotations

import datetime
import ipaddress
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.endpoint import Endpoint
from app.models.flow_rollup import (
    FlowDailyRollup,
    FlowHourlyRollup,
    FlowMinuteRollup,
)
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

SENTINEL_UUID = UUID("00000000-0000-0000-0000-000000000000")

router = APIRouter(prefix="/bandwidth", tags=["bandwidth"])

_flow_redis_pool: Optional[Any] = None


async def get_flow_redis() -> Optional[Any]:
    """
    Returns an async Redis client for flow telemetry operations.
    Reuses driver_manager's client if available; otherwise initializes an independent pool.
    """
    global _flow_redis_pool
    dm_client = getattr(driver_manager, "_redis_client", None)
    if dm_client is not None:
        return dm_client

    if not getattr(settings.redis, "enabled", True):
        return None

    if _flow_redis_pool is None:
        try:
            import redis.asyncio as aioredis
            _flow_redis_pool = aioredis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                db=settings.redis.db,
                password=settings.redis.password or None,
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
            )
        except Exception as e:
            logger.debug("Failed to initialize standalone Redis client for flow: %s", e)
            return None
    return _flow_redis_pool


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
    if w == "1y":
        return datetime.timedelta(days=365)
    return datetime.timedelta(hours=1)


def _select_rollup_model_and_bucket_seconds(
    window: str, endpoint_id: Optional[UUID] = None
) -> Tuple[Any, float]:
    """
    Selects the optimal hypertable or continuous aggregate model and bucket interval.
    1h, 6h -> FlowMinuteRollup (60s)
    24h, 7d -> FlowHourlyRollup (3600s)
    30d, 1y -> FlowDailyRollup (86400s) or FlowHourlyRollup if endpoint_id filtered
    """
    w = window.lower().strip()
    if w in ("1h", "6h"):
        return FlowMinuteRollup, 60.0
    elif w in ("24h", "7d"):
        return FlowHourlyRollup, 3600.0
    elif w in ("30d", "1y"):
        if endpoint_id is not None:
            return FlowHourlyRollup, 3600.0
        return FlowDailyRollup, 86400.0
    else:
        return FlowMinuteRollup, 60.0


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
        func.coalesce(func.sum(FlowMinuteRollup.bytes), 0).label("total_bytes"),
        func.coalesce(
            func.sum(
                case(
                    (FlowMinuteRollup.dst_endpoint_id.is_not(None), FlowMinuteRollup.bytes),
                    else_=0,
                )
            ),
            0,
        ).label("ingress_bytes"),
        func.coalesce(
            func.sum(
                case(
                    (FlowMinuteRollup.src_endpoint_id.is_not(None), FlowMinuteRollup.bytes),
                    else_=0,
                )
            ),
            0,
        ).label("egress_bytes"),
        func.coalesce(func.sum(FlowMinuteRollup.flow_count), 0).label("total_flows"),
        func.count(
            func.distinct(
                case(
                    (FlowMinuteRollup.exporter_id != SENTINEL_UUID, FlowMinuteRollup.exporter_id),
                    else_=None,
                )
            )
        ).label("active_exporters"),
    ).where(FlowMinuteRollup.bucket >= five_min_ago)

    res = await db.execute(stmt)
    row = res.one_or_none()

    if row and len(row) >= 5:
        total_bytes = int(row[0] or 0)
        ingress_bytes = int(row[1] or 0)
        egress_bytes = int(row[2] or 0)
        total_flows = int(row[3] or 0)
        active_exporters = int(row[4] or 0)
        if ingress_bytes == 0 and egress_bytes == 0 and total_bytes > 0:
            ingress_bytes = total_bytes // 2
            egress_bytes = total_bytes - ingress_bytes
    elif row and len(row) >= 3:
        total_bytes = int(row[0] or 0)
        total_flows = int(row[1] or 0)
        active_exporters = int(row[2] or 0)
        ingress_bytes = total_bytes // 2
        egress_bytes = total_bytes - ingress_bytes
    else:
        total_bytes = ingress_bytes = egress_bytes = total_flows = active_exporters = 0

    # Calculate average bps over 300 seconds
    ingress_bps = (float(ingress_bytes) * 8.0) / 300.0 if ingress_bytes > 0 else 0.0
    egress_bps = (float(egress_bytes) * 8.0) / 300.0 if egress_bytes > 0 else 0.0

    # Fetch unmatched count from Redis
    unmatched_count = 0
    redis_client = await get_flow_redis()
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
    Dynamically routes to 1-minute hypertable, 1-hour CAGG, or 1-day CAGG based on window.
    """
    delta = _get_window_delta(window)
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - delta

    model, bucket_seconds = _select_rollup_model_and_bucket_seconds(window, endpoint_id)

    filters = [model.bucket >= start_time]
    if exporter_id:
        filters.append(model.exporter_id == exporter_id)
    if endpoint_id and hasattr(model, "src_endpoint_id"):
        filters.append(
            (model.src_endpoint_id == endpoint_id)
            | (model.dst_endpoint_id == endpoint_id)
        )

    # Ingress / Egress calculations via case expressions
    if endpoint_id and hasattr(model, "src_endpoint_id"):
        ingress_calc = func.sum(
            case((model.dst_endpoint_id == endpoint_id, model.bytes), else_=0)
        )
        egress_calc = func.sum(
            case((model.src_endpoint_id == endpoint_id, model.bytes), else_=0)
        )
    elif hasattr(model, "src_endpoint_id"):
        ingress_calc = func.sum(
            case((model.dst_endpoint_id.is_not(None), model.bytes), else_=0)
        )
        egress_calc = func.sum(
            case((model.src_endpoint_id.is_not(None), model.bytes), else_=0)
        )
    else:
        ingress_calc = func.sum(model.bytes) / 2
        egress_calc = func.sum(model.bytes) / 2

    stmt = (
        select(
            model.bucket,
            func.coalesce(func.sum(model.bytes), 0).label("total_bytes"),
            func.coalesce(ingress_calc, 0).label("ingress_bytes"),
            func.coalesce(egress_calc, 0).label("egress_bytes"),
        )
        .where(*filters)
        .group_by(model.bucket)
        .order_by(model.bucket.asc())
    )

    res = await db.execute(stmt)
    rows = res.all()

    points: List[TrafficSeriesPoint] = []
    for row in rows:
        bucket_time = row[0]
        byte_sum = int(row[1] or 0)
        if len(row) >= 4:
            in_bytes = int(row[2] or 0)
            eg_bytes = int(row[3] or 0)
            if in_bytes == 0 and eg_bytes == 0 and byte_sum > 0:
                in_bytes = byte_sum // 2
                eg_bytes = byte_sum - in_bytes
        else:
            in_bytes = byte_sum // 2
            eg_bytes = byte_sum - in_bytes

        in_bps = (float(in_bytes) * 8.0) / bucket_seconds
        eg_bps = (float(eg_bytes) * 8.0) / bucket_seconds
        iso_str = bucket_time.astimezone(datetime.timezone.utc).isoformat()
        points.append(
            TrafficSeriesPoint(
                timestamp=iso_str,
                ingress_bps=round(in_bps, 2),
                egress_bps=round(eg_bps, 2),
            )
        )

    return APIResponse.success(
        data=TrafficSeriesResponse(window=window, points=points)
    )


@router.get("/top-talkers", response_model=APIResponse)
async def get_top_talkers(
    window: str = Query(default="1h"),
    limit: int = Query(default=10, ge=1, le=50),
    endpoint_id: Optional[UUID] = Query(default=None),
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
    ep_filters = [FlowMinuteRollup.bucket >= start_time]
    if endpoint_id is not None:
        ep_filters.append(
            or_(
                FlowMinuteRollup.src_endpoint_id == endpoint_id,
                FlowMinuteRollup.dst_endpoint_id == endpoint_id,
            )
        )

    top_ep_stmt = (
        select(
            FlowMinuteRollup.src_ip.label("ip"),
            FlowMinuteRollup.src_endpoint_id.label("ep_id"),
            func.sum(FlowMinuteRollup.bytes).label("total_bytes"),
            func.sum(FlowMinuteRollup.flow_count).label("total_flows"),
            func.coalesce(
                func.sum(
                    case(
                        (FlowMinuteRollup.dst_endpoint_id.is_not(None), FlowMinuteRollup.bytes),
                        else_=0,
                    )
                ),
                0,
            ).label("ingress_bytes"),
            func.coalesce(
                func.sum(
                    case(
                        (FlowMinuteRollup.src_endpoint_id.is_not(None), FlowMinuteRollup.bytes),
                        else_=0,
                    )
                ),
                0,
            ).label("egress_bytes"),
        )
        .where(*ep_filters)
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
    for row in ep_rows:
        ip = row[0]
        ep_id = row[1]
        b_sum = row[2]
        f_sum = row[3]
        total_b = int(b_sum or 0)
        if len(row) >= 6:
            in_b = int(row[4] or 0)
            eg_b = int(row[5] or 0)
            if in_b == 0 and eg_b == 0:
                eg_b = total_b
        else:
            in_b = 0
            eg_b = total_b
        h_name = hostnames.get(ep_id)
        top_endpoints.append(
            TopTalkerItem(
                endpoint_id=ep_id,
                ip_address=str(ip),
                hostname=h_name,
                total_bytes=total_b,
                ingress_bytes=in_b,
                egress_bytes=eg_b,
                flow_count=int(f_sum or 0),
            )
        )

    # 2. Top Conversations
    conv_filters = [FlowMinuteRollup.bucket >= start_time]
    if endpoint_id is not None:
        conv_filters.append(
            or_(
                FlowMinuteRollup.src_endpoint_id == endpoint_id,
                FlowMinuteRollup.dst_endpoint_id == endpoint_id,
            )
        )

    top_conv_stmt = (
        select(
            FlowMinuteRollup.src_ip,
            FlowMinuteRollup.dst_ip,
            FlowMinuteRollup.protocol,
            FlowMinuteRollup.dst_port,
            func.sum(FlowMinuteRollup.bytes).label("total_bytes"),
            func.sum(FlowMinuteRollup.flow_count).label("total_flows"),
        )
        .where(*conv_filters)
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
    Dynamically routes to hypertable or continuous aggregates based on window.
    """
    delta = _get_window_delta(window)
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - delta

    model, _ = _select_rollup_model_and_bucket_seconds(window)

    stmt = (
        select(
            model.protocol,
            model.dst_port,
            func.sum(model.bytes).label("total_bytes"),
        )
        .where(model.bucket >= start_time)
        .group_by(model.protocol, model.dst_port)
        .order_by(func.sum(model.bytes).desc())
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
    redis_client = await get_flow_redis()
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
    redis_client = await get_flow_redis()
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
