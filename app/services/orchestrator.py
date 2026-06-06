# app/services/orchestrator.py
#
# Central coordinator for all chat queries.
# Now handles both new questions AND follow-up questions.
#
# Decision flow:
#
#   Has conversation history?
#   ├── NO  → search Gmail → answer → store in memory
#   └── YES → analyze context
#             ├── Follow-up → use memory emails → answer
#             └── New topic → search Gmail → answer → update memory

import logging
from app.services.intent_service import intent_service
from app.services.live_gmail_service import live_gmail_service
from app.services.answer_service import answer_service
from app.services.conversation_memory import conversation_memory
from app.services.context_analyzer import context_analyzer

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """
    Routes each question to the right handler:
    - Follow-up questions → memory
    - New questions → Gmail search
    - Combines both when needed
    """

    def run(
        self,
        question: str,
        session_id: str = "default",
    ) -> dict:
        logger.info(
            f"[Orchestrator] Question: '{question}' | "
            f"Session: '{session_id}'"
        )

        # Get existing conversation context
        history = conversation_memory.get_history(session_id)
        history_string = conversation_memory.get_context_string(session_id)
        last_emails = conversation_memory.get_last_emails(session_id)
        has_previous_emails = len(last_emails) > 0

        # ── Step 1: Decide how to handle this question ────────────────────
        context_decision = context_analyzer.analyze(
            current_question=question,
            conversation_history=history_string,
            has_previous_emails=has_previous_emails,
        )

        needs_search = context_decision.get("needs_gmail_search", True)
        use_memory = context_decision.get("use_memory_emails", False)
        resolved_question = context_decision.get("resolved_question", question)

        logger.info(
            f"[Orchestrator] Decision — "
            f"needs_search: {needs_search}, use_memory: {use_memory}"
        )

        # ── Step 2A: Answer from memory only (follow-up question) ─────────
        if use_memory and not needs_search:
            result = answer_service.generate_from_memory(
                question=resolved_question,
                memory_emails=last_emails,
                conversation_history=history_string,
            )

            # Store this turn but reuse previous emails
            conversation_memory.add_turn(
                session_id=session_id,
                user_message=question,
                assistant_response=result["answer"],
                retrieved_emails=last_emails,  # carry forward
            )

            result["used_memory"] = True
            return result

        # ── Step 2B: Fresh Gmail search ───────────────────────────────────
        intent = intent_service.analyze(resolved_question)
        gmail_queries = intent.get("gmail_queries", [resolved_question])
        max_results = intent.get("max_results", 10)

        logger.info(f"[Orchestrator] Gmail queries: {gmail_queries}")

        emails = live_gmail_service.search_and_fetch(
            queries=gmail_queries,
            max_per_query=max_results,
        )

        logger.info(f"[Orchestrator] Fetched {len(emails)} emails")

        # ── Step 3: Generate answer ───────────────────────────────────────
        result = answer_service.generate(
            question=resolved_question,
            emails=emails,
            conversation_history=history_string,
        )

        # ── Step 4: Store turn in memory ──────────────────────────────────
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


orchestrator = QueryOrchestrator()