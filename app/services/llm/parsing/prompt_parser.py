import json
from typing import Type, TypeVar, Generic
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class PydanticOutputParser(Generic[T]):
    """
    A lightweight, dependency-free replacement for LangChain's PydanticOutputParser.
    Uses native Pydantic V2 JSON schema generation and validation.
    """

    def __init__(self, pydantic_object: Type[T]):
        self.pydantic_object = pydantic_object

    def get_format_instructions(self) -> str:
        # Generate the JSON schema using Pydantic V2
        schema_dict = self.pydantic_object.model_json_schema()
        
        # Strip internal schema fields that are verbose or irrelevant for standard LLMs
        schema_dict.pop("title", None)
        
        schema_json = json.dumps(schema_dict, indent=2)

        return (
            "Your response must be a single, valid JSON object matching the JSON Schema below:\n\n"
            f"```json\n{schema_json}\n```\n\n"
            "Return ONLY the JSON object. Do not include any explanations, markdown code blocks (outside of raw JSON), or other text. Ensure all fields are filled according to their types."
        )

    def parse(self, text: str) -> T:
        try:
            data = json.loads(text)
            return self.pydantic_object.model_validate(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}\nRaw output was:\n{text}") from e
        except ValidationError as e:
            raise ValueError(f"Schema validation failed: {e}\nRaw output was:\n{text}") from e
