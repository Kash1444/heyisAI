from pydantic import BaseModel
from typing import Optional, List


class SmsLogCreate(BaseModel):
    number: str
    name: Optional[str] = None
    body: str
    sms_type: str        # "Inbox" | "Sent" | "Draft"
    timestamp_ms: int


class SmsSyncRequest(BaseModel):
    device_id: str
    messages: List[SmsLogCreate]


class SmsSyncResponse(BaseModel):
    success: bool
    inserted_count: int
