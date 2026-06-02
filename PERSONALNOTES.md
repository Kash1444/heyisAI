# PHASE 1: Gmail AI Assistant (Foundation)
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





# important cmds
cd C:\Users\Kash\gmail-chatbot
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
uvicorn app.main:app --reload --port 8000
http://127.0.0.1:8000/docs
http://localhost:8000/auth/login
http://localhost:8000/auth/callback
http://localhost:8000/auth/status

# +++++++++RUN+++++++++
# 1. Start the Application
cd C:\Users\Kash\gmail-chatbot

venv\Scripts\activate

uvicorn app.main:app --reload --port 8000

# 2. Start the Application
http://127.0.0.1:8000/auth/status

if false:
    then login:
        link: http://127.0.0.1:8000/auth/login

# 3.FastAPI DOCS (Swagger UI)
http://127.0.0.1:8000/docs

# 4.First Ingest Emails
#This creates a local memory layer for the assistant.

Gmail
 ↓
Fetch Emails
 ↓
Chunk Content
 ↓
Generate Embeddings
 ↓
Store in ChromaDB

# 5.RAG Search
/chat/ask

Question
 ↓
Vector Search
 ↓
Relevant Emails
 ↓
Gemini Summarization
 ↓
Answer

# 6. Demonstrate Agent Mode
/chat/conversation
or 
/chat/agent

# 7. Demo Queries

List my most recent inbox emails
Find emails from LinkedIn
Find emails from LinkedIn
Any emails about internships?