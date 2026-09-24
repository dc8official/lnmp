from __future__ import annotations

from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class BandwidthOverview(BaseModel):
    total_ingress_bps: float
    total_egress_bps: float
    active_exporters_count: int
    unmatched_exporters_count: int
    total_flows_count: int

    model_config = ConfigDict(from_attributes=True)


class TrafficSeriesPoint(BaseModel):
    timestamp: str
    ingress_bps: float
    egress_bps: float

    model_config = ConfigDict(from_attributes=True)


class TrafficSeriesResponse(BaseModel):
    window: str
    points: List[TrafficSeriesPoint]

    model_config = ConfigDict(from_attributes=True)


class TopTalkerItem(BaseModel):
    endpoint_id: Optional[UUID] = None
    ip_address: str
    hostname: Optional[str] = None
    total_bytes: int
    ingress_bytes: int
    egress_bytes: int
    flow_count: int

    model_config = ConfigDict(from_attributes=True)


class TopConversationItem(BaseModel):
    src_ip: str
    dst_ip: str
    src_hostname: Optional[str] = None
    dst_hostname: Optional[str] = None
    protocol: str
    dst_port: int
    total_bytes: int
    flow_count: int

    model_config = ConfigDict(from_attributes=True)


class TopTalkersResponse(BaseModel):
    top_endpoints: List[TopTalkerItem]
    top_conversations: List[TopConversationItem]

    model_config = ConfigDict(from_attributes=True)


class ApplicationDistributionItem(BaseModel):
    protocol_name: str
    port: int
    service_label: str
    total_bytes: int
    percentage: float

    model_config = ConfigDict(from_attributes=True)


class ApplicationDistributionResponse(BaseModel):
    applications: List[ApplicationDistributionItem]

    model_config = ConfigDict(from_attributes=True)


class FlowExporterItem(BaseModel):
    id: UUID
    hostname: str
    primary_ip: str
    flow_exporter_ips: List[str]
    interface_aliases: Dict[str, str]
    last_flow_time: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UnmatchedExporterItem(BaseModel):
    ip_address: str
    last_seen: str

    model_config = ConfigDict(from_attributes=True)


class ExportersResponse(BaseModel):
    exporters: List[FlowExporterItem]
    unmatched: List[UnmatchedExporterItem]

    model_config = ConfigDict(from_attributes=True)


class MapExporterRequest(BaseModel):
    endpoint_id: UUID


class FlowPreflightResponse(BaseModel):
    redis_connected: bool
    redis_version: Optional[str] = None
    redis_version_supported: bool
    stream_write_success: bool
    rmem_max: Optional[int] = None
    rmem_max_supported: bool = True
    udp_ports_available: bool = True
    port_conflicts: List[int] = Field(default_factory=list)
    ready: bool
    message: str

    model_config = ConfigDict(from_attributes=True)
