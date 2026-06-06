# app/services/intent_service.py
#
# Analyzes what the user is asking and extracts
# structured search parameters from natural language.
#
# Example:
# "emails from Amazon last month"
# → { senders: ["amazon"], date_range: "last_month", topic: "order" }

import json
import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)


class IntentService:
    """
    Converts a natural language question into structured
    Gmail search parameters.

    Why a separate service for this?
    Because intent analysis is a distinct responsibility.
    The orchestrator asks "what does the user want?"
    before asking "how do I find it?"
    These are different questions answered differently.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.gemini_model)

    def analyze(self, question: str) -> dict:
        """
        Extract search intent from user question.

        Returns a dict with:
        - gmail_queries: list of Gmail search strings to try
        - needs_summary: bool — does user want a summary?
        - time_range: detected time reference if any
        - topic: main topic keyword
        """
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
- Examples:
  "last Amazon order" → ["from:amazon.com", "subject:order from:amazon"]
  "internship emails" → ["subject:internship", "subject:(intern OR internship OR placement)"]
  "NASA email" → ["from:nasa.gov", "subject:NASA"]
  "Lenovo warranty" → ["subject:warranty from:lenovo", "subject:(warranty OR guarantee) lenovo"]

Return ONLY the JSON. No explanation."""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Strip markdown code blocks if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            logger.info(f"Intent analyzed: {result}")
            return result

        except Exception as e:
            logger.warning(f"Intent analysis failed: {e}. Using fallback.")
            # Fallback: treat entire question as search query
            return {
                "gmail_queries": [question[:50]],
                "needs_summary": False,
                "time_range": None,
                "topic": question[:30],
                "max_results": 10,
            }


intent_service = IntentService()
