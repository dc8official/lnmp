from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class EndpointSummary(BaseModel):
    id: UUID
    hostname: str
    ip_address: str
    device_type: str
    location: Optional[str] = None
    endpoint_status: Literal["ACTIVE", "DISABLED", "DELETED"]
    current_operational_state: Literal["UP", "DOWN"]
    current_detailed_state: Literal[
        "UP", "UP-UNSTABLE", "DOWN-UNSTABLE", "DOWN"
    ]
    current_health_score: float
    uptime_percentage_24h: float
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("last_seen")
    def serialize_last_seen(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.isoformat()


class EndpointDetail(EndpointSummary):
    description: Optional[str] = None
    monitoring_enabled: bool
    allow_incident_trace: bool = True
    allow_topology_discovery: bool = True
    enable_rca: bool = True
    enable_scheduled_discovery: bool = True
    is_l2_segment: bool = False
    manual_parent_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def serialize_created_updated(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.isoformat()
