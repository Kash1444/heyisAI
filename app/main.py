# app/main.py

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# ------------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------------

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "false"

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug Mode: {settings.debug}")

    try:
        logger.info("Warming up embedding model...")

        from app.services.embedding_service import embedding_service

        embedding_service._get_model()

        logger.info("Embedding model ready.")

    except Exception as e:
        logger.error(f"Embedding startup failed: {e}")

    try:
        logger.info("Connecting to ChromaDB...")

        from app.db.vector_store import vector_store

        stats = vector_store.get_collection_stats()

        logger.info(
            f"ChromaDB ready — {stats.get('total_chunks', 0)} chunks indexed."
        )

    except Exception as e:
        logger.error(f"ChromaDB startup failed: {e}")

    logger.info("Application ready.")

    yield

    logger.info("Shutting down...")


# ------------------------------------------------------------------
# FastAPI Factory
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# App Factory
# ------------------------------------------------------------------

def create_app() -> FastAPI:

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Personal AI Memory Assistant",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # --------------------------------------------------------------
    # CORS
    # --------------------------------------------------------------

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --------------------------------------------------------------
    # Routers
    # --------------------------------------------------------------

    from app.api import auth
    from app.api import chat_live

    logger.info("Loaded auth router")
    logger.info("Loaded chat_live router")

    app.include_router(
        auth.router,
        prefix="/auth",
        tags=["Authentication"],
    )

    app.include_router(
        chat_live.router,
        prefix="/chat",
        tags=["Chat"],
    )

    return app

# ------------------------------------------------------------------
# App Instance
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# App Instance
# ------------------------------------------------------------------

app = create_app()

# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env,
        "version": "0.1.0",
    }

# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Root
# ------------------------------------------------------------------


@app.get("/", tags=["system"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
    }