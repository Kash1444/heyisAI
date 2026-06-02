from pydantic import BaseModel
from typing import Optional, List


class NotificationLogCreate(BaseModel):
    app_package:  str
    app_name:     Optional[str]  = None
    title:        Optional[str]  = None
    text:         Optional[str]  = None
    big_text:     Optional[str]  = None   # EXTRA_BIG_TEXT from Android
    sub_text:     Optional[str]  = None   # EXTRA_SUB_TEXT from Android
    full_text:    Optional[str]  = None   # all fields concatenated (for full-text search)
    is_ongoing:   Optional[bool] = None
    is_clearable: Optional[bool] = None
    # Pre-classified on Android at sync time.
    # Values: "food"|"ecommerce"|"banking"|"travel"|"entertainment"|"social"|None
    category:     Optional[str]  = None
    timestamp_ms: int


class NotificationSyncRequest(BaseModel):
    device_id:     str
    notifications: List[NotificationLogCreate]


class NotificationSyncResponse(BaseModel):
    success:        bool
    inserted_count: int
