# tests/test_config.py

from app.core.config import settings


def test_settings_load():
    """Verify settings load correctly from .env"""
    print(f"App Name     : {settings.app_name}")
    print(f"Environment  : {settings.app_env}")
    print(f"Gemini Model : {settings.gemini_model}")
    print(f"Embedding    : {settings.embedding_model}")
    print(f"DB URL       : {settings.database_url}")
    print(f"Chroma Dir   : {settings.chroma_persist_dir}")

    # Security check — never print actual secrets!
    print(f"Gemini Key   : {'SET' if settings.gemini_api_key else 'MISSING'}")
    print(f"Gmail ID     : {'SET' if settings.gmail_client_id else 'MISSING'}")


if __name__ == "__main__":
    test_settings_load()
