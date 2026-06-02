# app/services/call_service.py

from datetime import datetime, timedelta
from rapidfuzz import fuzz, process
from sqlalchemy import func
from app.models.call_log import CallLog


# ===========================================================================
# CONTACT FUZZY MATCH (unchanged)
# ===========================================================================

def find_best_contact_match(db, contact_name: str) -> str:
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
        print(f"[fuzzy] '{contact_name}' → '{best_match}' (score: {score})")
        return best_match
    print(f"[fuzzy] No close match for '{contact_name}', using as-is")
    return contact_name


# ===========================================================================
# MAIN DISPATCHER
# ===========================================================================

def retrieve_call_data(db, parsed_query):
    if hasattr(parsed_query, "model_dump"):
        parsed_query = parsed_query.model_dump()

    intent       = parsed_query.get("intent", "")
    contact_name = parsed_query.get("contact_name") or ""

    # ── Recency & Volume ────────────────────────────────────────────────────
    if intent == "recent_calls":
        return db.query(CallLog).order_by(CallLog.call_timestamp.desc()).limit(10).all()

    if intent == "missed_calls":
        q = db.query(CallLog).filter(CallLog.call_type == "Missed")
        if contact_name:
            name = find_best_contact_match(db, contact_name)
            q = q.filter(CallLog.name.ilike(f"%{name}%"))
        return q.order_by(CallLog.call_timestamp.desc()).limit(10).all()

    if intent == "outgoing_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Outgoing")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "incoming_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Incoming")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "unanswered_calls":
        # Outgoing calls the other side never picked up (0-second duration)
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Outgoing", CallLog.duration_seconds == 0)
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "rejected_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Rejected")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "declined_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Declined")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "auto_rejected_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type.in_(["Auto Rejected", "DND"]))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "total_calls":
        count = db.query(func.count(CallLog.id)).scalar()
        return [{"total_calls": count}]

    if intent == "calls_by_date":
        return retrieve_calls_by_date(db, parsed_query)

    # ── Contact-Specific ────────────────────────────────────────────────────
    if intent == "contact_history":
        name = find_best_contact_match(db, contact_name)
        return (
            db.query(CallLog)
            .filter(CallLog.name.ilike(f"%{name}%"))
            .order_by(CallLog.call_timestamp.desc())
            .limit(20).all()
        )

    if intent == "contact_last_call":
        name = find_best_contact_match(db, contact_name)
        call = (
            db.query(CallLog)
            .filter(CallLog.name.ilike(f"%{name}%"))
            .order_by(CallLog.call_timestamp.desc())
            .first()
        )
        return [call] if call else []

    if intent == "contact_call_count":
        name = find_best_contact_match(db, contact_name)
        count = (
            db.query(func.count(CallLog.id))
            .filter(CallLog.name.ilike(f"%{name}%"))
            .scalar()
        )
        return [{"contact_name": name, "call_count": count}]

    if intent == "duration_by_contact":
        name = find_best_contact_match(db, contact_name)
        total = (
            db.query(func.sum(CallLog.duration_seconds))
            .filter(CallLog.name.ilike(f"%{name}%"))
            .scalar() or 0
        )
        return [{"contact_name": name, "total_duration_seconds": total}]

    if intent == "most_contacted":
        limit = parsed_query.get("limit") or 5
        rows = (
            db.query(CallLog.name, func.count(CallLog.id).label("call_count"))
            .filter(CallLog.name.isnot(None), CallLog.name != "")
            .group_by(CallLog.name)
            .order_by(func.count(CallLog.id).desc())
            .limit(limit).all()
        )
        return [{"name": r.name, "call_count": r.call_count} for r in rows]

    if intent == "least_contacted":
        limit = parsed_query.get("limit") or 5
        rows = (
            db.query(CallLog.name, func.count(CallLog.id).label("call_count"))
            .filter(CallLog.name.isnot(None), CallLog.name != "")
            .group_by(CallLog.name)
            .order_by(func.count(CallLog.id).asc())
            .limit(limit).all()
        )
        return [{"name": r.name, "call_count": r.call_count} for r in rows]

    if intent == "frequent_callers":
        limit = parsed_query.get("limit") or 5
        rows = (
            db.query(CallLog.name, func.count(CallLog.id).label("call_count"))
            .filter(CallLog.call_type == "Incoming",
                    CallLog.name.isnot(None), CallLog.name != "")
            .group_by(CallLog.name)
            .order_by(func.count(CallLog.id).desc())
            .limit(limit).all()
        )
        return [{"name": r.name, "call_count": r.call_count} for r in rows]

    if intent == "contact_rank":
        limit   = parsed_query.get("limit") or 10
        rank_by = parsed_query.get("rank_by") or "count"
        if rank_by == "duration":
            order_col = func.sum(CallLog.duration_seconds).desc()
            metric_col = func.sum(CallLog.duration_seconds).label("metric")
        elif rank_by == "recency":
            order_col = func.max(CallLog.call_timestamp).desc()
            metric_col = func.max(CallLog.call_timestamp).label("metric")
        else:
            order_col = func.count(CallLog.id).desc()
            metric_col = func.count(CallLog.id).label("metric")
        rows = (
            db.query(CallLog.name, metric_col)
            .filter(CallLog.name.isnot(None), CallLog.name != "")
            .group_by(CallLog.name)
            .order_by(order_col)
            .limit(limit).all()
        )
        return [{"name": r.name, "rank_by": rank_by, "value": r.metric} for r in rows]

    if intent == "never_called_back":
        # Missed calls with no subsequent outgoing call to same number
        missed = (
            db.query(CallLog)
            .filter(CallLog.call_type == "Missed")
            .order_by(CallLog.call_timestamp.desc())
            .all()
        )
        outgoing_numbers = {
            row[0] for row in
            db.query(CallLog.number)
            .filter(CallLog.call_type == "Outgoing")
            .all() if row[0]
        }
        return [c for c in missed if c.number not in outgoing_numbers]

    if intent == "unknown_numbers":
        return (
            db.query(CallLog)
            .filter(CallLog.name.in_(["", None, "Unknown"]))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "blocked_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Blocked")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "new_contacts":
        return (
            db.query(CallLog)
            .filter(CallLog.name.in_(["", None]))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent in ("mutual_calls", "one_sided_calls"):
        outgoing_numbers = {
            row[0] for row in db.query(CallLog.number)
            .filter(CallLog.call_type == "Outgoing").all() if row[0]
        }
        incoming_numbers = {
            row[0] for row in db.query(CallLog.number)
            .filter(CallLog.call_type == "Incoming").all() if row[0]
        }
        if intent == "mutual_calls":
            mutual = outgoing_numbers & incoming_numbers
            return db.query(CallLog).filter(CallLog.number.in_(mutual)).all()
        else:
            one_sided = outgoing_numbers.symmetric_difference(incoming_numbers)
            return db.query(CallLog).filter(CallLog.number.in_(one_sided)).all()

    # ── Duration & Stats ────────────────────────────────────────────────────
    if intent == "longest_call":
        call = db.query(CallLog).order_by(CallLog.duration_seconds.desc()).first()
        return [call] if call else []

    if intent == "shortest_call":
        call = (
            db.query(CallLog)
            .filter(CallLog.duration_seconds > 0)
            .order_by(CallLog.duration_seconds.asc())
            .first()
        )
        return [call] if call else []

    if intent == "average_call_duration":
        avg = db.query(func.avg(CallLog.duration_seconds)).scalar() or 0
        return [{"average_duration_seconds": round(avg, 2)}]

    if intent == "total_call_duration":
        total = db.query(func.sum(CallLog.duration_seconds)).scalar() or 0
        return [{"total_duration_seconds": total}]

    if intent == "calls_over_duration":
        dur_min = parsed_query.get("duration_min")
        dur_max = parsed_query.get("duration_max")
        q = db.query(CallLog)
        if dur_min is not None:
            q = q.filter(CallLog.duration_seconds >= dur_min * 60)
        if dur_max is not None:
            q = q.filter(CallLog.duration_seconds <= dur_max * 60)
        return q.order_by(CallLog.duration_seconds.desc()).limit(20).all()

    if intent == "short_calls":
        # Calls under 10 seconds — likely accidental dials
        return (
            db.query(CallLog)
            .filter(CallLog.duration_seconds > 0, CallLog.duration_seconds < 10)
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "duration_by_period":
        return retrieve_duration_by_period(db, parsed_query)

    # ── Time-Based Insights ─────────────────────────────────────────────────
    if intent == "last_call_time":
        call = db.query(CallLog).order_by(CallLog.call_timestamp.desc()).first()
        return [call] if call else []

    if intent == "first_call_time":
        call = db.query(CallLog).order_by(CallLog.call_timestamp.asc()).first()
        return [call] if call else []

    if intent == "busiest_day":
        row = (
            db.query(
                func.date(func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("day"),
                func.count(CallLog.id).label("call_count")
            )
            .group_by("day")
            .order_by(func.count(CallLog.id).desc())
            .first()
        )
        return [{"busiest_day": row.day, "call_count": row.call_count}] if row else []

    if intent == "busiest_hour":
        row = (
            db.query(
                func.strftime("%H", func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("hour"),
                func.count(CallLog.id).label("call_count")
            )
            .group_by("hour")
            .order_by(func.count(CallLog.id).desc())
            .first()
        )
        return [{"busiest_hour": row.hour, "call_count": row.call_count}] if row else []

    if intent == "quietest_period":
        row = (
            db.query(
                func.date(func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("day"),
                func.count(CallLog.id).label("call_count")
            )
            .group_by("day")
            .order_by(func.count(CallLog.id).asc())
            .first()
        )
        return [{"quietest_day": row.day, "call_count": row.call_count}] if row else []

    if intent == "weekend_calls":
        # strftime %w: 0=Sunday, 6=Saturday
        return (
            db.query(CallLog)
            .filter(
                func.strftime("%w", func.datetime(CallLog.call_timestamp / 1000, "unixepoch"))
                .in_(["0", "6"])
            )
            .order_by(CallLog.call_timestamp.desc())
            .limit(20).all()
        )

    if intent == "weekday_calls":
        return (
            db.query(CallLog)
            .filter(
                func.strftime("%w", func.datetime(CallLog.call_timestamp / 1000, "unixepoch"))
                .in_(["1", "2", "3", "4", "5"])
            )
            .order_by(CallLog.call_timestamp.desc())
            .limit(20).all()
        )

    if intent == "late_night_calls":
        # Calls between midnight and 5 AM
        return (
            db.query(CallLog)
            .filter(
                func.strftime("%H", func.datetime(CallLog.call_timestamp / 1000, "unixepoch"))
                .in_(["00", "01", "02", "03", "04"])
            )
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "call_frequency":
        return retrieve_call_frequency(db, parsed_query)

    if intent == "no_call_days":
        # Returns a count of days with no calls in the past 30 days
        return retrieve_no_call_days(db)

    if intent == "peak_call_day":
        row = (
            db.query(
                func.date(func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("day"),
                func.count(CallLog.id).label("call_count")
            )
            .group_by("day")
            .order_by(func.count(CallLog.id).desc())
            .first()
        )
        return [{"peak_day": row.day, "call_count": row.call_count}] if row else []

    if intent == "call_gap":
        name = find_best_contact_match(db, contact_name) if contact_name else None
        q = db.query(CallLog)
        if name:
            q = q.filter(CallLog.name.ilike(f"%{name}%"))
        last = q.order_by(CallLog.call_timestamp.desc()).first()
        if not last:
            return []
        gap_seconds = int(datetime.now().timestamp() - last.call_timestamp / 1000)
        return [{"last_call_timestamp": last.call_timestamp, "gap_seconds": gap_seconds}]

    # ── Search & Lookup ─────────────────────────────────────────────────────
    if intent == "search_by_number":
        number = parsed_query.get("phone_number", "")
        return (
            db.query(CallLog)
            .filter(CallLog.number.ilike(f"%{number}%"))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "search_by_keyword":
        kw = parsed_query.get("keyword", "")
        return (
            db.query(CallLog)
            .filter(
                CallLog.name.ilike(f"%{kw}%") |
                CallLog.number.ilike(f"%{kw}%")
            )
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "voicemail_calls":
        return (
            db.query(CallLog)
            .filter(CallLog.call_type == "Voicemail")
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "international_calls":
        country_code = parsed_query.get("country_code", "")
        q = db.query(CallLog).filter(CallLog.number.like("+%"))
        if country_code:
            q = q.filter(CallLog.number.like(f"{country_code}%"))
        return q.order_by(CallLog.call_timestamp.desc()).limit(10).all()

    if intent == "calls_by_location":
        area_code = parsed_query.get("area_code", "")
        return (
            db.query(CallLog)
            .filter(CallLog.number.like(f"%{area_code}%"))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "calls_by_device":
        device = parsed_query.get("device", "")
        return (
            db.query(CallLog)
            .filter(CallLog.device.ilike(f"%{device}%"))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    if intent == "calls_by_carrier":
        carrier = parsed_query.get("carrier", "")
        return (
            db.query(CallLog)
            .filter(CallLog.carrier.ilike(f"%{carrier}%"))
            .order_by(CallLog.call_timestamp.desc())
            .limit(10).all()
        )

    # ── Comparison & Trends ─────────────────────────────────────────────────
    if intent == "call_comparison":
        compare_a = parsed_query.get("compare_a", "")
        compare_b = parsed_query.get("compare_b", "")
        results_a = db.query(CallLog).filter(
            CallLog.name.ilike(f"%{compare_a}%") |
            CallLog.number.ilike(f"%{compare_a}%")
        ).all()
        results_b = db.query(CallLog).filter(
            CallLog.name.ilike(f"%{compare_b}%") |
            CallLog.number.ilike(f"%{compare_b}%")
        ).all()
        return [{
            "compare_a": compare_a, "count_a": len(results_a),
            "compare_b": compare_b, "count_b": len(results_b),
        }]

    if intent == "call_trend":
        # Returns daily call counts for the past 30 days
        since_ms = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
        rows = (
            db.query(
                func.date(func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("day"),
                func.count(CallLog.id).label("call_count")
            )
            .filter(CallLog.call_timestamp >= since_ms)
            .group_by("day")
            .order_by("day")
            .all()
        )
        return [{"day": r.day, "call_count": r.call_count} for r in rows]

    if intent == "period_over_period":
        return retrieve_period_over_period(db, parsed_query)

    # ── Data Management ─────────────────────────────────────────────────────
    if intent == "call_stats":
        total       = db.query(func.count(CallLog.id)).scalar() or 0
        total_dur   = db.query(func.sum(CallLog.duration_seconds)).scalar() or 0
        avg_dur     = db.query(func.avg(CallLog.duration_seconds)).scalar() or 0
        missed      = db.query(func.count(CallLog.id)).filter(CallLog.call_type == "Missed").scalar() or 0
        incoming    = db.query(func.count(CallLog.id)).filter(CallLog.call_type == "Incoming").scalar() or 0
        outgoing    = db.query(func.count(CallLog.id)).filter(CallLog.call_type == "Outgoing").scalar() or 0
        return [{
            "total_calls": total,
            "total_duration_seconds": total_dur,
            "average_duration_seconds": round(avg_dur, 2),
            "missed_calls": missed,
            "incoming_calls": incoming,
            "outgoing_calls": outgoing,
        }]

    if intent == "call_summary":
        return retrieve_call_summary(db)

    print(f"[call_service] Unhandled intent: '{intent}'")
    return []


# ===========================================================================
# HELPER FUNCTIONS
# ===========================================================================

def retrieve_calls_by_date(db, parsed_query):
    now = datetime.now()
    start_dt = end_dt = None
    relative = parsed_query.get("relative", "")

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
        end_dt = now

    elif relative == "last_calls":
        sow      = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        start_dt = sow - timedelta(days=7)
        end_dt   = sow - timedelta(seconds=1)

    elif relative == "this_month":
        start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now

    elif relative == "last_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_dt   = (first_this - timedelta(days=1)).replace(day=1)
        end_dt     = first_this - timedelta(seconds=1)

    elif relative == "this_year":
        start_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now

    elif relative == "last_year":
        start_dt = now.replace(year=now.year - 1, month=1, day=1,
                               hour=0, minute=0, second=0, microsecond=0)
        end_dt   = now.replace(year=now.year - 1, month=12, day=31,
                               hour=23, minute=59, second=59, microsecond=999999)

    elif parsed_query.get("date"):
        try:
            day      = datetime.strptime(parsed_query["date"], "%Y-%m-%d")
            tf, tt   = parsed_query.get("time_from"), parsed_query.get("time_to")
            start_dt = day.replace(**(_parse_hhmm(tf) if tf else
                                       {"hour": 0, "minute": 0, "second": 0, "microsecond": 0}))
            end_dt   = day.replace(**(_parse_hhmm(tt) if tt else
                                       {"hour": 23, "minute": 59, "second": 59, "microsecond": 999999}))
        except ValueError as e:
            print(f"[call_service] Date parse error: {e}")
            return []

    elif parsed_query.get("date_from") and parsed_query.get("date_to"):
        try:
            start_dt = _parse_flexible(parsed_query["date_from"])
            end_raw  = _parse_flexible(parsed_query["date_to"])
            end_dt   = (end_raw.replace(hour=23, minute=59, second=59, microsecond=999999)
                        if len(parsed_query["date_to"]) == 10 else
                        end_raw.replace(second=59, microsecond=999999))
        except ValueError as e:
            print(f"[call_service] Range parse error: {e}")
            return []

    else:
        print("[call_service] calls_by_date: no usable date info.")
        return []

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp() * 1000)

    return (
        db.query(CallLog)
        .filter(CallLog.call_timestamp >= start_ms,
                CallLog.call_timestamp <= end_ms)
        .order_by(CallLog.call_timestamp.desc())
        .all()
    )


def retrieve_duration_by_period(db, parsed_query):
    calls = retrieve_calls_by_date(db, parsed_query)
    total = sum(c.duration_seconds or 0 for c in calls)
    avg   = total / len(calls) if calls else 0
    return [{"period_call_count": len(calls),
             "total_duration_seconds": total,
             "average_duration_seconds": round(avg, 2)}]


def retrieve_call_frequency(db, parsed_query):
    granularity = parsed_query.get("granularity") or "daily"
    fmt_map = {"daily": "%Y-%m-%d", "weekly": "%Y-%W", "monthly": "%Y-%m"}
    fmt = fmt_map.get(granularity, "%Y-%m-%d")
    rows = (
        db.query(
            func.strftime(fmt, func.datetime(
                CallLog.call_timestamp / 1000, "unixepoch")).label("period"),
            func.count(CallLog.id).label("call_count")
        )
        .group_by("period")
        .order_by("period")
        .all()
    )
    return [{"period": r.period, "call_count": r.call_count} for r in rows]


def retrieve_no_call_days(db):
    since    = datetime.now() - timedelta(days=30)
    since_ms = int(since.timestamp() * 1000)
    rows = (
        db.query(
            func.date(func.datetime(CallLog.call_timestamp / 1000, "unixepoch")).label("day")
        )
        .filter(CallLog.call_timestamp >= since_ms)
        .group_by("day")
        .all()
    )
    days_with_calls = {r.day for r in rows}
    all_days = {
        (since + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)
    }
    no_call = sorted(all_days - days_with_calls)
    return [{"no_call_days": no_call, "count": len(no_call)}]


def retrieve_period_over_period(db, parsed_query):
    compare_a = parsed_query.get("compare_a", "this_week")
    compare_b = parsed_query.get("compare_b", "last_week")

    def count_for_relative(rel):
        fq = {"intent": "calls_by_date", "relative": rel}
        calls = retrieve_calls_by_date(db, fq)
        return len(calls)

    count_a = count_for_relative(compare_a)
    count_b = count_for_relative(compare_b)
    delta   = count_a - count_b
    return [{
        "period_a": compare_a, "count_a": count_a,
        "period_b": compare_b, "count_b": count_b,
        "delta": delta,
    }]


def retrieve_call_summary(db):
    total     = db.query(func.count(CallLog.id)).scalar() or 0
    total_dur = db.query(func.sum(CallLog.duration_seconds)).scalar() or 0
    last      = db.query(CallLog).order_by(CallLog.call_timestamp.desc()).first()
    top = (
        db.query(CallLog.name, func.count(CallLog.id).label("c"))
        .filter(CallLog.name.isnot(None), CallLog.name != "")
        .group_by(CallLog.name)
        .order_by(func.count(CallLog.id).desc())
        .first()
    )
    return [{
        "total_calls": total,
        "total_duration_seconds": total_dur,
        "last_call_timestamp": last.call_timestamp if last else None,
        "top_contact": top.name if top else None,
        "top_contact_calls": top.c if top else None,
    }]


# ===========================================================================
# CONTEXT BUILDER
# ===========================================================================

def build_call_context(calls) -> str:
    if not calls:
        return "No matching calls found."

    # Dict/aggregate result (e.g. from call_stats, total_calls, etc.)
    if isinstance(calls[0], dict):
        return "\n".join(
            "\n".join(f"{k}: {v}" for k, v in item.items())
            for item in calls
        )

    lines = []
    for call in calls:
        dt       = datetime.fromtimestamp(call.call_timestamp / 1000)
        duration = (
            _format_duration(call.duration_seconds)
            if call.duration_seconds is not None else "N/A"
        )
        lines.append(
            f"Name: {call.name or 'Unknown'}\n"
            f"Number: {call.number}\n"
            f"Type: {call.call_type}\n"
            f"Time: {dt.strftime('%a, %b %d %Y at %I:%M %p')}\n"
            f"Duration: {duration}"
        )
    return "\n\n".join(lines)


# ===========================================================================
# PRIVATE UTILITIES
# ===========================================================================

def _parse_hhmm(t_str: str) -> dict:
    t = datetime.strptime(t_str, "%H:%M")
    return {"hour": t.hour, "minute": t.minute, "second": 0, "microsecond": 0}


def _parse_flexible(dt_str: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {dt_str!r}")


def _format_duration(seconds: int) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds} sec"
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h} hr {m} min"
    return f"{m} min {s} sec"