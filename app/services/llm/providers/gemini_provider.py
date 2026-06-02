import json
from google import genai
from google.genai import types
from typing import Type
from pydantic import BaseModel

from app.services.llm.base import BaseLLMProvider
from app.core.config import settings
from app.services.llm.parsing.prompt_parser import PydanticOutputParser
from app.services.llm.parsing.json_repair import repair_json


class GeminiProvider(BaseLLMProvider):

    def __init__(self):
        # The new Google GenAI SDK client instantiation
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY
        )
        self.model_name = "gemini-1.5-flash"

    def chat(
        self,
        prompt: str,
        temperature: float = 0
    ) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=4096,
            )
        )
        return response.text

    def chat_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0
    ) -> BaseModel:
        """
        Uses Gemini's native response_schema parameter for JSON schema enforcement in the new google-genai SDK.
        Falls back to prompt parsing if configuration or API fails.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                )
            )
            data = json.loads(response.text)
            return schema.model_validate(data)
        except Exception as e:
            print(f"[Gemini] Native structured output failed or unsupported: {e}. Falling back to prompt parsing.")
            
            parser = PydanticOutputParser(schema)
            augmented_prompt = f"{prompt}\n\n{parser.get_format_instructions()}"
            
            raw_response = self.chat(augmented_prompt, temperature=temperature)
            repaired = repair_json(raw_response)
            return parser.parse(repaired)
