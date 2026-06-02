# app/services/tools/sms_tool.py
#
# SMS tool functions for the Executor.
# All tools use enrichment columns (category, platform, amount, etc.)
# for fast indexed DB queries instead of full-body text scans.

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz, process
from sqlalchemy import func
from app.models.sms_log import SmsLog


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _fuzzy_resolve_contact(db, contact_name: str) -> str:
    all_names = [
        row[0] for row in db.query(SmsLog.name).distinct().all() if row[0]
    ]
    if not all_names:
        return contact_name
    result = process.extractOne(contact_name, all_names, scorer=fuzz.WRatio, score_cutoff=60)
    if result:
        best, score, _ = result
        print(f"[sms_tool/fuzzy] '{contact_name}' → '{best}' (score: {score})")
        return best
    return contact_name


def _sms_to_dict(sms: SmsLog) -> Dict[str, Any]:
    dt = datetime.fromtimestamp(sms.timestamp_ms / 1000)
    return {
        "name":             sms.name,
        "number":           sms.number,
        "body":             sms.body,
        "sms_type":         sms.sms_type,
        "timestamp_ms":     sms.timestamp_ms,
        "datetime_str":     dt.strftime("%Y-%m-%d %H:%M:%S"),
        "category":         sms.category,
        "platform":         sms.platform,
        "amount":           sms.amount,
        "transaction_type": sms.transaction_type,
        "entity_ref":       sms.entity_ref,
        "status":           sms.status,
    }


def _apply_date_filters(query, relative: str, date_str: str, date_from: str, date_to: str):
    """Apply date/time range filters to a SQLAlchemy query and return it."""
    now = datetime.now()
    start_dt = end_dt = None

    if relative == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif relative == "yesterday":
        y        = now - timedelta(days=1)
        start_dt = y.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = y.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif relative == "this_week":
        start_dt = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now
    elif relative == "last_week":
        s        = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        start_dt = s - timedelta(days=7)
        end_dt   = s - timedelta(seconds=1)
    elif relative == "this_month":
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now
    elif relative == "last_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_dt   = (first_this - timedelta(days=1)).replace(day=1)
        end_dt     = first_this - timedelta(seconds=1)
    elif date_str:
        try:
            d        = datetime.strptime(date_str, "%Y-%m-%d")
            start_dt = d.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt   = d.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            pass
    elif date_from and date_to:
        try:
            start_dt = datetime.strptime(date_from, "%Y-%m-%d")
            end_dt   = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            pass

    if start_dt and end_dt:
        query = query.filter(
            SmsLog.timestamp_ms >= int(start_dt.timestamp() * 1000),
            SmsLog.timestamp_ms <= int(end_dt.timestamp() * 1000),
        )
    return query


def _check_empty(db) -> bool:
    return db.query(SmsLog.id).limit(1).scalar() is None


# ===========================================================================
# TOOL 1 — search_sms  (enhanced)
# ===========================================================================

