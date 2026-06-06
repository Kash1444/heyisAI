# app/services/tools/location_tool.py
#
# DESIGN PLACEHOLDER — full implementation deferred to a future phase.
# Both functions gracefully return empty results when no data is present.

from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.models.location_log import LocationLog


def get_location_at_timestamp(db, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find the closest location record to a given timestamp.

    Supported params:
        timestamp_ms (int) — the target moment in epoch milliseconds
        window_minutes (int) — search window on each side (default 15)

    Returns a single location dict, or an empty dict if no data.
    """
    timestamp_ms   = params.get("timestamp_ms")
    window_minutes = int(params.get("window_minutes", 15))

    # Gracefully skip — no location data yet
    if db.query(LocationLog).count() == 0:
        print("[location_tool] No location data in DB — skipping.")
        return {}

    if not timestamp_ms:
        print("[location_tool] get_location_at_timestamp: no timestamp_ms provided.")
        return {}

    ts      = int(timestamp_ms)
    window  = window_minutes * 60 * 1000   # ms
    start   = ts - window
    end     = ts + window

    record = (
        db.query(LocationLog)
        .filter(
            LocationLog.timestamp_ms >= start,
            LocationLog.timestamp_ms <= end,
        )
        # closest record first
        .order_by(
            (LocationLog.timestamp_ms - ts) * (LocationLog.timestamp_ms - ts)
        )
        .first()
    )

    if not record:
        return {}

    dt = datetime.fromtimestamp(record.timestamp_ms / 1000)
    return {
        "latitude": record.latitude,
        "longitude": record.longitude,
        "address": record.address,
        "accuracy_meters": record.accuracy_meters,
        "timestamp_ms": record.timestamp_ms,
        "datetime_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_location_range(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Return location records within a date range.

    Supported params:
        date          (str)  — "YYYY-MM-DD"
        date_from     (str)  — "YYYY-MM-DD"
        date_to       (str)  — "YYYY-MM-DD"
        relative_date (str)  — "today" | "yesterday" | "this_week" | "last_week"
        limit         (int)  — default 50
    """
    # Gracefully skip — no location data yet
    if db.query(LocationLog).count() == 0:
        print("[location_tool] No location data in DB — skipping.")
        return []

    relative  = params.get("relative_date", "")
    date_str  = params.get("date", "")
    date_from = params.get("date_from", "")
    date_to   = params.get("date_to", "")
    limit     = int(params.get("limit", 50))

    now = datetime.now()
    start_dt = end_dt = None

    if relative == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now
    elif relative == "yesterday":
        y = now - timedelta(days=1)
        start_dt = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = y.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif relative == "this_week":
        start_dt = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now
    elif relative == "last_week":
        s = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = s - timedelta(days=7)
        end_dt   = s - timedelta(seconds=1)
    elif date_str:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            start_dt = d.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt   = d.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            pass
    elif date_from and date_to:
        try:
            start_dt = datetime.strptime(date_from, "%Y-%m-%d")
            end_dt   = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            pass

    if not (start_dt and end_dt):
        return []

    records = (
        db.query(LocationLog)
        .filter(
            LocationLog.timestamp_ms >= int(start_dt.timestamp() * 1000),
            LocationLog.timestamp_ms <= int(end_dt.timestamp() * 1000),
        )
        .order_by(LocationLog.timestamp_ms.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "latitude": r.latitude,
            "longitude": r.longitude,
            "address": r.address,
            "timestamp_ms": r.timestamp_ms,
            "datetime_str": datetime.fromtimestamp(r.timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for r in records
    ]
