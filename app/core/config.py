# app/core/config.py

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Central configuration for the entire application.
    All values are read from the .env file automatically.
    Pydantic validates types at startup — if something is missing
    or wrong, the app fails immediately with a clear error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ── App ────────────────────────────────────────────────
    app_name: str = Field(default="Gmail AI Assistant")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-production")

    # ── Gmail OAuth ────────────────────────────────────────
    gmail_client_id: str = Field(...)       # ... means REQUIRED
    gmail_client_secret: str = Field(...)   # must exist in .env
    gmail_redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback"
    )

    # added these two fields to the Settings class 31/5/2026
    # HuggingFace
    transformers_offline: str = Field(default="1")
    hf_datasets_offline: str = Field(default="1")

    # ── Gemini ─────────────────────────────────────────────
    gemini_api_key: str = Field(...)
    gemini_model: str = Field(default="gemini-1.5-flash")

    # ── Database ───────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./disqry.db"
    )

    # ── Vector DB ──────────────────────────────────────────
    chroma_persist_dir: str = Field(default="./chroma_db")
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2"  # small, fast, free local model
    )

    # ── Email Ingestion ────────────────────────────────────
    max_emails_to_fetch: int = Field(default=500)
    email_chunk_size: int = Field(default=1000)  # chars per chunk

    # ── LLM Provider (Atharva's multi-provider support) ───────────────
    llm_provider: str = Field(default="gemini")
    openai_api_key: Optional[str] = Field(default=None)
    huggingface_api_key: Optional[str] = Field(default=None)


# This is the singleton pattern.
# You import 'settings' everywhere — one object, always consistent.
settings = Settings()