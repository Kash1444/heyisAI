from typing import Type
from pydantic import BaseModel
from huggingface_hub import InferenceClient

from app.services.llm.base import BaseLLMProvider
from app.core.config import settings
from app.services.llm.parsing.prompt_parser import PydanticOutputParser
from app.services.llm.parsing.json_repair import repair_json


class HuggingFaceProvider(BaseLLMProvider):

    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        self.model = "meta-llama/Llama-3.3-70B-Instruct"

        # New router-based client — replaces the deprecated api-inference endpoint
        self.client = InferenceClient(
            provider="novita",
            api_key=self.api_key,
        )

    def chat(
        self,
        prompt: str,
        temperature: float = 0.01  # ← NOTE: HF rejects temperature=0 exactly
    ) -> str:
        messages = [
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=2048,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            raise RuntimeError(
                f"HuggingFace InferenceClient error: {e}"
            ) from e

    def chat_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        temperature: float = 0.01
    ) -> BaseModel:
        """
        Uses prompt-based PydanticOutputParser with JSON repair and 1 retry.
        """
        parser = PydanticOutputParser(schema)
        augmented_prompt = f"{prompt}\n\n{parser.get_format_instructions()}"

        raw = ""
        for attempt in range(2):  # 1 initial + 1 retry
            try:
                raw = self.chat(augmented_prompt, temperature)
                repaired = repair_json(raw)
                return parser.parse(repaired)
            except Exception as e:
                if attempt == 0:
                    print(f"[HuggingFace] Attempt 1 failed: {e}. Retrying with strict instruction.")
                    # Injected a stronger system instruction to return ONLY valid JSON on retry
                    augmented_prompt = (
                        f"{prompt}\n\n"
                        "CRITICAL: Return ONLY valid, raw JSON conforming to the schema below. "
                        "Do NOT include markdown fences, explanations, preambles, or postscripts. "
                        "Do not include comments or trailing commas. Start directly with '{' and end with '}'.\n\n"
                        f"{parser.get_format_instructions()}"
                    )
                else:
                    print(f"[HuggingFace] Attempt 2 failed: {e}.")
                    raise ValueError(
                        f"HuggingFace failed to produce valid structured output for {schema.__name__} after retries.\n"
                        f"Raw LLM response was:\n{raw}\nError: {e}"
                    ) from e
