# app/services/app_usage_sync_service.py

from sqlalchemy.orm import Session
from app.models.app_usage_log import AppUsageLog
from app.schemas.app_usage import AppUsageSyncRequest


def sync_app_usage(db: Session, payload: AppUsageSyncRequest):
    inserted = 0
    skipped = 0

    for event in payload.usage_events:
        exists = (
            db.query(AppUsageLog)
            .filter(
                AppUsageLog.device_id      == payload.device_id,
                AppUsageLog.app_package    == event.app_package,
                AppUsageLog.usage_start_ms == event.usage_start_ms
            )
            .first()
        )

        if exists:
            skipped += 1
            continue

        db_event = AppUsageLog(
            device_id=payload.device_id,
            app_package=event.app_package,
            app_name=event.app_name,
            usage_start_ms=event.usage_start_ms,
            usage_end_ms=event.usage_end_ms,
            duration_ms=event.duration_ms,
        )
        db.add(db_event)
        inserted += 1

    db.commit()
    print(f"[app_usage_sync] Inserted: {inserted} | Skipped: {skipped}")
    return {"inserted": inserted, "skipped": skipped, "total_received": len(payload.usage_events)}
