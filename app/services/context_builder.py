# app/services/context_builder.py
#
# Merges all tool results from the Executor into a single, human-readable
# context string that the Response Generator LLM can reason over.

from typing import Any, Dict, List
from app.services.llm.schemas.execution_plan import ExecutionPlan


# ---------------------------------------------------------------------------
# Per-domain formatters
# Each formatter receives a list of result dicts and returns a formatted string.
# ---------------------------------------------------------------------------

def _format_calls(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No matching calls found."
    lines = []
    for r in records:
        name     = r.get("name") or r.get("number", "Unknown")
        dt       = r.get("datetime_str", "Unknown time")
        ctype    = r.get("call_type", "")
        dur_sec  = r.get("duration_seconds")
        dur_str  = f"{dur_sec}s" if dur_sec is not None else "N/A"
        lines.append(f"• {name} | {ctype} | {dt} | Duration: {dur_str}")
    return "\n".join(lines)


def _format_sms(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No matching SMS messages found."
    lines = []
    for r in records:
        name     = r.get("name") or r.get("number", "Unknown")
        dt       = r.get("datetime_str", "Unknown time")
        typ      = r.get("sms_type", "")
        body     = r.get("body", "")[:120]
        platform = r.get("platform") or ""
        category = r.get("category") or ""
        amount   = r.get("amount")
        status   = r.get("status") or ""
        meta = " | ".join(filter(None, [
            platform, category,
            f"₹{amount}" if amount else "",
            status,
        ]))
        line = f"• [{typ}] {name} at {dt}"
        if meta:
            line += f" [{meta}]"
        line += f": \"{body}\""
        lines.append(line)
    return "\n".join(lines)


def _format_spend_summary(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No spending data found."
    r = records[0]
    return (
        f"Platform: {r.get('platform', 'all')}\n"
        f"Category: {r.get('category', 'all')}\n"
        f"Total spent: ₹{r.get('total_amount', 0):,.2f}\n"
        f"Transactions: {r.get('transaction_count', 0)}\n"
        f"Average per transaction: ₹{r.get('avg_amount', 0):,.2f}\n"
        f"Highest single transaction: ₹{r.get('max_amount', 0):,.2f}\n"
        f"Lowest single transaction: ₹{r.get('min_amount', 0):,.2f}"
    )


def _format_category_breakdown(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No SMS category data found."
    lines = []
    for r in records:
        label  = r.get("platform") or r.get("category") or "unknown"
        count  = r.get("count", 0)
        total  = r.get("total_amount", 0)
        amount_str = f" | ₹{total:,.2f} spent" if total else ""
        lines.append(f"• {label}: {count} messages{amount_str}")
    return "\n".join(lines)


def _format_otp_history(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No OTP messages found."
    lines = []
    for r in records:
        dt       = r.get("datetime_str", "")
        platform = r.get("platform") or r.get("number", "Unknown")
        otp_code = r.get("entity_ref") or "(see body)"
        body     = r.get("body", "")[:80]
        lines.append(f"• {platform} at {dt} — OTP: {otp_code} | {body}")
    return "\n".join(lines)


def _format_sms_timeline(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No timeline data found."
    lines = []
    for r in records:
        dt     = r.get("datetime_str", "")
        status = r.get("status") or ""
        ref    = r.get("entity_ref") or ""
        body   = r.get("body", "")[:100]
        status_str = f"[{status.upper()}] " if status else ""
        ref_str    = f"Ref: {ref} | " if ref else ""
        lines.append(f"• {dt}: {status_str}{ref_str}{body}")
    return "\n".join(lines)


def _format_sms_stats(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No SMS statistics available."
    r = records[0]
    return (
        f"Total SMS: {r.get('total', 0)}\n"
        f"Inbox: {r.get('inbox', 0)} | Sent: {r.get('sent', 0)}\n"
        f"Enriched: {r.get('enriched', 0)}\n"
        f"Top sender: {r.get('top_sender', 'N/A')} ({r.get('top_sender_count', 0)} messages)\n"
        f"Top platform: {r.get('top_platform', 'N/A')} ({r.get('top_platform_count', 0)} messages)"
    )


def _format_notifications(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No matching notifications found."
    lines = []
    for r in records:
        app   = r.get("app_name") or r.get("app_package", "Unknown app")
        dt    = r.get("datetime_str", "Unknown time")
        title = r.get("title", "")
        text  = (r.get("text") or "")[:100]
        lines.append(f"• [{app}] {dt} — {title}: {text}")
    return "\n".join(lines)


def _format_app_usage(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No matching app usage sessions found."
    lines = []
    for r in records:
        app   = r.get("app_name") or r.get("app_package", "Unknown")
        start = r.get("start_str", "")
        end   = r.get("end_str", "")
        dur   = r.get("duration_minutes", 0)
        lines.append(f"• {app}: {start} → {end} ({dur} min)")
    return "\n".join(lines)


def _format_location(result: Any) -> str:
    if not result:
        return "No location data available."
    if isinstance(result, dict):
        addr = result.get("address") or f"{result.get('latitude')}, {result.get('longitude')}"
        dt   = result.get("datetime_str", "")
        acc  = result.get("accuracy_meters")
        acc_str = f" (±{acc}m)" if acc else ""
        return f"Location: {addr}{acc_str} at {dt}"
    if isinstance(result, list):
        if not result:
            return "No location data available."
        lines = []
        for r in result:
            addr = r.get("address") or f"{r.get('latitude')}, {r.get('longitude')}"
            dt   = r.get("datetime_str", "")
            lines.append(f"• {addr} at {dt}")
        return "\n".join(lines)
    return "No location data available."


# ---------------------------------------------------------------------------
# Tool → section title + formatter mapping
# ---------------------------------------------------------------------------
_TOOL_FORMAT_MAP = {
    # ── Calls ────────────────────────────────────────────────────────────────
    "search_calls":                 ("CALL LOGS",              _format_calls),
    # ── SMS ──────────────────────────────────────────────────────────────────
    "search_sms":                   ("SMS MESSAGES",           _format_sms),
    "get_sms_spend_summary":        ("SMS SPEND SUMMARY",      _format_spend_summary),
    "get_sms_category_breakdown":   ("SMS CATEGORY BREAKDOWN", _format_category_breakdown),
    "get_otp_history":              ("OTP HISTORY",            _format_otp_history),
    "get_sms_timeline":             ("SMS TIMELINE",           _format_sms_timeline),
    "get_sms_stats":                ("SMS STATISTICS",         _format_sms_stats),
    # ── Other ─────────────────────────────────────────────────────────────────
    "search_notifications":         ("NOTIFICATIONS",          _format_notifications),
    "get_app_usage":                ("APP USAGE",              _format_app_usage),
    "get_location_at_timestamp":    ("LOCATION AT CALL TIME",  _format_location),
    "get_location_range":           ("LOCATION HISTORY",       _format_location),
    "search_gmail":                 ("GMAIL",                  lambda r: "No Gmail data available." if not r else "\n".join(str(x) for x in r)),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_unified_context(plan: ExecutionPlan, results: Dict[int, Any]) -> str:
    """
    Takes the ExecutionPlan and the Executor's result map and builds
    a single, labeled context string for the Response Generator LLM.

    Each task gets a titled section. Empty results are shown with a
    friendly 'no data' note instead of being silently dropped.
    """
    sections = []

    for task in sorted(plan.tasks, key=lambda t: t.task_id):
        result      = results.get(task.task_id)
        title, fmt  = _TOOL_FORMAT_MAP.get(task.tool, (task.tool.upper(), str))

        formatted   = fmt(result) if result is not None else f"No data returned by {task.tool}."

        sections.append(
            f"=== {title} ===\n{formatted}"
        )

    if not sections:
        return "No data was retrieved."

    return "\n\n".join(sections)
