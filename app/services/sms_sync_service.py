# app/services/sms_sync_service.py

from sqlalchemy.orm import Session
from app.models.sms_log import SmsLog
from app.schemas.sms import SmsSyncRequest


def sync_sms(db: Session, payload: SmsSyncRequest):
    inserted = 0
    skipped = 0

    for msg in payload.messages:
        exists = (
            db.query(SmsLog)
            .filter(
                SmsLog.device_id    == payload.device_id,
                SmsLog.number       == msg.number,
                SmsLog.timestamp_ms == msg.timestamp_ms
            )
            .first()
        )

        if exists:
            skipped += 1
            continue

        db_sms = SmsLog(
            device_id    = payload.device_id,
            number       = msg.number,
            name         = msg.name,
            body         = msg.body,
            sms_type     = msg.sms_type,
            timestamp_ms = msg.timestamp_ms,
            enriched     = False,   # background task will populate enrichment fields
        )
        db.add(db_sms)
        inserted += 1

    db.commit()
    print(f"[sms_sync] Inserted: {inserted} | Skipped (duplicates): {skipped}")
    return {"inserted": inserted, "skipped": skipped, "total_received": len(payload.messages)}
