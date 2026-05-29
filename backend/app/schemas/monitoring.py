from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, model_validator

class MonitoringStatus(BaseModel):
    service_status: Literal["RUNNING", "DEGRADED", "UNAVAILABLE"]
    monitored_endpoint_count: int
    last_cycle_completed_at: Optional[datetime] = None
    active_gap: bool
    gap_start_time: Optional[datetime] = None
    app_version: str

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode="after")
    def validate_gap_start_time(self) -> "MonitoringStatus":
        if self.active_gap and self.gap_start_time is None:
            raise ValueError("gap_start_time is required when active_gap is True")
        return self
