# app/main.py

import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "false"

from app.api import auth
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# ── Logging Setup ──────────────────────────────────────────────────────────
# Configure logging before anything else.
# In production this would write to files or a logging service.
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────
# This is the modern FastAPI way to handle startup + shutdown.
# Everything BEFORE yield runs on startup.
# Everything AFTER yield runs on shutdown.
# app/main.py — update your lifespan function

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    logger.info(f"Starting {settings.app_name}...")
    logger.info(f"Environment : {settings.app_env}")
    logger.info(f"Debug mode  : {settings.debug}")

    # Warm up the embedding model at startup
    # This ensures the first user request is fast
    logger.info("Warming up embedding model...")
    from app.services.embedding_service import embedding_service
    embedding_service._get_model()  # triggers lazy load now, not on first request
    logger.info("Embedding model ready.")

    # Warm up ChromaDB connection
    logger.info("Connecting to ChromaDB...")
    from app.db.vector_store import vector_store
    stats = vector_store.get_collection_stats()
    logger.info(f"ChromaDB ready — {stats['total_chunks']} chunks indexed.")

    logger.info("All systems ready. Accepting requests.")

    yield

    # ── SHUTDOWN ──
    logger.info("Shutting down... cleaning up resources.")


# ── App Factory ────────────────────────────────────────────────────────────
# This function creates and configures the FastAPI instance.
# Having it as a function (not module-level) makes testing easier later.
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Personal AI Memory Assistant — Gmail Integration",
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ────────────────────────────────────────────────────────────
    from app.api import auth, chat
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(chat.router, prefix="/chat", tags=["Chat"])

    return app

    # ── CORS Middleware ────────────────────────────────────────────────────
    # CORS = Cross-Origin Resource Sharing.
    # This allows your frontend (running on a different port) to talk
    # to your backend. In development, we allow all origins.
    # In production, you restrict this to your actual domain.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register Routers ───────────────────────────────────────────────────
    # We will import and register route modules here as we build them.
    # Example (commented out until we build them):
    # from app.api import auth, chat, emails

    # app.include_router(auth.router, prefix="/auth", tags=["auth"]) "delete this ?"
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

    # app.include_router(chat.router, prefix="/chat", tags=["chat"])

    return app


# ── App Instance ───────────────────────────────────────────────────────────
# This is what uvicorn imports to run the server.
app = create_app()


# ── Health Check ───────────────────────────────────────────────────────────
# Every production API has a health check endpoint.
# Load balancers, monitoring tools, and Docker ping this to know
# if the app is alive and ready to serve traffic.
@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "version": "0.1.0",
    }


# ── Root ───────────────────────────────────────────────────────────────────
@app.get("/", tags=["system"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
    }
