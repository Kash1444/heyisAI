# app/models/location_log.py
#
# DESIGN PLACEHOLDER — full implementation deferred to a future phase.
# This model defines the schema for location history synced from the phone.
# DB table will be created automatically when app starts (auto-create is on).

from sqlalchemy import Column, Integer, String, BigInteger, Float, DateTime, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class LocationLog(Base):
    __tablename__ = "location_logs"

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "timestamp_ms",
            name="uq_location_device_timestamp"
        ),
        {"extend_existing": True}
    )

    id               = Column(Integer, primary_key=True, index=True)
    device_id        = Column(String, nullable=False, index=True)
    latitude         = Column(Float, nullable=False)
    longitude        = Column(Float, nullable=False)
    address          = Column(String, nullable=True)   # reverse-geocoded label, optional
    accuracy_meters  = Column(Float, nullable=True)
    timestamp_ms     = Column(BigInteger, nullable=False)
    created_at       = Column(DateTime, default=datetime.utcnow)
