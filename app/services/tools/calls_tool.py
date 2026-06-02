# app/services/tools/calls_tool.py
#
# Wraps the existing call_query_service logic as a generic tool callable
# by the Executor. Accepts a flat params dict and returns a list of dicts.

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from rapidfuzz import fuzz, process
from app.models.call_log import CallLog


# ---------------------------------------------------------------------------
# Phone-number detection helper
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r'^[+\d][\d\s\-().]{4,}$')

def _looks_like_phone_number(s: str) -> bool:
    """Return True if the string looks like a phone number rather than a name."""
    return bool(_PHONE_RE.match(s.strip()))


# ---------------------------------------------------------------------------
# Internal helpers (adapted from call_query_service.py)
# ---------------------------------------------------------------------------

def _fuzzy_resolve_contact(db, contact_name: str) -> str:
    """Resolve a possibly-typo'd contact name against the DB using fuzzy matching."""
    all_names = [
        row[0] for row in db.query(CallLog.name).distinct().all() if row[0]
    ]
    if not all_names:
        return contact_name

    result = process.extractOne(
        contact_name, all_names, scorer=fuzz.WRatio, score_cutoff=60
    )
    if result:
        best_match, score, _ = result
        print(f"[calls_tool/fuzzy] '{contact_name}' → '{best_match}' (score: {score})")
        return best_match

    return contact_name


def _call_to_dict(call: CallLog) -> Dict[str, Any]:
    dt = datetime.fromtimestamp(call.call_timestamp / 1000)
    return {
        "name": call.name,
        "number": call.number,
        "call_type": call.call_type,
        "duration_seconds": call.duration_seconds,
        "timestamp_ms": call.call_timestamp,
        "datetime_str": dt.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _parse_flexible_dt(dt_str: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime string: {dt_str!r}")


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

def search_calls(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search call logs based on flexible params.

    Supported params:
        contact       (str)  — contact name to search
        relative_date (str)  — "today" | "yesterday" | "this_week" | "last_week"
        call_type     (str)  — "Incoming" | "Outgoing" | "Missed"
        date          (str)  — "YYYY-MM-DD"
        time_from     (str)  — "HH:MM" (24h)
        time_to       (str)  — "HH:MM" (24h)
        date_from     (str)  — "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
        date_to       (str)  — "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
        limit         (int)  — max results (default 10)
    """
    contact      = params.get("contact", "")
    relative     = params.get("relative_date", "")
    call_type    = params.get("call_type", "")
    date_str     = params.get("date", "")
    time_from    = params.get("time_from", "")
    time_to      = params.get("time_to", "")
    date_from    = params.get("date_from", "")
    date_to      = params.get("date_to", "")
    limit        = int(params.get("limit", 10))

    query = db.query(CallLog)

    # ── Contact filter ─────────────────────────────────────────────────────
    if contact:
        if _looks_like_phone_number(contact):
            # Strip spaces/dashes for a loose number match
            digits_only = re.sub(r'[\s\-().+]', '', contact)
            # Match last 7+ digits so +91-XXXXX and 0XXXXX both hit the same row
            suffix = digits_only[-7:] if len(digits_only) >= 7 else digits_only
            query = query.filter(CallLog.number.like(f"%{suffix}%"))
            print(f"[calls_tool] Phone number query — matching suffix '{suffix}'")
        else:
            resolved = _fuzzy_resolve_contact(db, contact)
            query = query.filter(CallLog.name.ilike(f"%{resolved}%"))

    # ── Call type filter ───────────────────────────────────────────────────
    if call_type:
        query = query.filter(CallLog.call_type == call_type)

    # ── Date / time range filters ──────────────────────────────────────────
    now = datetime.now()
    start_dt = end_dt = None

    if relative == "today":
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    elif relative == "yesterday":
        yesterday = now - timedelta(days=1)
        start_dt  = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt    = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

    elif relative == "this_week":
        start_dt = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_dt = now

    elif relative == "last_week":
        start_of_week = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_dt = start_of_week - timedelta(days=7)
        end_dt   = start_of_week - timedelta(seconds=1)

    elif date_str:
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d")
            if time_from:
                t = datetime.strptime(time_from, "%H:%M")
                start_dt = day.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            else:
                start_dt = day.replace(hour=0, minute=0, second=0, microsecond=0)

            if time_to:
                t = datetime.strptime(time_to, "%H:%M")
                end_dt = day.replace(hour=t.hour, minute=t.minute, second=59, microsecond=999999)
            else:
                end_dt = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError as e:
            print(f"[calls_tool] Invalid date format: {e}")

    elif date_from and date_to:
        try:
            start_dt = _parse_flexible_dt(date_from)
            end_raw  = _parse_flexible_dt(date_to)
            end_dt   = (
                end_raw.replace(hour=23, minute=59, second=59, microsecond=999999)
                if len(date_to) == 10
                else end_raw.replace(second=59, microsecond=999999)
            )
        except ValueError as e:
            print(f"[calls_tool] Invalid date_from/date_to: {e}")

    if start_dt and end_dt:
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms   = int(end_dt.timestamp() * 1000)
        query = query.filter(
            CallLog.call_timestamp >= start_ms,
            CallLog.call_timestamp <= end_ms,
        )

    results = query.order_by(CallLog.call_timestamp.desc()).limit(limit).all()
    return [_call_to_dict(c) for c in results]
