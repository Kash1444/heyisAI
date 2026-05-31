# Personal AI Memory Assistant — Gmail

An AI-powered email assistant that retrieves and reasons over Gmail 
using semantic search, RAG, and an AI agent with tool calling.

## Architecture
User Question
↓
AI Agent (Gemini) — picks the right tool
↓
MCP Tool Registry
├── search_emails_semantic  → ChromaDB vector search
├── search_emails_gmail     → Gmail API live search
├── get_email_full          → Read specific email
└── list_recent_emails      → Browse inbox
↓
Gemini generates grounded answer
↓
Response + source references

## Tech Stack

- FastAPI — async REST API
- Gemini 1.5 Flash — LLM + function calling
- ChromaDB — vector database
- sentence-transformers — local embeddings (all-MiniLM-L6-v2)
- Gmail API — OAuth 2.0 + email access
- SQLAlchemy + aiosqlite — structured storage
- Pydantic — data validation

## Setup

1. Clone the repo
2. Create virtual environment:
   python -m venv venv
   venv\Scripts\activate

3. Install dependencies:
   pip install -r requirements.txt

4. Copy and fill environment variables:
   copy .env.example .env
   # Fill in GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GEMINI_API_KEY

5. Authenticate with Gmail:
   uvicorn app.main:app --reload --port 8000
   # Visit http://localhost:8000/auth/login

6. Ingest emails:
   # POST http://localhost:8000/chat/ingest

7. Start chatting:
   # POST http://localhost:8000/chat/conversation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /auth/login | Start Gmail OAuth flow |
| GET | /auth/status | Check auth status |
| POST | /chat/ask | RAG-based question answering |
| POST | /chat/agent | Agent-based question answering |
| POST | /chat/conversation | Multi-turn chat with memory |
| POST | /chat/ingest | Index emails into ChromaDB |
| GET | /chat/stats | Vector DB statistics |
| GET | /health | Health check |
| GET | /docs | Interactive API documentation |

## Project Structure

├── api/           # FastAPI route handlers
├── agents/        # AI agent with tool calling
├── core/          # Config and settings
├── db/            # Vector store (ChromaDB)
├── mcp/           # Tool registry and definitions
├── schemas/       # Pydantic request/response models
└── services/      # Business logic
├── gmail_auth_service.py   # OAuth flow
├── gmail_service.py        # Gmail API
├── embedding_service.py    # Text → vectors
├── ingestion_service.py    # Email pipeline
├── retrieval_service.py    # Semantic search
├── rag_service.py          # RAG pipeline
└── conversation_service.py # Session memory

## Environment Variables

See `.env.example` for all required variables.
Never commit `.env` or `token.json`.