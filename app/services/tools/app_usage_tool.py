# app/services/tools/app_usage_tool.py

from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.models.app_usage_log import AppUsageLog


def _usage_to_dict(u: AppUsageLog) -> Dict[str, Any]:
    start_dt = datetime.fromtimestamp(u.usage_start_ms / 1000)
    end_dt   = datetime.fromtimestamp(u.usage_end_ms   / 1000)
    return {
        "app_name": u.app_name,
        "app_package": u.app_package,
        "usage_start_ms": u.usage_start_ms,
        "usage_end_ms": u.usage_end_ms,
        "duration_ms": u.duration_ms,
        "duration_minutes": round(u.duration_ms / 60000, 1),
        "start_str": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_str": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_app_usage(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Query app usage sessions.

    Supported params:
        app_name      (str)  — partial app name filter (e.g. "Instagram")
        app_package   (str)  — exact package filter
        relative_date (str)  — "today" | "yesterday" | "this_week" | "last_week"
        date          (str)  — "YYYY-MM-DD"
        date_from     (str)  — "YYYY-MM-DD"
        date_to       (str)  — "YYYY-MM-DD"
        timestamp_ms  (int)  — find sessions active at this timestamp
        limit         (int)  — default 10
    """
    app_name     = params.get("app_name", "")
    app_package  = params.get("app_package", "")
    relative     = params.get("relative_date", "")
    date_str     = params.get("date", "")
    date_from    = params.get("date_from", "")
    date_to      = params.get("date_to", "")
    timestamp_ms = params.get("timestamp_ms")
    limit        = int(params.get("limit", 10))

    # Gracefully skip if table is empty
    if db.query(AppUsageLog).count() == 0:
        print("[app_usage_tool] No app usage data in DB — skipping.")
        return []

    query = db.query(AppUsageLog)

    if app_name:
        query = query.filter(AppUsageLog.app_name.ilike(f"%{app_name}%"))

    if app_package:
        query = query.filter(AppUsageLog.app_package == app_package)

    now = datetime.now()
    start_dt = end_dt = None

    # Exact timestamp: find sessions that were active at that moment
    if timestamp_ms:
        ts = int(timestamp_ms)
        query = query.filter(
            AppUsageLog.usage_start_ms <= ts,
            AppUsageLog.usage_end_ms   >= ts,
        )
    elif relative == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
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

    if start_dt and end_dt:
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms   = int(end_dt.timestamp() * 1000)
        # Sessions that overlap with the requested window
        query = query.filter(
            AppUsageLog.usage_start_ms <= end_ms,
            AppUsageLog.usage_end_ms   >= start_ms,
        )

    results = query.order_by(AppUsageLog.usage_start_ms.desc()).limit(limit).all()
    return [_usage_to_dict(u) for u in results]
