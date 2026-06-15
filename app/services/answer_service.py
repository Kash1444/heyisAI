# app/services/answer_service.py

import logging
from app.services.llm_service import llm_service, ModelExhaustedException
from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a personal AI assistant with direct access to the user's Gmail inbox.

Your personality:
- Conversational and helpful, like ChatGPT
- Precise with dates, names, and details from emails
- Honest when information is missing or unclear
- Never robotic or overly formal

How to write responses:
- Start with a direct answer to the question
- Use bullet points (•) for lists of details
- Reference emails naturally (not "Email 1", "Source 2")
- Mention sender, subject, and date naturally
- Be accurate and grounded in real email content

When information is missing:
- Say "I couldn't find..."
- Suggest better search terms
"""


class AnswerService:

    def generate(self, question, emails, conversation_history=""):

        if not emails:
            return self._no_results_response(question, conversation_history)

        context = self._build_email_context(emails)
        prompt = self._build_prompt(question, context, conversation_history)

        try:
            answer = llm_service.generate(prompt)

        except ModelExhaustedException:
            raise

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            answer = "I found relevant emails but encountered an error. Please try again."

        return {
            "answer": answer,
            "sources": self._format_sources(emails),
            "has_results": True,
            "email_count": len(emails),
        }
    ###
    def generate_from_memory(
        self,
        question: str,
        memory_emails: list[dict],
        conversation_history: str,
    ) -> dict:
        logger.info("[AnswerService] Generating from memory (no Gmail search)")

        if not memory_emails:
            return {
                "answer": "I don't have context from a previous search. Could you re-ask your original question?",
                "sources": [],
                "has_results": False,
                "email_count": 0,
            }

        # Build context ONLY from memory emails
        context = self._build_email_context(memory_emails)

        prompt = f"""{SYSTEM_PROMPT}

    CONVERSATION SO FAR:
    {conversation_history}

    THE EMAILS FROM THE PREVIOUS SEARCH (use ONLY these):
    {context}

    CRITICAL INSTRUCTION: Answer ONLY using the emails listed above.
    Do NOT reference any other emails. Do NOT make up information.
    The user is asking a follow-up about specifically these emails.

    FOLLOW-UP QUESTION: {question}

    ANSWER:"""

        try:
            answer = llm_service.generate(prompt)
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
        ###

    def _no_results_response(self, question, conversation_history=""):

        history_section = (
            f"CONVERSATION HISTORY:\n{conversation_history}\n\n"
            if conversation_history
            else ""
        )

        prompt = f"""{SYSTEM_PROMPT}

{history_section}
The user asked: "{question}"
No emails were found.

Help the user by suggesting:
- better keywords
- sender names
- date filters

Keep response short and helpful.
"""

        try:
            answer = llm_service.generate(prompt)

        except Exception:
            answer = (
                "I couldn't find any matching emails. "
                "Try using different keywords or a sender name."
            )

        return {
            "answer": answer,
            "sources": [],
            "has_results": False,
            "email_count": 0,
        }

    def _build_email_context(self, emails: list[dict]) -> str:
        parts = []
        for email in emails:
            body = " ".join(email.get("body", "").split())
            # Reduce from 2000 to 500 chars per email
            body_preview = body[:500]

            parts.append(
                f"--- Email ---\n"
                f"Subject : {email.get('subject', '')}\n"
                f"From    : {email.get('sender', '')}\n"
                f"Date    : {email.get('date', '')}\n"
                f"Content : {body_preview}\n"
            )
        return "\n".join(parts)

    def _build_prompt(self, question: str, context: str, conversation_history: str = "") -> str:
        history_section = ""
        if conversation_history:
            history_section = f"CONVERSATION HISTORY:\n{conversation_history}\n\n"

        return f"""{SYSTEM_PROMPT}

    {history_section}EMAILS FROM GMAIL:
    {context}

    IMPORTANT INSTRUCTIONS:
    - If the user asked for "last" or "latest" and the emails found are more than 1 year old,
    mention this clearly: "The most recent order I found is from [date], which may not be your latest."
    - Suggest the user check if orders might be under a different email or sender
    - For Indian services: Amazon India uses amazon.in, Flipkart uses flipkart.com,
    Swiggy uses swiggy.in, Zomato uses zomato.com

    USER QUESTION: {question}

    ANSWER:"""

    def _format_sources(self, emails):
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


answer_service = AnswerService()