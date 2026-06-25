# app/services/unified_orchestrator.py
#
# The Unified Orchestrator — single entry point for ALL user queries.
#
# Routing logic:
#   1. Classify which domain(s) the query needs (gmail / calls / sms / notifications)
#   2. Run the relevant sub-pipelines in PARALLEL (asyncio.gather via run_in_executor)
#   3. Merge all results and generate one unified answer
#   4. Store the full turn in conversation memory
#
# Design principles:
#   - Sub-pipelines (gmail_pipeline, phone_pipeline) are called as black boxes.
#   - The existing orchestrator.py, executor.py, and tool files are NEVER modified.
#   - Partial failures surface as a note in the answer, not a full crash.

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.services.pipeline_result import PipelineResult
from app.services.gmail_pipeline import gmail_pipeline
from app.services.phone_pipeline import phone_pipeline
from app.services.conversation_memory import conversation_memory

logger = logging.getLogger(__name__)

# Thread pool for running blocking sub-pipelines concurrently.
# Max 4 workers: gmail + phone + headroom.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="unified_orch")

# Phone-data domains (served by phone_pipeline)
_PHONE_DOMAINS = {"calls", "sms", "notifications"}


class UnifiedOrchestrator:
    """
    Routes user queries to the correct data pipelines and returns
    a single coherent answer covering all requested data domains.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def run(
        self,
        query: str,
        session_id: str,
        db: Any,
    ) -> dict:
        """
        Async entry point called by the FastAPI endpoint.

        Parameters
        ----------
        query      : User's natural language message.
        session_id : Session ID for conversation memory.
        db         : SQLAlchemy session (for phone data tools).

        Returns
        -------
        dict with keys:
          answer       (str)
          sources      (list[dict])   — Gmail email citations
          domains_used (list[str])    — which domains were actually queried
          has_results  (bool)
          partial_failures (list[str]) — domains that errored (may be empty)
        """
        logger.info(
            f"[UnifiedOrchestrator] Query='{query}' | session={session_id}"
        )

        # ── Step 1: Load conversation history ─────────────────────────────
        history_str = conversation_memory.get_context_string(session_id)

        # ── Step 2: Classify domains ──────────────────────────────────────
        domain_plan = await self._classify_domains(query, history_str)

        if domain_plan is None:
            # Classification itself crashed — fall back to gmail-only
            logger.warning(
                "[UnifiedOrchestrator] Domain classification failed — "
                "defaulting to gmail"
            )
            domain_plan = _FallbackPlan(domains=["gmail"])

        if domain_plan.needs_clarification:
            clarification = (
                domain_plan.clarification_question
                or "Could you clarify what type of data you're looking for?"
            )
            logger.info(
                f"[UnifiedOrchestrator] Needs clarification: {clarification}"
            )
            return {
                "answer":           clarification,
                "sources":          [],
                "domains_used":     [],
                "has_results":      False,
                "partial_failures": [],
                "needs_clarification": True,
            }

        active_domains: list[str] = domain_plan.domains
        logger.info(
            f"[UnifiedOrchestrator] Domains={active_domains} | "
            f"Strategy={domain_plan.strategy}"
        )

        # ── Step 3: Run sub-pipelines ─────────────────────────────────────
        gmail_domains  = [d for d in active_domains if d == "gmail"]
        phone_domains  = [d for d in active_domains if d in _PHONE_DOMAINS]

        if domain_plan.strategy == "sequential" and gmail_domains and phone_domains:
            pipeline_results = await self._run_sequential(
                query, session_id, db, history_str,
                gmail_domains, phone_domains,
            )
        else:
            pipeline_results = await self._run_parallel(
                query, session_id, db, history_str,
                gmail_domains, phone_domains,
            )

        # ── Step 4: Check for phone-data clarification request ────────────
        # (The phone planner may itself ask for clarification)
        for pr in pipeline_results:
            if pr.meta.get("needs_clarification"):
                cq = pr.meta.get("clarification_question", "")
                return {
                    "answer":              cq,
                    "sources":             [],
                    "domains_used":        [],
                    "has_results":         False,
                    "partial_failures":    [],
                    "needs_clarification": True,
                }

        # ── Step 5: Collect errors and build context blocks ───────────────
        partial_failures: list[str] = []
        domain_contexts:  list[tuple[str, str]] = []
        all_sources:      list[dict] = []
        domains_used:     list[str]  = []
        has_any_results = False

        for pr in pipeline_results:
            if pr.error:
                partial_failures.append(pr.domain)
                logger.warning(
                    f"[UnifiedOrchestrator] Partial failure in "
                    f"'{pr.domain}': {pr.error}"
                )
                continue  # skip to next pipeline

            label = pr.domain.capitalize()
            domain_contexts.append((label, pr.context_str))
            all_sources.extend(pr.sources)
            domains_used.append(pr.domain)

            if pr.has_results:
                has_any_results = True

        # If EVERYTHING failed, return a graceful error
        if not domain_contexts and partial_failures:
            return {
                "answer": (
                    "I wasn't able to retrieve any data right now. "
                    "Please try again in a moment."
                ),
                "sources":          [],
                "domains_used":     [],
                "has_results":      False,
                "partial_failures": partial_failures,
            }

        # ── Step 6: Generate unified answer ───────────────────────────────
        answer = await self._generate_answer(
            query, domain_contexts, history_str, partial_failures
        )

        # ── Step 7: Store in unified memory ───────────────────────────────
        conversation_memory.add_unified_turn(
            session_id=session_id,
            user_message=query,
            assistant_response=answer,
            pipeline_results=pipeline_results,
        )

        logger.info(
            f"[UnifiedOrchestrator] Done — "
            f"domains_used={domains_used}, "
            f"partial_failures={partial_failures}, "
            f"has_results={has_any_results}"
        )

        return {
            "answer":           answer,
            "sources":          all_sources,
            "domains_used":     domains_used,
            "has_results":      has_any_results,
            "partial_failures": partial_failures,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _classify_domains(self, query: str, history: str):
        """Run domain classification in a thread (it's a blocking LLM call)."""
        loop = asyncio.get_event_loop()
        try:
            from app.services.llm.llm_service import classify_domains
            return await loop.run_in_executor(
                _EXECUTOR,
                lambda: classify_domains(query, history),
            )
        except Exception as e:
            logger.exception(f"[UnifiedOrchestrator] classify_domains failed: {e}")
            return None

    async def _run_parallel(
        self,
        query: str,
        session_id: str,
        db: Any,
        history: str,
        gmail_domains: list[str],
        phone_domains: list[str],
    ) -> list[PipelineResult]:
        """Run gmail and phone pipelines concurrently via asyncio.gather."""
        loop = asyncio.get_event_loop()
        tasks = []

        if gmail_domains:
            tasks.append(
                loop.run_in_executor(
                    _EXECUTOR,
                    lambda: gmail_pipeline.run(
                        query=query,
                        session_id=session_id,
                        history=history,
                    ),
                )
            )

        if phone_domains:
            tasks.append(
                loop.run_in_executor(
                    _EXECUTOR,
                    lambda: phone_pipeline.run(
                        query=query,
                        db=db,
                        domains=phone_domains,
                    ),
                )
            )

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert any unexpected exceptions to error PipelineResults
        clean: list[PipelineResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                domain = "gmail" if (gmail_domains and i == 0) else "phone"
                logger.error(f"[UnifiedOrchestrator] Pipeline '{domain}' raised: {r}")
                clean.append(PipelineResult(domain=domain, error=str(r)))
            else:
                clean.append(r)

        return clean

    async def _run_sequential(
        self,
        query: str,
        session_id: str,
        db: Any,
        history: str,
        gmail_domains: list[str],
        phone_domains: list[str],
    ) -> list[PipelineResult]:
        """
        Run gmail first, then phone (sequential strategy).
        Used when phone data needs gmail context (e.g. timestamp injection).
        For now both pipelines still run independently — true cross-pipeline
        dependency injection can be added here when needed.
        """
        results: list[PipelineResult] = []
        loop = asyncio.get_event_loop()

        if gmail_domains:
            gmail_result = await loop.run_in_executor(
                _EXECUTOR,
                lambda: gmail_pipeline.run(
                    query=query,
                    session_id=session_id,
                    history=history,
                ),
            )
            results.append(gmail_result)

        if phone_domains:
            phone_result = await loop.run_in_executor(
                _EXECUTOR,
                lambda: phone_pipeline.run(
                    query=query,
                    db=db,
                    domains=phone_domains,
                ),
            )
            results.append(phone_result)

        return results

    async def _generate_answer(
        self,
        query: str,
        domain_contexts: list[tuple[str, str]],
        history: str,
        partial_errors: list[str],
    ) -> str:
        """Generate the final unified answer in a thread (blocking LLM call)."""
        loop = asyncio.get_event_loop()
        try:
            from app.services.llm.llm_service import llm
            from app.services.llm.prompts.response_generator import (
                build_unified_response_prompt,
            )

            prompt = build_unified_response_prompt(
                query=query,
                domain_contexts=domain_contexts,
                conversation_history=history,
                partial_errors=partial_errors if partial_errors else None,
            )
            return await loop.run_in_executor(
                _EXECUTOR,
                lambda: llm.chat(prompt, temperature=0.3),
            )
        except Exception as e:
            logger.exception(f"[UnifiedOrchestrator] Answer generation failed: {e}")
            # Graceful degradation: return the raw context string
            fallback = "\n\n".join(ctx for _, ctx in domain_contexts)
            return fallback or "I encountered an error generating a response. Please try again."


# ─────────────────────────────────────────────────────────────────────────────
# Fallback plan (used when domain classification crashes)
# ─────────────────────────────────────────────────────────────────────────────

class _FallbackPlan:
    """Minimal stand-in for DomainPlan when the LLM classifier fails."""
    def __init__(self, domains: list[str]):
        self.domains               = domains
        self.strategy              = "parallel"
        self.needs_clarification   = False
        self.clarification_question = None


# Singleton
unified_orchestrator = UnifiedOrchestrator()
