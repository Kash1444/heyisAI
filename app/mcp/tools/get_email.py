# app/mcp/tools/get_email.py

import logging
from app.services.gmail_service import gmail_service

logger = logging.getLogger(__name__)


def get_email_full(email_id: str) -> dict:
    """
    MCP Tool: Retrieve complete content of a specific email.
    
    Use this when:
    - User wants to read a specific email in full
    - You found an email ID from search and need its content
    - User asks "what exactly did that email say?"
    """
    logger.info(f"[MCP Tool] get_email_full: {email_id}")

    try:
        email = gmail_service.get_email_full(email_id)

        if not email:
            return {
                "found": False,
                "error": f"Email {email_id} not found or inaccessible"
            }

        return {
            "found": True,
            "email_id": email.id,
            "subject": email.subject,
            "sender": email.sender,
            "recipient": email.recipient,
            "date": email.date,
            "body": email.body_text[:3000] if email.body_text else email.body_html[:3000],
            "labels": email.labels,
        }

    except Exception as e:
        logger.error(f"[MCP Tool] get_email_full failed: {e}")
        return {"found": False, "error": str(e)}


def list_recent_emails(max_results: int = 10, label: str = "INBOX") -> dict:
    """
    MCP Tool: List recent emails from a mailbox label.
    
    Use this when:
    - User wants to browse recent emails
    - User asks "what's in my inbox?"
    - You need to find an email without a specific query
    """
    logger.info(f"[MCP Tool] list_recent_emails: {max_results} from {label}")

    try:
        emails = gmail_service.list_emails(
            max_results=max_results,
            label=label,
        )

        if not emails:
            return {
                "found": False,
                "count": 0,
                "emails": [],
                "message": "No emails found"
            }

        return {
            "found": True,
            "count": len(emails),
            "emails": [
                {
                    "email_id": e.id,
                    "subject": e.subject,
                    "sender": e.sender,
                    "date": e.date,
                    "snippet": e.snippet[:150],
                }
                for e in emails
            ]
        }

    except Exception as e:
        logger.error(f"[MCP Tool] list_recent_emails failed: {e}")
        return {"found": False, "count": 0, "emails": [], "error": str(e)}