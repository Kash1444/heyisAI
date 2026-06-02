# app/main.py

import os
import logging
from contextlib import asynccontextmanager
from app.api import auth, chat_atharva
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

# ------------------------------------------------------------------
# Environment
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

    logger.info("Application shutting down...")

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

    # Authentication
    try:
        from app.api import auth

        app.include_router(
            auth.router,
            prefix="/auth",
            tags=["Authentication"]
        )

        logger.info("Loaded auth router")

    except Exception as e:
        logger.error(f"Failed loading auth router: {e}")

    # Atharva APIs
    try:
        from app.api import (
            call_sync,
            sms_sync,
            location_sync,
            notification_sync,
            app_usage_sync,
            chat_atharva,
        )

        app.include_router(
            call_sync.router,
            prefix="/sync/calls",
            tags=["Sync - Calls"]
        )

        app.include_router(
            sms_sync.router,
            prefix="/sync/sms",
            tags=["Sync - SMS"]
        )

        app.include_router(
            location_sync.router,
            prefix="/sync/location",
            tags=["Sync - Location"]
        )

        app.include_router(
            notification_sync.router,
            prefix="/sync/notifications",
            tags=["Sync - Notifications"]
        )

        app.include_router(
            app_usage_sync.router,
            prefix="/sync/app-usage",
            tags=["Sync - App Usage"]
        )

        app.include_router(
            chat_atharva.router,
            prefix="/query",
            tags=["Query Engine"]
        )
        

        logger.info("Loaded Atharva routers")

    except Exception as e:
        logger.error(f"Failed loading Atharva routers: {e}")

    return app

# ------------------------------------------------------------------
# App Instance
# ------------------------------------------------------------------

app = create_app()

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

@app.get("/", tags=["system"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
    }