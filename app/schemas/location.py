# DESIGN PLACEHOLDER — full implementation deferred to a future phase.

from pydantic import BaseModel
from typing import Optional, List


class LocationLogCreate(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    accuracy_meters: Optional[float] = None
    timestamp_ms: int


class LocationSyncRequest(BaseModel):
    device_id: str
    locations: List[LocationLogCreate]


class LocationSyncResponse(BaseModel):
    success: bool
    inserted_count: int
