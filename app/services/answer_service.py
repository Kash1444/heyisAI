# app/services/answer_service.py
#
# Generates ChatGPT-quality responses grounded in real emails.
# The prompt engineering here is what makes answers feel natural
# instead of robotic.
#
# Key principles:
# 1. Never expose internal IDs ("Email 1", "Document 2")
# 2. Reference emails naturally ("An email from Instamart...")
# 3. Use bullet points for structured information
# 4. Acknowledge uncertainty honestly
# 5. Synthesize across multiple emails intelligently

import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)

SYSTEM_PROMPT = """You are a personal AI assistant with direct access to the user's Gmail inbox.

Your personality:
- Conversational and helpful, like ChatGPT
- Precise with dates, names, and details from emails
- Honest when information is missing or unclear
- Never robotic or overly formal

How to write responses:
- Start with a direct answer to the question
- Use bullet points (•) for lists of details, multiple items, or structured data
- Reference emails naturally: "An email from Instamart...", "Your Amazon order confirmation...", "A message sent on May 15..."
- Never say "Email 1", "Document 2", "Source 3", or any internal reference IDs
- Mention sender name/email, subject line, and date naturally in the response
- For delivery/order questions: mention order ID, date, status
- For subscription questions: list what you found across multiple emails
- For timeline questions: organize chronologically
- For summary questions: give key details in bullet points

When information is missing:
- Say "I couldn't find..." or "The email doesn't mention..."
- Suggest what the user could search for instead
- Never make up information

Remember: You are reading the user's actual emails. Be helpful, accurate, and natural."""


class AnswerService:
    """
    Generates natural, ChatGPT-quality answers from retrieved emails.
    Handles multiple answer modes: fresh answer, follow-up from memory,
    and combined context + new emails.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.gemini_model)

    def generate(
        self,
        question: str,
        emails: list[dict],
        conversation_history: str = "",
    ) -> dict:
        """
        Generate a natural answer from emails.

        Args:
            question: user's current question
            emails: retrieved emails (can be empty)
            conversation_history: previous turns for context
        """
        if not emails:
            return self._no_results_response(
                question, conversation_history
            )

        context = self._build_email_context(emails)
        prompt = self._build_prompt(
            question, context, conversation_history
        )

        try:
            response = self.model.generate_content(prompt)
            answer = self._extract_text(response)
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            answer = (
                "I found relevant emails but encountered an error. "
                "Please try again."
            )

        return {
            "answer": answer,
            "sources": self._format_sources(emails),
            "has_results": True,
            "email_count": len(emails),
        }

    def generate_from_memory(
        self,
        question: str,
        memory_emails: list[dict],
        conversation_history: str,
    ) -> dict:
        """
        Answer a follow-up question using only memory — no Gmail search.
        Used for "summarize it", "who sent it", "tell me more" etc.
        """
        logger.info("[AnswerService] Generating from memory (no Gmail search)")

        if not memory_emails:
            return {
                "answer": (
                    "I don't have previous email context to refer to. "
                    "Could you ask a specific question so I can search your Gmail?"
                ),
                "sources": [],
                "has_results": False,
                "email_count": 0,
            }

        context = self._build_email_context(memory_emails)

        prompt = f"""{SYSTEM_PROMPT}

CONVERSATION SO FAR:
{conversation_history}

EMAILS FROM PREVIOUS SEARCH:
{context}

The user is asking a follow-up question about the emails above.
Answer naturally without re-searching. Use the conversation context.

FOLLOW-UP QUESTION: {question}

ANSWER:"""

        try:
            response = self.model.generate_content(prompt)
            answer = self._extract_text(response)
        except Exception as e:
            logger.error(f"Memory generation failed: {e}")
            answer = "I encountered an error. Please try again."

        return {
            "answer": answer,
            "sources": self._format_sources(memory_emails),
            "has_results": True,
            "email_count": len(memory_emails),
            "from_memory": True,
        }

    def _build_email_context(self, emails: list[dict]) -> str:
        """
        Format emails into a rich context block.
        Include enough detail for quality answers without
        overwhelming the prompt.
        """
        parts = []
        for i, email in enumerate(emails, 1):
            # Clean up body — remove excessive whitespace
            body = " ".join(email.get("body", "").split())
            body_preview = body[:2000]

            parts.append(
                f"--- Email from {email.get('sender', 'unknown')} ---\n"
                f"Subject : {email.get('subject', '(no subject)')}\n"
                f"Date    : {email.get('date', 'unknown')}\n"
                f"Preview : {email.get('snippet', '')}\n"
                f"Content : {body_preview}\n"
            )

        return "\n".join(parts)

    def _build_prompt(
        self,
        question: str,
        email_context: str,
        conversation_history: str = "",
    ) -> str:
        """Build the full prompt with system instructions."""

        history_section = ""
        if conversation_history:
            history_section = f"""CONVERSATION HISTORY:
{conversation_history}

"""

        return f"""{SYSTEM_PROMPT}

{history_section}EMAILS FROM GMAIL:
{email_context}

USER QUESTION: {question}

ANSWER:"""

    def _no_results_response(
        self,
        question: str,
        conversation_history: str = "",
    ) -> dict:
        """Handle empty search results gracefully."""
        prompt = f"""{SYSTEM_PROMPT}

{"CONVERSATION HISTORY:" + conversation_history if conversation_history else ""}

The user asked: "{question}"
A Gmail search returned no matching emails.

Respond helpfully. Suggest:
1. What specific keywords to try
2. Whether to check a different time range
3. Whether the sender might have a different name/address

Keep it conversational and brief. One short paragraph."""

        try:
            response = self.model.generate_content(prompt)
            answer = self._extract_text(response)
        except Exception:
            answer = (
                "I couldn't find any matching emails for that query. "
                "Try being more specific — for example, mention the "
                "sender's name or an approximate date."
            )

        return {
            "answer": answer,
            "sources": [],
            "has_results": False,
            "email_count": 0,
        }

    def _format_sources(self, emails: list[dict]) -> list[dict]:
        """Format emails as clean citation objects."""
        return [
            {
                "email_id": e.get("id", ""),
                "subject": e.get("subject", ""),
                "sender": e.get("sender", ""),
                "date": e.get("date", ""),
                "snippet": e.get("snippet", "")[:150],
            }
            for e in emails[:5]
        ]

    def _extract_text(self, response) -> str:
        """Safely extract text from Gemini response."""
        try:
            parts = [
                p.text for p in response.parts
                if hasattr(p, "text") and p.text
            ]
            return "\n".join(parts) if parts else ""
        except Exception:
            try:
                return response.candidates[0].content.parts[0].text
            except Exception:
                return "Unable to generate response."


answer_service = AnswerService()