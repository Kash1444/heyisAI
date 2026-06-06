# app/models/notification_log.py

from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "app_package",
            "timestamp_ms",
            name="uq_notif_device_app_timestamp"
        ),
        {"extend_existing": True}
    )

    id           = Column(Integer, primary_key=True, index=True)
    device_id    = Column(String, nullable=False, index=True)
    app_package  = Column(String, nullable=False)   # e.g. "com.whatsapp"
    app_name     = Column(String, nullable=True)    # e.g. "WhatsApp"
    title        = Column(String, nullable=True)
    text         = Column(String, nullable=True)
    big_text     = Column(String, nullable=True)    # expanded notification body
    sub_text     = Column(String, nullable=True)    # secondary text line
    full_text    = Column(String, nullable=True)    # all text fields concatenated
    is_ongoing   = Column(Boolean, nullable=True)   # e.g. media/navigation notifications
    is_clearable = Column(Boolean, nullable=True)   # whether user can dismiss
    # Category detected on Android at sync time — avoids expensive runtime keyword scanning.
    # Values: "food" | "ecommerce" | "banking" | "travel" | "entertainment" | "social" | None
    category     = Column(String, nullable=True, index=True)
    timestamp_ms = Column(BigInteger, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

