# app/models/sms_log.py

from sqlalchemy import Column, Integer, String, BigInteger, Float, DateTime, Boolean, UniqueConstraint
from datetime import datetime
from app.core.database import Base


class SmsLog(Base):
    __tablename__ = "sms_logs"

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "number",
            "timestamp_ms",
            name="uq_sms_device_number_timestamp"
        ),
        {"extend_existing": True}
    )

    id           = Column(Integer, primary_key=True, index=True)
    device_id    = Column(String, nullable=False, index=True)
    number       = Column(String, nullable=False)
    name         = Column(String, nullable=True)
    body         = Column(String, nullable=False)
    sms_type     = Column(String, nullable=False)   # "Inbox" | "Sent" | "Draft"
    timestamp_ms = Column(BigInteger, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    # ── Enrichment columns (populated by background sms_enricher) ─────────────
    enriched         = Column(Boolean, default=False, nullable=False)
    # "bank" | "ecommerce" | "travel" | "food" | "entertainment" | "otp" | "promo" | "personal" | "unknown"
    category         = Column(String, nullable=True, index=True)
    # "HDFC" | "Amazon" | "Swiggy" | "IRCTC" | etc.
    platform         = Column(String, nullable=True, index=True)
    # extracted ₹ amount (e.g. 2499.0)
    amount           = Column(Float, nullable=True)
    # "debit" | "credit" | "refund"
    transaction_type = Column(String, nullable=True)
    # order ID / PNR / UPI ref / ticket ref
    entity_ref       = Column(String, nullable=True)
    # "confirmed" | "shipped" | "delivered" | "cancelled" | "otp"
    status           = Column(String, nullable=True)
