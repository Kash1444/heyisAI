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