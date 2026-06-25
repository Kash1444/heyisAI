# app/services/phone_pipeline.py
#
# Thin adapter that wraps the existing Planner → Executor pipeline
# for phone data (calls, SMS, notifications) so the Unified Orchestrator
# can call it via the same PipelineResult contract.
#
# This file MUST NOT modify planner.py, executor.py, or any tool file.

import logging
from typing import Any

from app.services.pipeline_result import PipelineResult
from app.services.context_builder import build_unified_context

logger = logging.getLogger(__name__)

# Map domain names → the tool names that belong to each domain.
# Used to filter the execution plan to only the requested domains.
_DOMAIN_TOOLS: dict[str, set[str]] = {
    "calls": {
        "search_calls",
    },
    "sms": {
        "search_sms",
        "get_sms_spend_summary",
        "get_sms_category_breakdown",
        "get_otp_history",
        "get_sms_timeline",
        "get_sms_stats",
    },
    "notifications": {
        "search_notifications",
    },
}


class PhonePipeline:
    """
    Runs the Planner → Executor pipeline for any combination of
    calls / sms / notifications domains.

    The planner generates a full execution plan; we then optionally
    filter tasks to only the requested domains before executing.
    """

    def run(
        self,
        query: str,
        db: Any,
        domains: list[str],
    ) -> PipelineResult:
        """
        Run the phone data pipeline.

        Parameters
        ----------
        query   : The user's natural language query.
        db      : SQLAlchemy session (injected by FastAPI dependency).
        domains : Subset of ["calls", "sms", "notifications"] to activate.

        Returns
        -------
        PipelineResult with domain="phone" (covers calls+sms+notifications).
        """
        logger.info(
            f"[PhonePipeline] Running for query: '{query}' | domains: {domains}"
        )

        try:
            from app.services.llm.llm_service import plan_query
            from app.services.executor import run_execution_plan

            # ── Step 1: Plan ─────────────────────────────────────────────────
            plan = plan_query(query)

            # If the planner itself wants clarification, surface it
            if plan.needs_clarification:
                logger.info(
                    f"[PhonePipeline] Clarification needed: "
                    f"{plan.clarification_question}"
                )
                return PipelineResult(
                    domain="phone",
                    error=None,
                    meta={
                        "needs_clarification":    True,
                        "clarification_question": plan.clarification_question,
                    },
                )

            # ── Step 2: Filter to requested domains ──────────────────────────
            # Build the union of allowed tool names for the requested domains
            allowed_tools: set[str] = set()
            for d in domains:
                allowed_tools |= _DOMAIN_TOOLS.get(d, set())

            # Keep tasks whose tool is in the allowed set.
            # If no domain filtering (e.g. domains=["calls","sms","notifications"]),
            # all tasks pass through.
            if allowed_tools:
                original_tasks = plan.tasks
                plan.tasks = [
                    t for t in plan.tasks if t.tool in allowed_tools
                ]
                skipped = len(original_tasks) - len(plan.tasks)
                if skipped:
                    logger.info(
                        f"[PhonePipeline] Filtered out {skipped} tasks "
                        f"outside requested domains {domains}"
                    )

            if not plan.tasks:
                logger.info("[PhonePipeline] No tasks after domain filtering.")
                return PipelineResult(
                    domain="phone",
                    context_str="No relevant phone data found for this query.",
                    has_results=False,
                )

            # ── Step 3: Execute ──────────────────────────────────────────────
            results: dict[int, Any] = run_execution_plan(db, plan)

            # ── Step 4: Build context string ─────────────────────────────────
            context_str = build_unified_context(plan, results)

            # Collect all raw records for memory storage
            all_data: list[dict] = []
            for task_result in results.values():
                if isinstance(task_result, list):
                    all_data.extend(task_result)
                elif isinstance(task_result, dict):
                    all_data.append(task_result)

            has_results = any(
                (isinstance(v, list) and len(v) > 0) or
                (isinstance(v, dict) and v)
                for v in results.values()
            )

            logger.info(
                f"[PhonePipeline] Done — {len(plan.tasks)} tasks, "
                f"{len(all_data)} records, has_results={has_results}"
            )

            return PipelineResult(
                domain="phone",
                data=all_data,
                context_str=context_str,
                has_results=has_results,
                meta={
                    "domains_queried": domains,
                    "tasks_run":       [t.tool for t in plan.tasks],
                    "query_intent":    plan.query_understanding.user_intent,
                },
            )

        except Exception as e:
            logger.exception(f"[PhonePipeline] Unexpected error: {e}")
            return PipelineResult(
                domain="phone",
                error=f"Phone data pipeline failed: {e}",
            )


# Singleton
phone_pipeline = PhonePipeline()