def search_sms(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search SMS messages with rich filtering.

    Params:
        contact       (str)  — contact name or number (fuzzy matched)
        keyword       (str)  — text to search in message body
        sms_type      (str)  — "Inbox" | "Sent" | "Draft"
        category      (str)  — "bank" | "ecommerce" | "travel" | "food" |
                               "entertainment" | "otp" | "promo" | "personal" | "unknown"
        platform      (str)  — "Amazon" | "HDFC" | "Swiggy" | "IRCTC" etc.
        status        (str)  — "confirmed" | "shipped" | "delivered" | "cancelled"
        has_amount    (bool) — if True, only return SMS with a non-null amount
        relative_date (str)  — "today" | "yesterday" | "this_week" | "last_week" |
                               "this_month" | "last_month"
        date          (str)  — "YYYY-MM-DD"
        date_from     (str)  — "YYYY-MM-DD"
        date_to       (str)  — "YYYY-MM-DD"
        limit         (int)  — default 10
    """
    if _check_empty(db):
        print("[sms_tool] No SMS data in DB — skipping.")
        return []

    contact   = params.get("contact", "")
    keyword   = params.get("keyword", "")
    sms_type  = params.get("sms_type", "")
    category  = params.get("category", "")
    platform  = params.get("platform", "")
    status    = params.get("status", "")
    has_amount = params.get("has_amount", False)
    relative  = params.get("relative_date", "")
    date_str  = params.get("date", "")
    date_from = params.get("date_from", "")
    date_to   = params.get("date_to", "")
    limit     = int(params.get("limit", 10))

    query = db.query(SmsLog)

    if contact:
        resolved = _fuzzy_resolve_contact(db, contact)
        query = query.filter(
            (SmsLog.name.ilike(f"%{resolved}%")) | (SmsLog.number.ilike(f"%{contact}%"))
        )
    if keyword:
        query = query.filter(SmsLog.body.ilike(f"%{keyword}%"))
    if sms_type:
        query = query.filter(SmsLog.sms_type == sms_type)
    if category:
        query = query.filter(SmsLog.category == category.lower())
    if platform:
        query = query.filter(SmsLog.platform.ilike(f"%{platform}%"))
    if status:
        query = query.filter(SmsLog.status == status.lower())
    if has_amount:
        query = query.filter(SmsLog.amount.isnot(None))

    query = _apply_date_filters(query, relative, date_str, date_from, date_to)

    results = query.order_by(SmsLog.timestamp_ms.desc()).limit(limit).all()
    return [_sms_to_dict(s) for s in results]


# ===========================================================================
# TOOL 2 — get_sms_spend_summary
# ===========================================================================

def get_sms_spend_summary(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Aggregate spending extracted from bank/transaction SMS.

    Params:
        platform      (str)  — filter by platform (e.g. "Swiggy", "Amazon")
        category      (str)  — filter by category (e.g. "food", "ecommerce", "bank")
        transaction_type (str) — "debit" | "credit" | "refund"
        relative_date (str)
        date_from, date_to (str)

    Returns: { total_amount, transaction_count, avg_amount, max_amount, min_amount, platform, category }
    """
    if _check_empty(db):
        return []

    platform         = params.get("platform", "")
    category         = params.get("category", "")
    transaction_type = params.get("transaction_type", "")
    relative         = params.get("relative_date", "")
    date_from        = params.get("date_from", "")
    date_to          = params.get("date_to", "")

    query = db.query(SmsLog).filter(SmsLog.amount.isnot(None))

    if platform:
        query = query.filter(SmsLog.platform.ilike(f"%{platform}%"))
    if category:
        query = query.filter(SmsLog.category == category.lower())
    if transaction_type:
        query = query.filter(SmsLog.transaction_type == transaction_type.lower())

    query = _apply_date_filters(query, relative, "", date_from, date_to)

    rows = query.all()
    if not rows:
        return [{"total_amount": 0, "transaction_count": 0, "avg_amount": 0,
                 "platform": platform or "all", "category": category or "all"}]

    amounts = [r.amount for r in rows if r.amount is not None]
    return [{
        "total_amount":      round(sum(amounts), 2),
        "transaction_count": len(amounts),
        "avg_amount":        round(sum(amounts) / len(amounts), 2) if amounts else 0,
        "max_amount":        max(amounts) if amounts else 0,
        "min_amount":        min(amounts) if amounts else 0,
        "platform":          platform or "all",
        "category":          category or "all",
        "transaction_type":  transaction_type or "all",
    }]


# ===========================================================================
# TOOL 3 — get_sms_category_breakdown
# ===========================================================================

def get_sms_category_breakdown(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns count and total spend per category (or per platform within a category).

    Params:
        relative_date (str)
        date_from, date_to (str)
        group_by (str) — "category" (default) | "platform"
    """
    if _check_empty(db):
        return []

    relative  = params.get("relative_date", "")
    date_from = params.get("date_from", "")
    date_to   = params.get("date_to", "")
    group_by  = params.get("group_by", "category")

    query = db.query(SmsLog)
    query = _apply_date_filters(query, relative, "", date_from, date_to)

    if group_by == "platform":
        rows = (
            query
            .filter(SmsLog.platform.isnot(None))
            .with_entities(
                SmsLog.platform,
                func.count(SmsLog.id).label("count"),
                func.sum(SmsLog.amount).label("total_amount"),
            )
            .group_by(SmsLog.platform)
            .order_by(func.count(SmsLog.id).desc())
            .all()
        )
        return [{"platform": r.platform, "count": r.count,
                 "total_amount": round(r.total_amount or 0, 2)} for r in rows]
    else:
        rows = (
            query
            .with_entities(
                SmsLog.category,
                func.count(SmsLog.id).label("count"),
                func.sum(SmsLog.amount).label("total_amount"),
            )
            .group_by(SmsLog.category)
            .order_by(func.count(SmsLog.id).desc())
            .all()
        )
        return [{"category": r.category or "unknown", "count": r.count,
                 "total_amount": round(r.total_amount or 0, 2)} for r in rows]


# ===========================================================================
# TOOL 4 — get_otp_history
# ===========================================================================

def get_otp_history(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch recent OTP messages.

    Params:
        platform      (str)  — filter by platform/sender (e.g. "HDFC")
        relative_date (str)
        date, date_from, date_to (str)
        limit         (int)  — default 10
    """
    if _check_empty(db):
        return []

    platform  = params.get("platform", "")
    relative  = params.get("relative_date", "")
    date_str  = params.get("date", "")
    date_from = params.get("date_from", "")
    date_to   = params.get("date_to", "")
    limit     = int(params.get("limit", 10))

    query = db.query(SmsLog).filter(SmsLog.category == "otp")
    if platform:
        query = query.filter(SmsLog.platform.ilike(f"%{platform}%"))
    query = _apply_date_filters(query, relative, date_str, date_from, date_to)

    results = query.order_by(SmsLog.timestamp_ms.desc()).limit(limit).all()
    return [_sms_to_dict(s) for s in results]


# ===========================================================================
# TOOL 5 — get_sms_timeline
# ===========================================================================

def get_sms_timeline(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns an ordered timeline of all SMS from a specific platform/order — useful
    for tracking a delivery, booking, or transaction chain.

    Params:
        platform      (str)  — required — e.g. "Amazon", "IRCTC", "Swiggy"
        entity_ref    (str)  — optional — specific order ID / PNR to filter on
        relative_date (str)
        date_from, date_to (str)
        limit         (int)  — default 20
    """
    if _check_empty(db):
        return []

    platform   = params.get("platform", "")
    entity_ref = params.get("entity_ref", "")
    relative   = params.get("relative_date", "")
    date_from  = params.get("date_from", "")
    date_to    = params.get("date_to", "")
    limit      = int(params.get("limit", 20))

    query = db.query(SmsLog)
    if platform:
        query = query.filter(SmsLog.platform.ilike(f"%{platform}%"))
    if entity_ref:
        query = query.filter(SmsLog.entity_ref.ilike(f"%{entity_ref}%"))
    query = _apply_date_filters(query, relative, "", date_from, date_to)

    # Ascending order for timeline readability
    results = query.order_by(SmsLog.timestamp_ms.asc()).limit(limit).all()
    return [_sms_to_dict(s) for s in results]


# ===========================================================================
# TOOL 6 — get_sms_stats
# ===========================================================================

def get_sms_stats(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    General SMS statistics.

    Params:
        relative_date (str)
        date_from, date_to (str)

    Returns: total counts, by type, by category, busiest sender
    """
    if _check_empty(db):
        return [{"total": 0}]

    relative  = params.get("relative_date", "")
    date_from = params.get("date_from", "")
    date_to   = params.get("date_to", "")

    base = db.query(SmsLog)
    base = _apply_date_filters(base, relative, "", date_from, date_to)

    total    = base.count()
    inbox    = base.filter(SmsLog.sms_type == "Inbox").count()
    sent     = base.filter(SmsLog.sms_type == "Sent").count()
    enriched = base.filter(SmsLog.enriched == True).count()   # noqa: E712

    # Top sender
    top_sender = (
        base.with_entities(SmsLog.number, func.count(SmsLog.id).label("c"))
        .group_by(SmsLog.number)
        .order_by(func.count(SmsLog.id).desc())
        .first()
    )

    # Top platform
    top_platform = (
        base.filter(SmsLog.platform.isnot(None))
        .with_entities(SmsLog.platform, func.count(SmsLog.id).label("c"))
        .group_by(SmsLog.platform)
        .order_by(func.count(SmsLog.id).desc())
        .first()
    )

    return [{
        "total":            total,
        "inbox":            inbox,
        "sent":             sent,
        "enriched":         enriched,
        "top_sender":       top_sender.number if top_sender else None,
        "top_sender_count": top_sender.c if top_sender else 0,
        "top_platform":     top_platform.platform if top_platform else None,
        "top_platform_count": top_platform.c if top_platform else 0,
    }]
