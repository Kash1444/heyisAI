from typing import Type
from pydantic import BaseModel

from app.services.llm.base import BaseLLMProvider


class StructuredLLM:
    """
    A unified facade abstraction for LLM providers.
    Directs generation request to the proper structured or unstructured method.
    """

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    def generate(
        self,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0,
    ) -> BaseModel:
        """
        Generates structured output constrained and validated by the Pydantic schema.
        Native provider schema enforcement is preferred; fallback parsing is handled automatically.
        """
        # Ensure validation through Pydantic (even native outputs are validated again in the providers)
        return self.provider.chat_structured(prompt, schema, temperature)

    def chat(self, prompt: str, temperature: float = 0) -> str:
        """
        Standard unstructured chat or text generation (e.g. final natural language response).
        """
        return self.provider.chat(prompt, temperature)
