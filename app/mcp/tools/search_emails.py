# app/mcp/tools/search_emails.py

import logging
from app.services.gmail_service import gmail_service
from app.services.retrieval_service import retrieval_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


def search_emails_semantic(query: str, n_results: int = 5) -> dict:
    """
    MCP Tool: Search emails by semantic meaning.
    
    Use this when the user asks about a topic, concept, or 
    situation — not an exact keyword.
    
    Examples:
    - "train ticket booking"
    - "order confirmation"
    - "password reset"
    """
    logger.info(f"[MCP Tool] search_emails_semantic: '{query}'")

    try:
        query_embedding = embedding_service.embed_text(query)
        chunks = retrieval_service.retrieve(
            question=query,
            n_results=n_results,
        )
        chunks = retrieval_service.deduplicate_by_email(chunks)

        if not chunks:
            return {
                "found": False,
                "count": 0,
                "results": [],
                "message": "No matching emails found in indexed data"
            }

        results = [
            {
                "email_id": c.email_id,
                "subject": c.subject,
                "sender": c.sender,
                "date": c.date,
                "relevance": c.similarity_score,
                "preview": c.text[:200],
            }
            for c in chunks
        ]

        return {
            "found": True,
            "count": len(results),
            "results": results,
            "message": f"Found {len(results)} relevant emails"
        }

    except Exception as e:
        logger.error(f"[MCP Tool] search_emails_semantic failed: {e}")
        return {"found": False, "count": 0, "results": [], "error": str(e)}


def search_emails_gmail(query: str, max_results: int = 10) -> dict:
    """
    MCP Tool: Search Gmail directly using Gmail's search syntax.
    
    Use this for precise, keyword-based searches or when the
    user specifies exact criteria like sender, date, or label.
    
    Examples:
    - "from:zerodha.com"
    - "subject:OTP after:2026/05/01"
    - "has:attachment filename:pdf"
    """
    logger.info(f"[MCP Tool] search_emails_gmail: '{query}'")

    try:
        emails = gmail_service.search_emails(
            query=query,
            max_results=max_results,
        )

        if not emails:
            return {
                "found": False,
                "count": 0,
                "results": [],
                "message": "No emails found matching Gmail query"
            }

        results = [
            {
                "email_id": e.id,
                "subject": e.subject,
                "sender": e.sender,
                "date": e.date,
                "snippet": e.snippet,
            }
            for e in emails
        ]

        return {
            "found": True,
            "count": len(results),
            "results": results,
            "message": f"Found {len(results)} emails"
        }

    except Exception as e:
        logger.error(f"[MCP Tool] search_emails_gmail failed: {e}")
        return {"found": False, "count": 0, "results": [], "error": str(e)}