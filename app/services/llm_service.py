# app/services/llm_service.py
#
# Multi-provider LLM service with intelligent fallback routing.

import time
import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)

# =========================
# FAILURE TRACKING SYSTEM
# =========================
_model_failures: dict[str, list[float]] = {}

EXHAUSTION_THRESHOLD = 2   # failures within window → mark unavailable
EXHAUSTION_TTL = 3600      # 1 hour cooldown


class ModelExhaustedException(Exception):
    """Raised when all providers are exhausted."""
    pass


class LLMService:

    def __init__(self):
        # ✅ NEW: tracks last successful model
        self._last_successful_model = None

    # =========================
    # MAIN ENTRY
    # =========================
    def generate(self, prompt: str) -> str:
        providers = self._get_provider_chain()

        available = [
            p for p in providers
            if not self._is_exhausted(p["name"])
        ]

        if not available:
            raise ModelExhaustedException(
                "All AI models are currently unavailable. Try again later."
            )

        for provider in available:
            try:
                logger.info(f"[LLM] Trying provider: {provider['name']}")

                result = provider["call"](prompt)

                if result:
                    logger.info(f"[LLM] Success: {provider['name']}")

                    # ✅ FIX: track successful model
                    self._last_successful_model = provider["name"]

                    return result

            except Exception as e:
                error_str = str(e).lower()

                is_rate_limit = any(x in error_str for x in [
                    "429", "quota", "rate", "limit", "exhausted",
                    "too many", "resource_exhausted"
                ])

                is_permanent = any(x in error_str for x in [
                    "decommissioned",
                    "deprecated",
                    "not found",
                    "invalid_request",
                    "no such model",
                    "model_decommissioned"
                ])

                if is_rate_limit:
                    self._record_failure(provider["name"])
                    logger.warning(
                        f"[LLM] {provider['name']} rate limited "
                        f"(failures={len(_model_failures.get(provider['name'], []))})."
                    )
                    continue

                if is_permanent:
                    self._record_failure(provider["name"])
                    self._record_failure(provider["name"])

                    logger.error(
                        f"[LLM] {provider['name']} permanent error: {e}"
                    )
                    continue

                logger.error(f"[LLM] {provider['name']} unexpected error: {e}")
                continue

        raise ModelExhaustedException(
            "All AI models are currently unavailable."
        )

    # =========================
    # PROVIDER CHAIN
    # =========================
    def _get_provider_chain(self) -> list[dict]:
        providers = [
            {
                "name": "gemini-1.5-flash",
                "call": lambda p: self._call_gemini("gemini-1.5-flash", p),
            },
            {
                "name": "gemini-1.5-pro",
                "call": lambda p: self._call_gemini("gemini-1.5-pro", p),
            },
            {
                "name": "gemini-2.0-flash",
                "call": lambda p: self._call_gemini("gemini-2.0-flash", p),
            },
        ]

        if settings.groq_api_key:
            providers.append({
                "name": "groq-llama3",
                "call": lambda p: self._call_groq(p),
            })

        return providers

    # =========================
    # GEMINI CALL
    # =========================
    def _call_gemini(self, model_name: str, prompt: str) -> str:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return self._extract_gemini_text(response)

    # =========================
    # GROQ CALL
    # =========================
    def _call_groq(self, prompt: str) -> str:
        try:
            from groq import Groq
        except ImportError:
            raise Exception("Groq package not installed. Run: pip install groq")

        client = Groq(api_key=settings.groq_api_key)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
        )

        return response.choices[0].message.content

    # =========================
    # FAILURE TRACKING
    # =========================
    def _is_exhausted(self, model_name: str) -> bool:
        now = time.time()
        failures = _model_failures.get(model_name, [])

        recent = [t for t in failures if now - t < EXHAUSTION_TTL]
        _model_failures[model_name] = recent

        return len(recent) >= EXHAUSTION_THRESHOLD

    def _record_failure(self, model_name: str):
        if model_name not in _model_failures:
            _model_failures[model_name] = []

        _model_failures[model_name].append(time.time())

    # =========================
    # RESPONSE PARSING
    # =========================
    def _extract_gemini_text(self, response) -> str:
        try:
            return "\n".join(
                p.text for p in response.parts
                if hasattr(p, "text") and p.text
            )
        except Exception:
            try:
                return response.candidates[0].content.parts[0].text
            except Exception:
                return ""

    # =========================
    # DEBUG / STATUS
    # =========================
    def reset_exhausted(self):
        _model_failures.clear()
        logger.info("[LLM] Failure tracking reset")

    def get_status(self) -> dict:
        providers = self._get_provider_chain()

        status = []
        for p in providers:
            status.append({
                "model": p["name"],
                "available": not self._is_exhausted(p["name"]),
                "recent_failures": len(_model_failures.get(p["name"], []))
            })

        available = [s for s in status if s["available"]]

        return {
            "models": status,
            # ✅ FIX: show actual last working model
            "active_model": self._last_successful_model or (
                available[0]["model"] if available else None
            ),
            "all_exhausted": len(available) == 0,
        }


# Singleton
llm_service = LLMService()