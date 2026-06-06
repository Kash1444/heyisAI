# app/api/chat_live.py

import logging
from fastapi import APIRouter, HTTPException
from app.services.orchestrator import orchestrator
from app.schemas.chat import ChatMessage, ChatAnswer, SourceEmail

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
        result = orchestrator.run(
            question=request.message,
            session_id=request.session_id,
        )

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

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Chat error")