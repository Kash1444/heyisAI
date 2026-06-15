# app/services/orchestrator.py

import logging

from app.services.llm_service import (
llm_service,
ModelExhaustedException,
)
from app.services.intent_service import intent_service
from app.services.live_gmail_service import live_gmail_service
from app.services.answer_service import answer_service
from app.services.conversation_memory import conversation_memory
from app.services.context_analyzer import context_analyzer

logger = logging.getLogger(__name__)

class QueryOrchestrator:

    def run(
        self,
        question: str,
        session_id: str = "default",
    ) -> dict:
        logger.info(
            f"[Orchestrator] Question: '{question}' | Session: '{session_id}'"
        )

        # Quick check — is this even an email-related question?
        if self._is_non_email_query(question):
            logger.info(
                "[Orchestrator] Non-email query detected, responding directly"
            )
            return self._handle_non_email_query(question)

        try:
            # ── Step 1: Load context ─────────────────────────────
            history = conversation_memory.get_history(session_id)
            history_string = conversation_memory.get_context_string(session_id)
            last_emails = conversation_memory.get_last_emails(session_id)
            has_previous_emails = len(last_emails) > 0

            # ── Step 2: Decide routing ───────────────────────────
            context_decision = context_analyzer.analyze(
                current_question=question,
                conversation_history=history_string,
                has_previous_emails=has_previous_emails,
            )

            needs_search = context_decision.get(
                "needs_gmail_search",
                True,
            )

            use_memory = context_decision.get(
                "use_memory_emails",
                False,
            )

            resolved_question = context_decision.get(
                "resolved_question",
                question,
            )

            logger.info(
                f"[Orchestrator] Decision — "
                f"needs_search: {needs_search}, "
                f"use_memory: {use_memory}"
            )

            # ── Step 3A: Memory-only flow ────────────────────────
            if use_memory and not needs_search:
                result = answer_service.generate_from_memory(
                    question=resolved_question,
                    memory_emails=last_emails,
                    conversation_history=history_string,
                )

                conversation_memory.add_turn(
                    session_id=session_id,
                    user_message=question,
                    assistant_response=result["answer"],
                    retrieved_emails=last_emails,
                )

                result["used_memory"] = True
                return result

            # ── Step 3B: Fresh Gmail search ──────────────────────
            intent = intent_service.analyze(resolved_question)

            gmail_queries = intent.get(
                "gmail_queries",
                [resolved_question],
            )

            gmail_queries = gmail_queries[:2]

            max_results = min(
                intent.get("max_results", 5),
                5,
            )

            logger.info(
                f"[Orchestrator] Gmail queries: {gmail_queries}"
            )

            emails = live_gmail_service.search_and_fetch(
                queries=gmail_queries,
                max_per_query=max_results,
            )

            logger.info(
                f"[Orchestrator] Fetched {len(emails)} emails"
            )

            # ── Step 4: Generate answer ──────────────────────────
            result = answer_service.generate(
                question=resolved_question,
                emails=emails,
                conversation_history=history_string,
            )

            # ── Step 5: Save memory ──────────────────────────────
            conversation_memory.add_turn(
                session_id=session_id,
                user_message=question,
                assistant_response=result["answer"],
                retrieved_emails=emails,
                gmail_queries_used=gmail_queries,
            )

            result["intent"] = intent
            result["used_memory"] = False

            return result

        except ModelExhaustedException as e:
            logger.warning(
                f"[Orchestrator] All models exhausted: {e}"
            )

            return {
                "answer": str(e),
                "sources": [],
                "has_results": False,
                "email_count": 0,
                "error_type": "model_exhausted",
            }

        except Exception as e:
            logger.exception(
                f"[Orchestrator] Unexpected error: {e}"
            )

            return {
                "answer": (
                    "Something went wrong while processing "
                    "your request. Please try again."
                ),
                "sources": [],
                "has_results": False,
                "email_count": 0,
                "error_type": "internal_error",
            }

    # ============================================================
    # NON-EMAIL QUERY DETECTION
    # ============================================================

    def _is_non_email_query(self, question: str) -> bool:

        non_email_signals = [
            "generate",
            "write code",
            "python code",
            "javascript",
            "how to code",
            "what is",
            "explain",
            "define",
            "calculate",
            "solve",
            "help me with",
            "can you make",
            "create a",
            "build a",
            "write a program",
        ]

        email_signals = [
            "email",
            "mail",
            "gmail",
            "inbox",
            "sent",
            "received",
            "sender",
            "subject",
            "message",
            "newsletter",
            "order",
            "booking",
            "confirmation",
            "invoice",
            "receipt",
            "amazon order",
            "swiggy",
            "instamart",
            "flight",
            "ticket",
            "payment",
        ]

        question_lower = question.lower()

        has_email_signal = any(
            signal in question_lower
            for signal in email_signals
        )

        has_non_email_signal = any(
            signal in question_lower
            for signal in non_email_signals
        )

        return has_non_email_signal and not has_email_signal

    def _handle_non_email_query(self, question: str) -> dict:

        try:
            answer = llm_service.generate(
                f'''

    You are a Gmail AI assistant.

    The user asked:

    "{question}"

    This does not appear to be related to the user's emails.

    Politely explain that you specialize in Gmail and email search.

    Then suggest examples such as:

    • What was my last Amazon order?
    • Show emails from LinkedIn
    • Find internship emails
    • Show flight booking confirmations

    Keep the response short and friendly.
    '''
    )

        except Exception:
            answer = (
                "I'm specialized for Gmail-related questions.\n\n"
                "Try asking:\n"
                "• What was my last Amazon order?\n"
                "• Show emails from LinkedIn\n"
                "• Find internship emails\n"
                "• Show flight booking confirmations"
            )

        return {
            "answer": answer,
            "sources": [],
            "has_results": False,
            "email_count": 0,
            "error_type": None,
        }

orchestrator = QueryOrchestrator()