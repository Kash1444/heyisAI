# app/services/orchestrator.py
#
# The single entry point for all chat queries.
# Connects: intent → search → fetch → answer

import logging
from app.services.intent_service import intent_service
from app.services.live_gmail_service import live_gmail_service
from app.services.answer_service import answer_service

logger = logging.getLogger(__name__)


class QueryOrchestrator:
    """
    Orchestrates the full query pipeline:
    1. Analyze intent → get Gmail queries
    2. Search Gmail live
    3. Generate answer with citations
    """

    def run(self, question: str) -> dict:
        logger.info(f"[Orchestrator] Question: '{question}'")

        # Step 1: Analyze intent
        intent = intent_service.analyze(question)
        gmail_queries = intent.get("gmail_queries", [question])
        max_results = intent.get("max_results", 10)

        logger.info(f"[Orchestrator] Gmail queries: {gmail_queries}")

        # Step 2: Fetch live emails
        emails = live_gmail_service.search_and_fetch(
            queries=gmail_queries,
            max_per_query=max_results,
        )

        logger.info(f"[Orchestrator] Fetched {len(emails)} emails")

        # Step 3: Generate answer
        result = answer_service.generate(
            question=question,
            emails=emails,
        )

        result["intent"] = intent
        return result


orchestrator = QueryOrchestrator()