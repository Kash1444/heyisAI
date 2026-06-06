from pydantic import BaseModel
from typing import Optional, List


class CallLogCreate(BaseModel):
    number: str
    name: Optional[str] = None

    call_type: str

    duration_seconds: int

    call_timestamp: int


class CallSyncRequest(BaseModel):
    device_id: str
    calls: List[CallLogCreate]


class CallSyncResponse(BaseModel):
    success: bool
    inserted_count: int