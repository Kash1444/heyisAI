# app/models/call_log.py

from sqlalchemy import (
    Column, Integer, String,
    BigInteger, DateTime, UniqueConstraint
)
from datetime import datetime
from app.core.database import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "number",
            "call_timestamp",
            name="uq_call_device_number_timestamp"
        ),
        {"extend_existing": True}   # ← fixes the double-import error
    )

    id               = Column(Integer, primary_key=True, index=True)
    device_id        = Column(String, nullable=False, index=True)
    number           = Column(String, nullable=False)
    name             = Column(String, nullable=True)
    call_type        = Column(String, nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    call_timestamp   = Column(BigInteger, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)