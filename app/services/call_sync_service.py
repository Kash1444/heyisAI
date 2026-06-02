# app/services/call_sync_service.py

from sqlalchemy.orm import Session
from app.models.call_log import CallLog
from app.schemas.call_log import CallSyncRequest


def sync_calls(
    db: Session,
    payload: CallSyncRequest
):
    inserted = 0
    skipped = 0

    for call in payload.calls:

        # A call is uniquely identified by device + number + timestamp
        # (same phone, same contact, same exact moment = same call)
        exists = (
            db.query(CallLog)
            .filter(
                CallLog.device_id      == payload.device_id,
                CallLog.number         == call.number,
                CallLog.call_timestamp == call.call_timestamp
            )
            .first()
        )

        if exists:
            skipped += 1
            continue

        db_call = CallLog(
            device_id=payload.device_id,
            number=call.number,
            name=call.name,
            call_type=call.call_type,
            duration_seconds=call.duration_seconds,
            call_timestamp=call.call_timestamp
        )

        db.add(db_call)
        inserted += 1

    db.commit()

    print(f"[sync] Inserted: {inserted} | Skipped (duplicates): {skipped}")

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total_received": len(payload.calls)
    }