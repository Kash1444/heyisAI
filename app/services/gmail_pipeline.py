# app/services/gmail_pipeline.py
#
# Thin adapter that wraps the existing Gmail Orchestrator so the
# Unified Orchestrator can call it via the same PipelineResult contract.
#
# This file MUST NOT modify orchestrator.py — it only delegates to it.

import logging
from app.services.pipeline_result import PipelineResult

logger = logging.getLogger(__name__)


class GmailPipeline:
    """
    Delegates to the existing QueryOrchestrator (orchestrator.py) and
    maps its output to a standard PipelineResult.
    """

    def run(
        self,
        query: str,
        session_id: str,
        history: str = "",
    ) -> PipelineResult:
        """
        Run the Gmail pipeline for a user query.

        Parameters
        ----------
        query      : The user's natural language query.
        session_id : Conversation session ID (for Gmail's own memory).
        history    : Serialised conversation history string (context only;
                     Gmail's orchestrator manages its own internal memory).

        Returns
        -------
        PipelineResult with domain="gmail".
        """
        logger.info(f"[GmailPipeline] Running for query: '{query}'")

        try:
            # Import here to avoid circular imports at module load
            from app.services.orchestrator import orchestrator

            result = orchestrator.run(
                question=query,
                session_id=session_id,
            )

            # Map orchestrator output → PipelineResult
            answer      = result.get("answer", "")
            sources_raw = result.get("sources", [])
            emails      = result.get("emails", [])      # may or may not be present
            has_results = result.get("has_results", False)
            error_type  = result.get("error_type")

            # Build a simple context string from the answer (the orchestrator
            # already fetched emails and built its own context internally).
            # We expose the answer as context so the unified response generator
            # can incorporate it alongside phone data.
            context_str = answer if answer else "No Gmail data found."

            # Map sources (list of SourceEmail-like dicts)
            sources = []
            for s in sources_raw:
                if hasattr(s, "dict"):
                    sources.append(s.dict())
                elif isinstance(s, dict):
                    sources.append(s)

            error_msg = None
            if error_type == "model_exhausted":
                error_msg = "Gmail AI model is temporarily unavailable."
            elif error_type == "internal_error":
                error_msg = "Gmail pipeline encountered an internal error."

            logger.info(
                f"[GmailPipeline] Done — has_results={has_results}, "
                f"sources={len(sources)}, error={error_msg}"
            )

            return PipelineResult(
                domain="gmail",
                data=emails,
                context_str=context_str,
                has_results=has_results,
                sources=sources,
                error=error_msg,
                meta={
                    "intent":      result.get("intent"),
                    "used_memory": result.get("used_memory", False),
                },
            )

        except ValueError as e:
            # Typically: Gmail auth not set up
            logger.warning(f"[GmailPipeline] Auth error: {e}")
            return PipelineResult(
                domain="gmail",
                error=f"Gmail is not authenticated: {e}",
            )

        except Exception as e:
            logger.exception(f"[GmailPipeline] Unexpected error: {e}")
            return PipelineResult(
                domain="gmail",
                error="Gmail pipeline failed unexpectedly.",
            )


# Singleton
gmail_pipeline = GmailPipeline()
