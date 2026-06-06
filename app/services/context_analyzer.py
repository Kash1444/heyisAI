# app/services/context_analyzer.py
#
# Determines whether the current question is a follow-up
# that can be answered from memory, or a new question
# that requires a Gmail search.
#
# This decision is critical for two reasons:
# 1. Performance: memory answers are instant, Gmail search takes 3-8s
# 2. Correctness: "summarize it" without memory = wrong answer

# new import 
from app.services.llm_service import llm_service, ModelExhaustedException

# In _llm_analyze, replace:
#   response = self.model.generate_content(prompt)
#   text = response.text.strip()
# With:
#   text = llm_service.generate(prompt).strip()

import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)


# Patterns that almost always indicate follow-up questions
# Check these first before calling the LLM — saves API calls
FOLLOWUP_SIGNALS = [
    "summarize it",
    "summarize that",
    "summarize this",
    "tell me more",
    "explain it",
    "explain that",
    "who sent it",
    "who sent that",
    "when was it",
    "what was it",
    "what did it say",
    "more details",
    "elaborate",
    "expand on",
    "what about",
    "and the",
    "how about",
]


class ContextAnalyzer:
    """
    Decides how to handle each incoming question:

    CASE 1 — Pure follow-up: answer from memory only
      "Summarize it" → use last emails, no Gmail search

    CASE 2 — Contextual follow-up: memory + new search
      "Find more emails like that" → use context but also search

    CASE 3 — New question: fresh Gmail search
      "What was my last Amazon order?" → search Gmail
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.gemini_model)

    def analyze(
        self,
        current_question: str,
        conversation_history: str,
        has_previous_emails: bool,
    ) -> dict:
        """
        Analyze whether the question needs Gmail search or memory.

        Returns:
        - needs_gmail_search: bool
        - use_memory_emails: bool
        - resolved_question: the question with references resolved
          e.g. "summarize it" → "summarize the Instamart order email"
        """
        # Fast path: no history means always search Gmail
        if not conversation_history or not has_previous_emails:
            return {
                "needs_gmail_search": True,
                "use_memory_emails": False,
                "resolved_question": current_question,
            }

        # Fast path: check obvious follow-up signals first
        question_lower = current_question.lower().strip()
        is_obvious_followup = any(
            signal in question_lower
            for signal in FOLLOWUP_SIGNALS
        )

        # For obvious follow-ups, skip LLM call entirely
        if is_obvious_followup:
            logger.info(
                f"[ContextAnalyzer] Obvious follow-up detected: "
                f"'{current_question}'"
            )
            return {
                "needs_gmail_search": False,
                "use_memory_emails": True,
                "resolved_question": current_question,
            }

        # For ambiguous cases, ask the LLM to decide
        return self._llm_analyze(
            current_question,
            conversation_history,
        )

    def _llm_analyze(
        self,
        question: str,
        history: str,
    ) -> dict:
        """Use LLM to resolve ambiguous context dependencies."""

        prompt = f"""You are analyzing a conversation to decide if a question needs a new Gmail search or can be answered from conversation history.

CONVERSATION HISTORY:
{history}

CURRENT QUESTION: "{question}"

Decide:
1. Is this question referring to something already discussed? (follow-up)
2. Or is this a completely new topic requiring new Gmail search?

Respond with ONLY this JSON:
{{
  "needs_gmail_search": true or false,
  "use_memory_emails": true or false,
  "resolved_question": "rewrite the question with any pronouns resolved using context, or keep original if new topic"
}}

Rules:
- "it", "that", "this email", "the order", "that message" = follow-up, use memory
- A completely new topic, new company, new timeframe = new search
- "tell me more about X" where X was in history = follow-up"""

        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()

            # Strip markdown if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            import json
            result = json.loads(text)
            logger.info(f"[ContextAnalyzer] Decision: {result}")
            return result

        except Exception as e:
            logger.warning(f"[ContextAnalyzer] LLM analysis failed: {e}")
            # On failure, default to Gmail search — safer than wrong answer
            return {
                "needs_gmail_search": True,
                "use_memory_emails": False,
                "resolved_question": question,
            }


context_analyzer = ContextAnalyzer()