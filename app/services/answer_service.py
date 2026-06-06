# app/services/answer_service.py
#
# Takes fetched emails + user question → generates answer with Gemini.
# Always includes citations. Never makes up information.

import logging
import google.generativeai as genai
from app.core.config import settings

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.gemini_api_key)


class AnswerService:
    """
    Generates grounded answers from retrieved emails.

    The prompt design here is critical.
    We explicitly tell Gemini:
    - Only use the provided emails
    - Always cite which email you're drawing from
    - If nothing found, say so honestly
    """

    def __init__(self):
        self.model = genai.GenerativeModel(settings.gemini_model)

    def generate(
        self,
        question: str,
        emails: list[dict],
    ) -> dict:
        """
        Generate an answer with citations.

        Returns:
        - answer: the text response
        - sources: list of emails used as sources
        - has_results: whether relevant emails were found
        """
        if not emails:
            return self._no_results_response(question)

        # Build context from emails
        context = self._build_context(emails)
        prompt = self._build_prompt(question, context)

        try:
            response = self.model.generate_content(prompt)
            answer = self._extract_text(response)
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            answer = "I found relevant emails but encountered an error generating the answer. Please try again."

        sources = self._format_sources(emails)

        return {
            "answer": answer,
            "sources": sources,
            "has_results": True,
            "email_count": len(emails),
        }

    def _build_context(self, emails: list[dict]) -> str:
        """Format emails into a readable context block."""
        parts = []
        for i, email in enumerate(emails, 1):
            parts.append(
                f"[Email {i}]\n"
                f"Subject : {email['subject']}\n"
                f"From    : {email['sender']}\n"
                f"Date    : {email['date']}\n"
                f"Content : {email['body'][:1500]}\n"
            )
        return "\n---\n".join(parts)

    def _build_prompt(self, question: str, context: str) -> str:
        return f"""You are a personal Gmail AI assistant.
    Answer the user's question using ONLY the emails provided below.

    EMAILS:
    {context}

    INSTRUCTIONS:
    - Answer directly and specifically
    - Reference emails by their subject and sender naturally
    - Say "an email from Amazon titled X" NOT "Email 1"
    - Mention dates when relevant
    - Never make up information not in the emails
    - Keep the answer clear and conversational

    USER QUESTION: 
    {question}

    ANSWER:
    """

    def _no_results_response(self, question: str) -> dict:
        """Handle case where Gmail returned no results."""
        try:
            prompt = f"""The user asked: "{question}"
                A Gmail search returned no matching emails.
                Generate one short, helpful follow-up question to help narrow the search.
                Ask about: time period, sender name, or specific keywords they remember.
                One sentence only."""
            response = self.model.generate_content(prompt)
            clarification = self._extract_text(response)
        except Exception:
            clarification = (
                "I couldn't find matching emails. "
                "Could you give me more details like the sender's name "
                "or approximate date?"
            )

        return {
            "answer": clarification,
            "sources": [],
            "has_results": False,
            "email_count": 0,
        }

    def _format_sources(self, emails: list[dict]) -> list[dict]:
        """Format email list into source citations."""
        return [
            {
                "email_id": e["id"],
                "subject": e["subject"],
                "sender": e["sender"],
                "date": e["date"],
                "snippet": e["snippet"][:150],
            }
            for e in emails[:5]  # max 5 citations shown
        ]

    def _extract_text(self, response) -> str:
        """Safely extract text from Gemini response."""
        try:
            parts = [
                p.text for p in response.parts
                if hasattr(p, "text") and p.text
            ]
            return "\n".join(parts) if parts else response.candidates[0].content.parts[0].text
        except Exception:
            return "Unable to generate response."


answer_service = AnswerService()