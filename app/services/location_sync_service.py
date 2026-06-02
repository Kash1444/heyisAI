# app/services/location_sync_service.py
#
# DESIGN PLACEHOLDER — full implementation deferred to a future phase.
# The DB model and schema are in place; this service is a stub.

from sqlalchemy.orm import Session
from app.models.location_log import LocationLog
from app.schemas.location import LocationSyncRequest


def sync_location(db: Session, payload: LocationSyncRequest):
    inserted = 0
    skipped = 0

    for loc in payload.locations:
        exists = (
            db.query(LocationLog)
            .filter(
                LocationLog.device_id    == payload.device_id,
                LocationLog.timestamp_ms == loc.timestamp_ms
            )
            .first()
        )

        if exists:
            skipped += 1
            continue

        db_loc = LocationLog(
            device_id=payload.device_id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            address=loc.address,
            accuracy_meters=loc.accuracy_meters,
            timestamp_ms=loc.timestamp_ms,
        )
        db.add(db_loc)
        inserted += 1

    db.commit()
    print(f"[location_sync] Inserted: {inserted} | Skipped: {skipped}")
    return {"inserted": inserted, "skipped": skipped, "total_received": len(payload.locations)}
