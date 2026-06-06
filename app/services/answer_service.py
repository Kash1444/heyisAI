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

    def generate_from_memory(self, question, memory_emails, conversation_history):

        if not memory_emails:
            return {
                "answer": "I don't have previous context. Please ask a new question.",
                "sources": [],
                "has_results": False,
                "email_count": 0,
            }

        context = self._build_email_context(memory_emails)

        prompt = f"""{SYSTEM_PROMPT}

CONVERSATION HISTORY:
{conversation_history}

EMAILS:
{context}

Question: {question}

Answer:"""

        try:
            answer = llm_service.generate(prompt)

        except Exception as e:
            logger.error(f"Memory generation failed: {e}")
            answer = "Error generating response. Please try again."

        return {
            "answer": answer,
            "sources": self._format_sources(memory_emails),
            "has_results": True,
            "email_count": len(memory_emails),
            "from_memory": True,
        }

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

    def _build_email_context(self, emails):
        parts = []

        for email in emails:
            body = " ".join(email.get("body", "").split())[:2000]

            parts.append(
                f"""--- Email ---
Sender: {email.get('sender', 'unknown')}
Subject: {email.get('subject', '(no subject)')}
Date: {email.get('date', 'unknown')}
Snippet: {email.get('snippet', '')}
Body: {body}
"""
            )

        return "\n".join(parts)

    def _build_prompt(self, question, email_context, conversation_history=""):

        history_section = (
            f"CONVERSATION HISTORY:\n{conversation_history}\n\n"
            if conversation_history
            else ""
        )

        return f"""{SYSTEM_PROMPT}

{history_section}
EMAILS:
{email_context}

QUESTION: {question}

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