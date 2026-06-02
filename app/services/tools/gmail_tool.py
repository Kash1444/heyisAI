# app/services/tools/gmail_tool.py
#
# FUTURE INTEGRATION STUB — Gmail OAuth not yet implemented.
# Returns an empty list so the executor can gracefully skip this domain.

from typing import Any, Dict, List


def search_gmail(db, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Searches Gmail messages.

    Stub: returns empty list.
    Full implementation requires Gmail OAuth2 integration.

    Future params:
        query        (str) — Gmail search query string (same syntax as Gmail search bar)
        date_from    (str) — "YYYY-MM-DD"
        date_to      (str) — "YYYY-MM-DD"
        relative_date(str) — "today" | "yesterday" | "this_week" | "last_week"
        limit        (int) — max results
    """
    print("[gmail_tool] Gmail integration not yet implemented — returning empty.")
    return []
