# app/schemas/chat.py

from pydantic import BaseModel, Field
from typing import Optional

# Add these to app/schemas/chat.py

class ChatMessage(BaseModel):
    """Single chat request — just a message."""
    message: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        description="User's natural language question",
        examples=["What was my last Amazon order?"]
    )


class SourceEmail(BaseModel):
    """Email citation returned with answer."""
    email_id: str
    subject: str
    sender: str
    date: str
    snippet: str


class ChatAnswer(BaseModel):
    """Complete response from the assistant."""
    answer: str
    sources: list[SourceEmail] = []
    has_results: bool
    email_count: int = 0

class ChatRequest(BaseModel):
    """
    What the client sends when asking a question.
    
    We use Field with description because FastAPI uses
    these to generate your /docs documentation automatically.
    Good schemas = good documentation = good API.
    """
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="The user's natural language question",
        examples=["What emails did I get from Amazon last month?"]
    )
    n_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="How many email chunks to retrieve"
    )


class EmailSource(BaseModel):
    """A single email source reference returned with the answer."""
    email_id: str
    subject: str
    sender: str
    date: str
    relevance_score: float


class ChatResponse(BaseModel):
    """
    What we send back after processing a question.
    
    Always return structured responses — never raw strings.
    The frontend needs to know: was this answered from real data?
    How many sources? Where can I read the original email?
    """
    answer: str
    has_context: bool
    retrieved_count: int
    sources: list[EmailSource] = []


class IngestRequest(BaseModel):
    """Request body for triggering email ingestion."""
    max_emails: int = Field(
        default=50,
        ge=1,
        le=500,
        description="How many emails to ingest"
    )
    query: str = Field(
        default="",
        description="Optional Gmail filter query"
    )


class IngestResponse(BaseModel):
    """Result of an ingestion run."""
    total_fetched: int
    total_embedded: int
    total_failed: int
    total_chunks_in_db: int
    message: str


class StatsResponse(BaseModel):
    """Current state of the vector database."""
    total_chunks: int
    collection_name: str
    is_ready: bool
    message: str

class ToolUsed(BaseModel):
    """Records which tool the agent called and what it got."""
    tool: str
    params: dict
    result_summary: str


class AgentResponse(BaseModel):
    """Response from the AI agent endpoint."""
    answer: str
    tools_used: list[ToolUsed] = []
    question: str

#Step 11 — Conversational Memory
class ConversationTurn(BaseModel):
    """A single exchange in a conversation."""
    role: str          # "user" or "assistant"
    content: str


class ConversationRequest(BaseModel):
    """Request with conversation history for multi-turn chat."""
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: str = Field(
        default="default",
        description="Session ID to maintain conversation history"
    )
    history: list[ConversationTurn] = Field(
        default=[],
        description="Previous conversation turns for context"
    )


class ConversationResponse(BaseModel):
    """Response including updated conversation state."""
    answer: str
    session_id: str
    tools_used: list[ToolUsed] = []
    history: list[ConversationTurn] = []