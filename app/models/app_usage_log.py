# app/models/app_usage_log.py

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class AppUsageLog(Base):
    __tablename__ = "app_usage_logs"

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "app_package",
            "usage_start_ms",
            name="uq_appusage_device_pkg_start"
        ),
        {"extend_existing": True}
    )

    id             = Column(Integer, primary_key=True, index=True)
    device_id      = Column(String, nullable=False, index=True)
    app_package    = Column(String, nullable=False)   # e.g. "com.instagram.android"
    app_name       = Column(String, nullable=True)    # e.g. "Instagram"
    usage_start_ms = Column(BigInteger, nullable=False)
    usage_end_ms   = Column(BigInteger, nullable=False)
    duration_ms    = Column(BigInteger, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow)
