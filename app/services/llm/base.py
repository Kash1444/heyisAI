from abc import ABC, abstractmethod
from typing import Type
from pydantic import BaseModel


class BaseLLMProvider(ABC):

    @abstractmethod
    def chat(
        self,
        prompt: str,
        temperature: float = 0
    ) -> str:
        """Unstructured text generation."""
        pass

    @abstractmethod
    def chat_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0
    ) -> BaseModel:
        """Structured output generation — returns a validated Pydantic instance."""
        pass