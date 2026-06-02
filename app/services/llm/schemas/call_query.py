from pydantic import BaseModel
from typing import Literal, Optional


class CallQueryResult(BaseModel):
    """Schema for parsed call queries from the LLM."""
    intent: Literal[
        "recent_calls",
        "missed_calls",
        "outgoing_calls",
        "incoming_calls",
        "contact_history",
        "longest_call",
        "last_call_time",
        "calls_by_date"
    ]
    contact_name: Optional[str] = None
    relative: Optional[Literal["today", "yesterday", "this_week", "last_week"]] = None
    date: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
