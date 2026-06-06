from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.structured_llm import StructuredLLM
from app.services.llm.providers.openai_provider import OpenAIProvider
from app.services.llm.providers.gemini_provider import GeminiProvider
from app.services.llm.providers.huggingface_provider import HuggingFaceProvider


def get_llm_provider() -> BaseLLMProvider:
    """
    Instantiates the underlying LLM provider based on environment settings.
    """
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "openai":
        return OpenAIProvider()

    if provider_name == "gemini":
        return GeminiProvider()

    if provider_name == "huggingface":
        return HuggingFaceProvider()

    raise ValueError(f"Unsupported LLM provider: {provider_name}")


def get_structured_llm() -> StructuredLLM:
    """
    Returns the unified StructuredLLM interface configured with the active provider.
    """
    return StructuredLLM(get_llm_provider())
