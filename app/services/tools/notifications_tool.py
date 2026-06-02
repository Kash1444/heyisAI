# app/services/tools/notifications_tool.py

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import or_
from app.models.notification_log import NotificationLog


# ---------------------------------------------------------------------------
# Valid category values (must match Android's NotificationSyncManager.categorize())
# ---------------------------------------------------------------------------
VALID_CATEGORIES = {"food", "ecommerce", "banking", "travel", "entertainment", "social"}

# ---------------------------------------------------------------------------
# Keyword fallback maps — used ONLY when a record's category column is NULL
# (e.g. synced from an older Android client that didn't send the category field).
# Mirrors the keyword lists in NotificationSyncManager.kt / NotificationHelper.kt.
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "food": [
        "swiggy", "zomato", "dunzo", "bigbasket", "grofers", "blinkit", "zepto",
        "jiomart", "licious", "freshmenu", "faasos", "box8", "dominos", "pizzahut",
        "kfc", "mcdonalds", "burgerking", "subway", "food", "delivery", "order",
        "restaurant", "meal",
    ],
    "ecommerce": [
        "amazon", "flipkart", "myntra", "ajio", "nykaa", "purplle", "tatacliq",
        "croma", "snapdeal", "shopclues", "paytmmall", "order", "delivery", "shipped",
        "tracking", "purchase", "payment", "invoice", "receipt",
    ],
    "banking": [
        "sbi", "hdfc", "icici", "axis", "kotak", "yes", "bank", "account",
        "transaction", "upi", "payment", "transfer", "debit", "credit",
        "balance", "atm", "card",
    ],
    "travel": [
        "makemytrip", "goibibo", "booking", "cleartrip", "yatra", "irctc",
        "flight", "hotel", "reservation", "travel", "trip", "journey", "ticket",
    ],
    "entertainment": [
        "netflix", "amazon prime", "hotstar", "sonyliv", "zee5", "voot",
        "altbalaji", "movie", "show", "series", "entertainment", "streaming",
        "video", "music",
    ],
    "social": [
        "whatsapp", "facebook", "instagram", "twitter", "linkedin", "telegram",
        "snapchat", "tiktok", "youtube", "social", "message", "chat", "post",
    ],
}


def _keyword_fallback_filter(category: str):
    """
    Build a SQLAlchemy OR filter for rows whose category column is NULL
    but whose text fields match the given category's keywords.
    Used as a fallback for records synced by older app versions.
    """
    keywords = _CATEGORY_KEYWORDS.get(category, [])
    conditions = []
    for kw in keywords:
        pattern = f"%{kw}%"
        conditions.extend([
            NotificationLog.app_name.ilike(pattern),
            NotificationLog.app_package.ilike(pattern),
            NotificationLog.title.ilike(pattern),
            NotificationLog.text.ilike(pattern),
            NotificationLog.full_text.ilike(pattern),
        ])
    return or_(*conditions) if conditions else None


def _notif_to_dict(n: NotificationLog) -> Dict[str, Any]:
    dt = datetime.fromtimestamp(n.timestamp_ms / 1000)
    return {
        "app_name":    n.app_name,
        "app_package": n.app_package,
        "title":       n.title,
        "text":        n.text,
        "big_text":    n.big_text,
        "full_text":   n.full_text,
        "category":    n.category,
        "is_ongoing":  n.is_ongoing,
        "timestamp_ms": n.timestamp_ms,
        "datetime_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def search_notifications(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search notification logs.

    Supported params:
        app_name      (str)  — partial match on app display name (e.g. "WhatsApp")
        app_package   (str)  — exact Android package (e.g. "com.whatsapp")
        keyword       (str)  — text to search in title, text, big_text, full_text
        category      (str)  — "food"|"ecommerce"|"banking"|"travel"|"entertainment"|"social"
                               PRIMARY path: matches category column (fast indexed lookup).
                               FALLBACK path: if category column is NULL, uses keyword scan
                               (for records synced by older app versions without classification).
        relative_date (str)  — "today" | "yesterday" | "this_week" | "last_week"
        date          (str)  — "YYYY-MM-DD"
        date_from     (str)  — "YYYY-MM-DD"
        date_to       (str)  — "YYYY-MM-DD"
        timestamp_ms  (int)  — find notifications near this exact timestamp (±30 min)
        limit         (int)  — default 10
    """
    app_name     = params.get("app_name", "")
    app_package  = params.get("app_package", "")
    keyword      = params.get("keyword", "")
    category     = params.get("category", "").lower()
    relative     = params.get("relative_date", "")
    date_str     = params.get("date", "")
    date_from    = params.get("date_from", "")
    date_to      = params.get("date_to", "")
    timestamp_ms = params.get("timestamp_ms")
    limit        = int(params.get("limit", 10))

    # Gracefully skip if table is empty
    if db.query(NotificationLog).count() == 0:
        print("[notifications_tool] No notification data in DB — skipping.")
        return []

    query = db.query(NotificationLog)

    # ── App-specific filters ────────────────────────────────────────────────
    if app_name:
        query = query.filter(NotificationLog.app_name.ilike(f"%{app_name}%"))

    if app_package:
        query = query.filter(NotificationLog.app_package == app_package)

    # ── Category filter (PRIMARY: column lookup | FALLBACK: keyword scan) ───
    #
    # Two-part OR:
    #   Part 1 — rows where category column == requested category (fast, uses index)
    #   Part 2 — rows where category IS NULL but text fields match keywords
    #             (handles records from older app versions without pre-classification)
    #
    if category and category in VALID_CATEGORIES:
        fallback_filter = _keyword_fallback_filter(category)
        if fallback_filter is not None:
            query = query.filter(
                or_(
                    NotificationLog.category == category,   # ← indexed, O(log n)
                    (
                        (NotificationLog.category == None) &  # noqa: E711
                        fallback_filter
                    ),
                )
            )
        else:
            query = query.filter(NotificationLog.category == category)

    # ── Free-text keyword search (across all text columns) ──────────────────
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                NotificationLog.title.ilike(pattern),
                NotificationLog.text.ilike(pattern),
                NotificationLog.big_text.ilike(pattern),
                NotificationLog.full_text.ilike(pattern),
            )
        )

    # ── Date / timestamp filters ────────────────────────────────────────────
    now = datetime.now()
    start_dt = end_dt = None

    if timestamp_ms:
        ts_sec   = int(timestamp_ms) / 1000
        start_ms = int((ts_sec - 1800) * 1000)
        end_ms   = int((ts_sec + 1800) * 1000)
        query = query.filter(
            NotificationLog.timestamp_ms >= start_ms,
            NotificationLog.timestamp_ms <= end_ms,
        )
    elif relative == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif relative == "yesterday":
        y = now - timedelta(days=1)
        start_dt = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = y.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif relative == "this_week":
        start_dt = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = now
    elif relative == "last_week":
        s = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
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
            end_dt   = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        except ValueError:
            pass

    if start_dt and end_dt:
        query = query.filter(
            NotificationLog.timestamp_ms >= int(start_dt.timestamp() * 1000),
            NotificationLog.timestamp_ms <= int(end_dt.timestamp() * 1000),
        )

    results = query.order_by(NotificationLog.timestamp_ms.desc()).limit(limit).all()
    return [_notif_to_dict(n) for n in results]
