from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel

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

    model_config = {
        "from_attributes": True
    }

class EndpointDetail(EndpointSummary):
    description: Optional[str] = None
    monitoring_enabled: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
