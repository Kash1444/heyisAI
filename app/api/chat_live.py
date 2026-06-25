# app/api/chat_live.py

import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.services.llm_service import llm_service
from app.services.orchestrator import orchestrator
from app.services.unified_orchestrator import unified_orchestrator
from app.schemas.chat import ChatMessage, ChatAnswer, SourceEmail, UnifiedChatAnswer
from app.dependencies.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=ChatAnswer)
async def chat(request: ChatMessage):
    """
    Conversational Gmail AI endpoint.
    Remembers context across turns within a session.
    """

    logger.info(f"Chat | session={request.session_id} | '{request.message}'")

    try:
        # ------------------------------------------------------------
        # TIMEOUT-GUARDED EXECUTION (30 seconds max)
        # ------------------------------------------------------------

        loop = asyncio.get_event_loop()

        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: orchestrator.run(
                    question=request.message,
                    session_id=request.session_id,
                ),
            ),
            timeout=30.0,
        )

        # ------------------------------------------------------------
        # RESPONSE BUILDING
        # ------------------------------------------------------------

        sources = [
            SourceEmail(**s)
            for s in result.get("sources", [])
        ]

        return ChatAnswer(
            answer=result["answer"],
            sources=sources,
            has_results=result["has_results"],
            email_count=result.get("email_count", 0),
        )

    # ------------------------------------------------------------
    # TIMEOUT HANDLING
    # ------------------------------------------------------------

    except asyncio.TimeoutError:
        logger.error("Chat request timed out after 30 seconds")

        raise HTTPException(
            status_code=504,
            detail="Request took too long. Please try a more specific query.",
        )

    # ------------------------------------------------------------
    # AUTH / VALIDATION ERRORS
    # ------------------------------------------------------------

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # ------------------------------------------------------------
    # GENERIC FAILURE
    # ------------------------------------------------------------

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail="Chat service error",
        )


# ─────────────────────────────────────────────────────────────
# MODEL MANAGEMENT ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.get("/model-status")
async def model_status():
    """
    Check which AI models are available and their health status.
    """
    return llm_service.get_status()


@router.post("/reset-models")
async def reset_models():
    """
    Reset exhausted model tracking (admin/debug use only).
    """
    llm_service.reset_exhausted()

    return {
        "message": "Model status reset successfully",
        "status": llm_service.get_status(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED ORCHESTRATOR ENDPOINT
# Handles Gmail + Calls + SMS + Notifications in a single request
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/unified", response_model=UnifiedChatAnswer)
async def unified_chat(
    request: ChatMessage,
    db=Depends(get_db),
):
    """
    Unified AI chat endpoint.

    Routes the user's query to the correct data domains automatically:
      - Gmail     → emails
      - Calls     → call logs
      - SMS       → text messages / OTPs / spend
      - Notifications → push notification history

    Multi-domain queries (e.g. "show my Amazon emails AND delivery SMS")
    are handled in a single request — both pipelines run in parallel.

    On partial failure (e.g. Gmail auth expired), results from healthy
    domains are still returned with a note about what failed.
    """
    logger.info(
        f"[/chat/unified] session={request.session_id} | '{request.message}'"
    )

    try:
        result = await asyncio.wait_for(
            unified_orchestrator.run(
                query=request.message,
                session_id=request.session_id,
                db=db,
            ),
            timeout=45.0,  # slightly longer than /chat since it may run 2 pipelines
        )

        # Map sources (may be SourceEmail-like dicts from Gmail)
        raw_sources = result.get("sources", [])
        sources = []
        for s in raw_sources:
            try:
                if isinstance(s, dict):
                    sources.append(SourceEmail(**s))
                elif hasattr(s, "email_id"):
                    sources.append(s)
            except Exception:
                pass  # skip malformed sources

        return UnifiedChatAnswer(
            answer=result["answer"],
            sources=sources,
            has_results=result.get("has_results", False),
            email_count=len([s for s in raw_sources]),
            domains_used=result.get("domains_used", []),
            partial_failures=result.get("partial_failures", []),
            needs_clarification=result.get("needs_clarification", False),
        )

    except asyncio.TimeoutError:
        logger.error("[/chat/unified] Request timed out after 45 seconds")
        raise HTTPException(
            status_code=504,
            detail="Request took too long. Try a more specific query.",
        )

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    except Exception as e:
        logger.error(f"[/chat/unified] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Unified chat service error",
        )