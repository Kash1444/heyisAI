# app/api/chat.py

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

#new import
from app.agents.memory_agent import memory_agent
from app.services.rag_service import rag_service
from app.services.ingestion_service import ingestion_service
from app.db.vector_store import vector_store
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    EmailSource,
    IngestRequest,
    IngestResponse,
    StatsResponse,
    ToolUsed,
    AgentResponse,
    ConversationRequest,
    ConversationResponse,
    ConversationTurn,
)
#new import for convo memory
from app.services.conversation_service import conversation_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/conversation", response_model=ConversationResponse)
async def conversation(request: ConversationRequest):
    """
    Multi-turn conversational chat with memory.

    Maintains conversation history per session_id.
    The agent can refer to previous messages in the conversation.

    Send the same session_id across requests to maintain context.
    """
    logger.info(
        f"Conversation request | session: {request.session_id} | "
        f"question: '{request.question}'"
    )

    try:
        # Build question with conversation history as context
        contextual_question = conversation_service.build_context_prompt(
            session_id=request.session_id,
            current_question=request.question,
        )

        # Run agent with context-aware question
        result = memory_agent.run(contextual_question)
        answer = result["answer"]

        # Store this turn in session memory
        conversation_service.add_turn(
            session_id=request.session_id,
            user_message=request.question,
            assistant_message=answer,
        )

        # Return updated history so client can track state
        history = conversation_service.get_history(request.session_id)
        tools_used = [
            ToolUsed(**t) for t in result.get("tools_used", [])
        ]

        return ConversationResponse(
            answer=answer,
            session_id=request.session_id,
            tools_used=tools_used,
            history=history,
        )

    except Exception as e:
        logger.error(f"Conversation endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask", response_model=ChatResponse)
async def ask(request: ChatRequest):
    """
    Ask a question about your emails.
    
    The full RAG pipeline runs here:
    1. Embed the question
    2. Retrieve relevant email chunks
    3. Generate a grounded answer with Gemini
    4. Return answer + source references
    """
    logger.info(f"Chat request received: '{request.question}'")

    try:
        result = rag_service.answer(
            question=request.question,
            n_chunks=request.n_results,
        )

        # Convert raw source dicts to typed EmailSource objects
        sources = [
            EmailSource(**src)
            for src in result.get("sources", [])
        ]

        return ChatResponse(
            answer=result["answer"],
            has_context=result["has_context"],
            retrieved_count=result["retrieved_count"],
            sources=sources,
        )

    except ValueError as e:
        # ValueError = client sent bad input
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Unexpected error = our problem
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your question"
        )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_emails(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger email ingestion into the vector database.
    
    Why BackgroundTasks?
    Ingesting 100+ emails takes 30-60 seconds.
    If we block the HTTP request for that long, the client
    times out. BackgroundTasks lets us:
    1. Return immediately: "Ingestion started"
    2. Run ingestion in background
    
    For Phase 1 we run it synchronously (simpler to debug).
    We'll move to background later.
    """
    logger.info(
        f"Ingestion requested: {request.max_emails} emails, "
        f"query='{request.query}'"
    )

    try:
        stats = ingestion_service.ingest_emails(
            max_emails=request.max_emails,
            query=request.query,
        )

        db_stats = vector_store.get_collection_stats()

        return IngestResponse(
            total_fetched=stats.total_fetched,
            total_embedded=stats.total_embedded,
            total_failed=stats.total_failed,
            total_chunks_in_db=db_stats["total_chunks"],
            message=stats.message,
        )

    except Exception as e:
        logger.error(f"Ingestion endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Check the current state of the vector database.
    Useful for knowing if ingestion has run and how much is indexed.
    """
    try:
        db_stats = vector_store.get_collection_stats()
        total = db_stats["total_chunks"]

        return StatsResponse(
            total_chunks=total,
            collection_name=db_stats["collection_name"],
            is_ready=total > 0,
            message=(
                f"{total} chunks indexed and ready for search"
                if total > 0
                else "No emails indexed yet. POST /chat/ingest to start."
            ),
        )

    except Exception as e:
        logger.error(f"Stats endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/agent", response_model=AgentResponse)
async def agent_ask(request: ChatRequest):
    """
    Ask a question using the full AI agent.

    Unlike /ask which always uses RAG, the agent decides
    which tool to use based on the question.

    - "List my inbox" → uses list_recent_emails tool
    - "Find emails from Amazon" → uses search_emails_gmail tool  
    - "Any order confirmations?" → uses search_emails_semantic tool
    - "Read that Airtel email" → uses get_email_full tool
    """
    logger.info(f"Agent request: '{request.question}'")

    try:
        result = memory_agent.run(request.question)

        tools_used = [
            ToolUsed(**t) for t in result.get("tools_used", [])
        ]

        return AgentResponse(
            answer=result["answer"],
            tools_used=tools_used,
            question=request.question,
        )

    except Exception as e:
        logger.error(f"Agent endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Agent encountered an error"
        )