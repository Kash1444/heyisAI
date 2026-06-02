from openai import OpenAI
from typing import Type
from pydantic import BaseModel

from app.services.llm.base import BaseLLMProvider
from app.core.config import settings
from app.services.llm.parsing.prompt_parser import PydanticOutputParser
from app.services.llm.parsing.json_repair import repair_json


class OpenAIProvider(BaseLLMProvider):

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        # Using a model that supports structured outputs natively
        self.structured_model = "gpt-4o-mini"
        self.text_model = "gpt-3.5-turbo"

    def chat(
        self,
        prompt: str,
        temperature: float = 0
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.text_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    def chat_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0
    ) -> BaseModel:
        """
        Uses OpenAI's native Structured Outputs when possible.
        Falls back to prompt-based parsing if the SDK or model call fails.
        """
        try:
            # Native Structured Outputs API
            response = self.client.beta.chat.completions.parse(
                model=self.structured_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format=schema,
                temperature=temperature
            )
            parsed = response.choices[0].message.parsed
            if parsed is not None:
                return parsed
            raise ValueError("OpenAI returned empty structured response.")
        except Exception as e:
            # Fallback to prompt-based parsing with repair if native call fails
            print(f"[OpenAI] Native structured output failed or unsupported: {e}. Falling back to prompt parsing.")
            
            parser = PydanticOutputParser(schema)
            augmented_prompt = f"{prompt}\n\n{parser.get_format_instructions()}"
            
            raw_response = self.chat(augmented_prompt, temperature=temperature)
            repaired = repair_json(raw_response)
            return parser.parse(repaired)
