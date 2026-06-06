# app/services/tools/registry.py
#
# Central mapping from tool name strings (as produced by the Planner LLM)
# to callable Python functions. The Executor imports only this module.
#
# To add a new tool:
#   1. Create a new tool file in this directory
#   2. Add an entry to TOOL_REGISTRY below
#   3. Add the tool name to the ToolName Literal in execution_plan.py

from app.services.tools import calls_tool
from app.services.tools import sms_tool
from app.services.tools import notifications_tool
from app.services.tools import app_usage_tool
from app.services.tools import location_tool
from app.services.tools import gmail_tool

# Maps the string tool names (from ExecutionPlan.tasks[].tool) → callable
TOOL_REGISTRY = {
    # ── Calls ──────────────────────────────────────────────────────────────
    "search_calls":                 calls_tool.search_calls,

    # ── SMS ────────────────────────────────────────────────────────────────
    "search_sms":                   sms_tool.search_sms,
    "get_sms_spend_summary":        sms_tool.get_sms_spend_summary,
    "get_sms_category_breakdown":   sms_tool.get_sms_category_breakdown,
    "get_otp_history":              sms_tool.get_otp_history,
    "get_sms_timeline":             sms_tool.get_sms_timeline,
    "get_sms_stats":                sms_tool.get_sms_stats,

    # ── Other domains ──────────────────────────────────────────────────────
    "search_notifications":         notifications_tool.search_notifications,
    "get_app_usage":                app_usage_tool.get_app_usage,
    "get_location_at_timestamp":    location_tool.get_location_at_timestamp,
    "get_location_range":           location_tool.get_location_range,
    "search_gmail":                 gmail_tool.search_gmail,
}

