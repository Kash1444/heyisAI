import re
import json


def repair_json(text: str) -> str:
    """
    Cleans up LLM-generated JSON:
    1. Removes markdown code fences.
    2. Extracts the substring between the first '{' and the last '}'.
    3. Removes trailing commas before closing curly braces or brackets.
    """
    if not text:
        return text

    cleaned = text.strip()

    # 1. Remove markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```", "", cleaned).strip()

    # 2. Extract first JSON object block
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        cleaned = cleaned[start_idx : end_idx + 1]

    # 3. Remove trailing commas within objects or arrays, e.g., {"a": 1,} -> {"a": 1}
    # This matches a comma followed by optional whitespace and a closing bracket or brace.
    cleaned = re.sub(r",\s*([\}\])])", r"\1", cleaned)

    return cleaned
