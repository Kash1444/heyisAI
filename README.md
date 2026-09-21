# Personal AI Memory Assistant — Gmail

An AI-powered email assistant that retrieves and reasons over Gmail 
using semantic search, RAG, and an AI agent with tool calling.

![gmail chatbot](https://github.com/Kash1444/heyisAI/blob/8138244d9080ddc1ce1a91081e65431bb3e79d5b/chatbot%20interface%20image.png)

## Architecture
```text
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
```

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

# Demo video
https://github.com/Kash1444/gmail-chatbot/blob/0dc8e0c4c9bbffb2bd402450c9251f4e229a9cdb/Gmail-Chatbot-%20demo-video.mp4


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

```text
gmail-chatbot/
│
├── app/
│   ├── api/
│   ├── agents/
│   ├── core/
│   ├── db/
│   ├── mcp/
│   ├── schemas/
│   └── services/
│       ├── gmail_auth_service.py
│       ├── gmail_service.py
│       ├── embedding_service.py
│       ├── ingestion_service.py
│       ├── retrieval_service.py
│       ├── rag_service.py
│       └── conversation_service.py
│
├── tests/
├── chroma_db/
├── .env
├── requirements.txt
├── README.md
└── main.py
```

## Environment Variables

See `.env.example` for all required variables.
Never commit `.env` or `token.json`.
