# app/services/notification_sync_service.py

from sqlalchemy.orm import Session
from app.models.notification_log import NotificationLog
from app.schemas.notification import NotificationSyncRequest


def sync_notifications(db: Session, payload: NotificationSyncRequest):
    inserted = 0
    skipped = 0

    for notif in payload.notifications:
        exists = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.device_id    == payload.device_id,
                NotificationLog.app_package  == notif.app_package,
                NotificationLog.timestamp_ms == notif.timestamp_ms
            )
            .first()
        )

        if exists:
            skipped += 1
            continue

        db_notif = NotificationLog(
            device_id    = payload.device_id,
            app_package  = notif.app_package,
            app_name     = notif.app_name,
            title        = notif.title,
            text         = notif.text,
            big_text     = notif.big_text,
            sub_text     = notif.sub_text,
            full_text    = notif.full_text,
            is_ongoing   = notif.is_ongoing,
            is_clearable = notif.is_clearable,
            category     = notif.category,    # pre-classified on Android
            timestamp_ms = notif.timestamp_ms,
        )
        db.add(db_notif)
        inserted += 1

    db.commit()
    print(f"[notification_sync] Inserted: {inserted} | Skipped: {skipped}")
    return {"inserted": inserted, "skipped": skipped, "total_received": len(payload.notifications)}

