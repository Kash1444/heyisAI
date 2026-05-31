# app/mcp/gmail_mcp_server.py

"""
MCP Tool Registry for Gmail.

This file defines the tools available to the AI agent.
Each tool has:
- name: how the AI refers to it
- description: what the AI reads to decide when to use it
- parameters: what inputs the tool accepts
- function: the actual Python function to call

The descriptions are CRITICAL — the AI model reads them
to decide which tool to call. Write them like documentation
for a very smart engineer who has never seen your codebase.
"""

from app.mcp.tools.search_emails import (
    search_emails_semantic,
    search_emails_gmail,
)
from app.mcp.tools.get_email import (
    get_email_full,
    list_recent_emails,
)


# Tool registry — the agent reads this to know what's available
GMAIL_TOOLS = [
    {
        "name": "search_emails_semantic",
        "description": (
            "Search the user's emails by semantic meaning and topic. "
            "Use this for conceptual queries like 'train ticket booking', "
            "'order confirmation', 'job offer', 'bank statement'. "
            "Returns the most relevant emails from indexed data."
        ),
        "parameters": {
            "query": {
                "type": "string",
                "description": "Topic or concept to search for"
            },
            "n_results": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
                "default": 5
            }
        },
        "function": search_emails_semantic,
    },
    {
        "name": "search_emails_gmail",
        "description": (
            "Search Gmail directly using Gmail search syntax. "
            "Use this when the user specifies a sender, date range, "
            "or exact keywords. "
            "Examples: 'from:amazon.com', 'subject:OTP', "
            "'after:2026/01/01 from:zerodha'"
        ),
        "parameters": {
            "query": {
                "type": "string",
                "description": "Gmail search query string"
            },
            "max_results": {
                "type": "integer",
                "description": "Max emails to return (default 10)",
                "default": 10
            }
        },
        "function": search_emails_gmail,
    },
    {
        "name": "get_email_full",
        "description": (
            "Retrieve the complete content of a specific email by its ID. "
            "Use this after finding an email ID from search results, "
            "when the user wants to read the full email content."
        ),
        "parameters": {
            "email_id": {
                "type": "string",
                "description": "The Gmail email ID to retrieve"
            }
        },
        "function": get_email_full,
    },
    {
        "name": "list_recent_emails",
        "description": (
            "List the most recent emails from the user's inbox. "
            "Use this when the user wants to browse recent emails "
            "without a specific search query."
        ),
        "parameters": {
            "max_results": {
                "type": "integer",
                "description": "How many recent emails to list (default 10)",
                "default": 10
            },
            "label": {
                "type": "string",
                "description": "Gmail label to list from (default INBOX)",
                "default": "INBOX"
            }
        },
        "function": list_recent_emails,
    },
]


def get_tool_by_name(name: str) -> dict | None:
    """Look up a tool by name from the registry."""
    for tool in GMAIL_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def execute_tool(name: str, parameters: dict) -> dict:
    """
    Execute a tool from the registry by name.
    Coerces parameter types to match what the tool expects.
    """
    tool = get_tool_by_name(name)

    if not tool:
        return {
            "error": f"Tool '{name}' not found",
            "available_tools": [t["name"] for t in GMAIL_TOOLS]
        }

    try:
        # Coerce types — Gemini sometimes returns floats for integers
        coerced_params = {}
        for param_name, value in parameters.items():
            expected_type = tool["parameters"].get(param_name, {}).get("type")
            if expected_type == "integer" and isinstance(value, float):
                coerced_params[param_name] = int(value)
            else:
                coerced_params[param_name] = value

        result = tool["function"](**coerced_params)
        return result

    except TypeError as e:
        return {"error": f"Invalid parameters for tool '{name}': {e}"}
    except Exception as e:
        return {"error": f"Tool '{name}' execution failed: {e}"}