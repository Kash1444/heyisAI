PHASE 1: Gmail AI Assistant (Foundation)
│
├── Step 1 — Project skeleton (folders, configs, entry point) X
├── Step 2 — Settings and environment management X
├── Step 3 — Gmail OAuth (login, token storage, refresh) X
├── Step 4 — Gmail Service (fetch emails, search, parse) X
├── Step 5 — Email ingestion pipeline (chunk + embed + store) X
├── Step 6 — Vector database setup (ChromaDB) X
├── Step 7 — Semantic retrieval service X
├── Step 8 — RAG pipeline (retrieve + generate with Gemini) X
├── Step 9 — MCP server (expose Gmail as tools) X
├── Step 10 — AI Agent (orchestrate everything) X
└── Step 11 — Conversational chat API (final endpoint) X






cd C:\Users\Kash\gmail-chatbot
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
http://localhost:8000/auth/login
http://localhost:8000/auth/callback
http://localhost:8000/auth/status


# DM

cd C:\Users\Kash\gmail-chatbot
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Swagger UI(FAST API)
    http://localhost:8000/docs

# quick test
python -m tests.test_app

# Google OAuth
http://localhost:8000/auth/login

----------------------------------------------------------------------------------------------------------------------------------

The New Architecture — Mental Model First
OLD ARCHITECTURE (what you had)
────────────────────────────────
User asks → search ChromaDB → Gemini answers
Problem: only knows emails you manually ingested

NEW ARCHITECTURE (what we're building)
────────────────────────────────────────
User asks → LLM converts to Gmail query → 
search Gmail live → fetch relevant emails → 
Gemini answers with citations
Advantage: entire Gmail history, always fresh
The core insight is this:

Gmail's search API is already a retrieval system. You don't need to replicate it with embeddings. You need an LLM that knows how to USE it.


Complete System Design
Browser (React + Tailwind)
        │
        │  POST /chat  { message }
        ▼
FastAPI Backend
        │
        ▼
┌─────────────────────────────┐
│      Query Orchestrator     │  ← brain of the system
│                             │
│  1. Analyze user intent     │
│  2. Generate Gmail queries  │
│  3. Fetch + rank emails     │
│  4. Build context           │
│  5. Generate answer         │
└─────────────────────────────┘
        │
        ├──────────────────────────┐
        ▼                          ▼
Gmail Search Service          Gemini Service
(live API calls)              (answer generation)
        │
        ▼
Gmail API (your entire inbox)

Phase Plan — 3 Clear Phases
PHASE A — Backend Pivot (Today, 2-3 hours)
  A1. Query intent analyzer
  A2. Gmail query generator  
  A3. Live email fetcher
  A4. Context builder
  A5. New /chat endpoint

PHASE B — Frontend (Today, 2-3 hours)
  B1. React app scaffold
  B2. Google login flow
  B3. Chat interface
  B4. Source citations UI

PHASE C — Polish (Tomorrow)
  C1. Streaming responses
  C2. Conversation memory
  C3. Edge cases

New Folder Structure
Only showing what changes. Everything else stays:
gmail-chatbot/
│
├── app/
│   ├── api/
│   │   ├── auth.py          ← keep as-is
│   │   └── chat_new.py      ← NEW: replaces old chat
│   │
│   ├── services/
│   │   ├── intent_service.py      ← NEW: analyze question
│   │   ├── query_gen_service.py   ← NEW: make Gmail queries
│   │   ├── live_gmail_service.py  ← NEW: fetch live emails
│   │   ├── context_service.py     ← NEW: build LLM context
│   │   └── answer_service.py      ← NEW: Gemini answer
│   │
│   └── main.py              ← update router registration
│
└── frontend/                ← NEW: React app
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── ChatWindow.jsx
    │   │   ├── MessageBubble.jsx
    │   │   ├── SourceCard.jsx
    │   │   └── LoginPage.jsx
    │   └── api/
    │       └── client.js
    ├── package.json
    └── tailwind.config.js

# Running Everything Together

# Terminal 1 — Backend:
cd C:\Users\Kash\gmail-chatbot
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend:
cd C:\Users\Kash\gmail-chatbot\frontend\frontend
npm install
npm start