# app/services/intent_service.py

import json
import logging
from app.services.llm_service import llm_service, ModelExhaustedException

logger = logging.getLogger(__name__)


class IntentService:
    """
    Converts a natural language question into structured
    Gmail search parameters using LLMService.
    """

    def analyze(self, question: str) -> dict:
        prompt = f"""You are a Gmail search expert. Analyze this question and extract search parameters.

User question: "{question}"

Return ONLY a valid JSON object with these fields:
{{
  "gmail_queries": ["query1", "query2"],
  "needs_summary": true/false,
  "time_range": null,
  "topic": "short topic description",
  "max_results": 5
}}

Rules for gmail_queries:
- Generate 1-2 queries maximum
- Gmail returns results newest-first automatically
- Do NOT add time filters — let Gmail handle recency naturally
- Search by subject keywords, not sender domains
- Use broad keyword searches that match email subjects

Examples:
"last amazon order" →
  ["subject:(amazon order) OR subject:(order confirmation)",
   "amazon.in order"]

"last flipkart order" →
  ["subject:(flipkart order) OR subject:(order confirmation flipkart)"]

"last swiggy order" →
  ["subject:(swiggy) order delivered"]

"emails about flight booking" →
  ["subject:(flight booking OR ticket confirmation OR boarding pass)"]

"internship emails" →
  ["subject:(intern OR internship OR placement)"]

"emails from NASA" →
  ["from:nasa.gov", "subject:NASA"]

Return ONLY the JSON. No explanation."""

        try:
            text = llm_service.generate(prompt)

            # Strip markdown formatting if LLM returns code block
            if "```" in text:
                parts = text.split("```")
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]

            text = text.strip()

            result = json.loads(text)
            logger.info(f"Intent analyzed: {result}")
            return result

        except ModelExhaustedException:
            raise  # Let orchestrator handle retry/fallback across models

        except Exception as e:
            logger.warning(f"Intent analysis failed: {e}. Using fallback.")

            return {
                "gmail_queries": [question[:50]],
                "needs_summary": False,
                "time_range": None,
                "topic": question[:30],
                "max_results": 5,
            }


intent_service = IntentService()