from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from pydantic import BaseModel, field_validator, field_serializer
from app.services.timezone_utils import get_local_timezone

class UptimeReport(BaseModel):
    endpoint_id: UUID
    period_start: datetime
    period_end: datetime
    total_seconds: int
    uptime_seconds: int
    downtime_seconds: int
    unknown_seconds: int
    uptime_percentage: float
    incident_count: int

    model_config = {
        "from_attributes": True
    }

    @field_validator("uptime_percentage")
    @classmethod
    def validate_uptime_percentage(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("uptime_percentage must be between 0.0 and 100.0 inclusive")
        return v

    @field_serializer("period_start", "period_end")
    def serialize_period(self, v: datetime) -> str:
        local_tz = get_local_timezone()
        if v.tzinfo is None:
            v = v.replace(tzinfo=local_tz)
        else:
            v = v.astimezone(local_tz)
        return v.isoformat()

class IncidentRecord(BaseModel):
    endpoint_id: UUID
    incident_start: datetime
    incident_end: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    peak_detailed_state: Literal[
        "UP", "UP-UNSTABLE", "DOWN-UNSTABLE", "DOWN"
    ]
    contributing_event_count: int

    model_config = {
        "from_attributes": True
    }

    @field_serializer("incident_start")
    def serialize_incident_start(self, v: datetime) -> str:
        local_tz = get_local_timezone()
        if v.tzinfo is None:
            v = v.replace(tzinfo=local_tz)
        else:
            v = v.astimezone(local_tz)
        return v.isoformat()

    @field_serializer("incident_end")
    def serialize_incident_end(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        local_tz = get_local_timezone()
        if v.tzinfo is None:
            v = v.replace(tzinfo=local_tz)
        else:
            v = v.astimezone(local_tz)
        return v.isoformat()
