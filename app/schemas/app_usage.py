from pydantic import BaseModel
from typing import Optional, List


class AppUsageLogCreate(BaseModel):
    app_package: str
    app_name: Optional[str] = None
    usage_start_ms: int
    usage_end_ms: int
    duration_ms: int


class AppUsageSyncRequest(BaseModel):
    device_id: str
    usage_events: List[AppUsageLogCreate]


class AppUsageSyncResponse(BaseModel):
    success: bool
    inserted_count: int
