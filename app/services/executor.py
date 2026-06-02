# app/services/executor.py

from typing import Any, Dict
from app.services.llm.schemas.execution_plan import ExecutionPlan
from app.services.tools.registry import TOOL_REGISTRY


# Params that act as filters — if empty/null they must be dropped,
# not passed as empty strings which tools may interpret as real filters.
_FILTER_PARAMS = {
    "relative_date", "date", "date_from", "date_to",
    "time_from", "time_to", "call_type", "sms_type",
    "contact", "keyword", "app_name", "app_package",
    "timestamp_ms",
}


def _sanitize_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Removes filter params that are empty/null so tools don't apply
    unintended filters. Non-filter params (limit, sort, etc.) are kept.
    """
    clean = {}
    for key, value in params.items():
        if key in _FILTER_PARAMS:
            # Drop the param if it's empty, null, or a blank string
            if value is None or value == "" or value == [] or value == {}:
                continue
        clean[key] = value
    return clean


def _merge_upstream_results(
    task_params: Dict[str, Any],
    upstream_results: Dict[int, Any],
    depends_on: list[int],
) -> Dict[str, Any]:
    """
    Merges results from upstream tasks into the current task's params.
    Upstream values only fill keys that are missing or empty in task_params.
    """
    merged = dict(task_params)

    for dep_id in depends_on:
        result = upstream_results.get(dep_id)
        if result is None:
            continue

        # Single-item list of dicts → treat as one record
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            result = result[0]

        if isinstance(result, dict):
            for key, value in result.items():
                if key not in merged or merged[key] in (None, "", [], {}):
                    merged[key] = value

        elif isinstance(result, list):
            merged[f"task_{dep_id}_result"] = result

    return merged


import re as _re

_PHONE_DIGITS_RE = _re.compile(r'^[+\d][\d\s\-().]{4,}$')


def _contact_is_phone(params: Dict[str, Any]) -> bool:
    """Return True if the 'contact' param looks like a phone number."""
    contact = params.get("contact", "")
    return bool(contact and _PHONE_DIGITS_RE.match(str(contact).strip()))


def _run_tool(tool_fn, db, params: Dict[str, Any]) -> Any:
    """
    Runs a tool with sanitized params.
    On empty result, retries once with all date/type filters stripped
    so recency-only queries (e.g. 'last call') always find something.

    Exception: if 'contact' is a phone number, no retry is performed —
    an empty result means the number is genuinely absent from the logs.
    """
    clean = _sanitize_params(params)
    result = tool_fn(db, clean)

    # If empty and there were date/type filters, retry without them —
    # but skip retry when searching by phone number (avoid false positives).
    if not result and not _contact_is_phone(clean):
        relaxed = {k: v for k, v in clean.items()
                   if k not in _FILTER_PARAMS or k in ("limit", "sort")}
        if relaxed != clean:
            print(f"[executor] Empty result — retrying without date/type filters.")
            result = tool_fn(db, relaxed)

    return result


def run_execution_plan(db, plan: ExecutionPlan) -> Dict[int, Any]:
    """
    Executes all tasks in the plan in task_id order.

    - Tasks with no depends_on run with their static params.
    - Tasks with depends_on receive merged params from upstream results.
    - Params are sanitized before each tool call (empty filters dropped).
    - On empty result, retries once with relaxed filters.
    - Unknown tools and exceptions are handled gracefully.

    Returns:
        Dict mapping task_id → tool result
    """
    results: Dict[int, Any] = {}
    sorted_tasks = sorted(plan.tasks, key=lambda t: t.task_id)

    for task in sorted_tasks:
        tool_fn = TOOL_REGISTRY.get(task.tool)

        if tool_fn is None:
            print(f"[executor] Unknown tool '{task.tool}' for task {task.task_id} — skipping.")
            results[task.task_id] = []
            continue

        merged_params = _merge_upstream_results(
            task.params,
            results,
            task.depends_on,
        )

        print(
            f"[executor] Running task {task.task_id}: {task.tool} "
            f"with params={merged_params}"
        )

        try:
            result = _run_tool(tool_fn, db, merged_params)
            results[task.task_id] = result
            print(
                f"[executor] Task {task.task_id} returned "
                f"{len(result) if isinstance(result, list) else 1} item(s)."
            )
        except Exception as e:
            print(f"[executor] Task {task.task_id} ({task.tool}) failed: {e}")
            results[task.task_id] = []

    return results