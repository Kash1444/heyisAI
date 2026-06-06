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
  "time_range": "last_week" | "last_month" | "last_year" | "all_time" | null,
  "topic": "short topic description",
  "max_results": 10
}}

Rules for gmail_queries:
- Generate 1-3 Gmail search queries that would find relevant emails
- Use Gmail search operators: from:, subject:, after:, before:, has:attachment
- Order from most specific to most broad

Examples:
"last Amazon order" → ["from:amazon.com", "subject:order from:amazon"]
"internship emails" → ["subject:internship", "subject:(intern OR internship OR placement)"]
"NASA email" → ["from:nasa.gov", "subject:NASA"]

Return ONLY the JSON. No explanation.
"""

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
                "max_results": 10,
            }


intent_service = IntentService()