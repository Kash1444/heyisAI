# app/services/conversation_memory.py
#
# Stores conversation history per session.
# Each turn stores: user message, assistant response, AND
# the retrieved data from ALL domains (gmail, calls, sms, notifications)
# so follow-up questions can reference the same data without re-fetching.
#
# add_turn()         → legacy method used by the single-domain Gmail orchestrator
# add_unified_turn() → new method used by the Unified Orchestrator

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_TURNS = 10  # keep last 10 exchanges per session


@dataclass
class ConversationTurn:
    """
    One complete exchange in a conversation.
    Stores everything needed to answer follow-up questions
    across ALL data domains (gmail, calls, sms, notifications).
    """
    user_message:       str
    assistant_response: str

    # Gmail-specific (kept for backward compat with legacy orchestrator)
    retrieved_emails:   list[dict] = field(default_factory=list)
    gmail_queries_used: list[str]  = field(default_factory=list)

    # Unified — one entry per domain that returned results
    # Each entry: { "domain": "calls", "data": [...], "context_str": "..." }
    domain_results:     list[dict[str, Any]] = field(default_factory=list)

    # Which domains were active in this turn
    domains_used:       list[str] = field(default_factory=list)


class ConversationMemoryService:
    """
    Per-session conversation memory.

    Storage: in-memory dict keyed by session_id.
    Each session holds a list of ConversationTurns.

    Production upgrade path: replace the dict with Redis.
    The interface (get/add/clear) stays identical.
    """

    def __init__(self):
        # session_id → list of ConversationTurn
        self._sessions: dict[str, list[ConversationTurn]] = defaultdict(list)

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        retrieved_emails: list[dict] = None,
        gmail_queries_used: list[str] = None,
    ):
        """Store a completed conversation turn."""
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            retrieved_emails=retrieved_emails or [],
            gmail_queries_used=gmail_queries_used or [],
        )

        session = self._sessions[session_id]
        session.append(turn)

        # Keep only last MAX_TURNS to avoid unbounded memory growth
        if len(session) > MAX_TURNS:
            self._sessions[session_id] = session[-MAX_TURNS:]

        logger.debug(
            f"[Memory] Session '{session_id}' "
            f"now has {len(self._sessions[session_id])} turns"
        )

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        """Get all turns for a session."""
        return self._sessions.get(session_id, [])

    def add_unified_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        pipeline_results: list,          # list[PipelineResult] — avoid circular import
    ):
        """
        Store a completed turn from the Unified Orchestrator.
        Saves results from ALL active domains so follow-up questions
        can reference calls, SMS, notifications, and emails.
        """
        from app.services.pipeline_result import PipelineResult

        retrieved_emails = []
        gmail_queries    = []
        domain_results   = []
        domains_used     = []

        for pr in pipeline_results:
            if not isinstance(pr, PipelineResult) or pr.error:
                continue

            domains_used.append(pr.domain)

            # Store serialisable snapshot of this domain's results
            domain_results.append({
                "domain":      pr.domain,
                "data":        pr.data,
                "context_str": pr.context_str,
                "has_results": pr.has_results,
            })

            # Keep gmail emails in the legacy field for backward compat
            if pr.domain == "gmail":
                retrieved_emails = pr.data
                gmail_queries    = pr.meta.get("gmail_queries", [])

        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
            retrieved_emails=retrieved_emails,
            gmail_queries_used=gmail_queries,
            domain_results=domain_results,
            domains_used=domains_used,
        )

        session = self._sessions[session_id]
        session.append(turn)

        if len(session) > MAX_TURNS:
            self._sessions[session_id] = session[-MAX_TURNS:]

        logger.debug(
            f"[Memory] Unified turn saved for session '{session_id}' — "
            f"domains: {domains_used}"
        )

    def get_last_emails(self, session_id: str) -> list[dict]:
        """
        Get the emails from the most recent turn.

        This is what powers follow-up questions.
        "Summarize it" → get last emails → summarize those.
        """
        history = self.get_history(session_id)
        if not history:
            return []
        return history[-1].retrieved_emails

    def get_last_domain_data(self, session_id: str, domain: str) -> list[dict]:
        """
        Get the raw data records from the most recent turn for a specific domain.
        Useful for follow-up questions about calls, SMS, or notifications.
        """
        history = self.get_history(session_id)
        if not history:
            return []
        for dr in reversed(history[-1].domain_results):
            if dr.get("domain") == domain:
                return dr.get("data", [])
        return []

    def get_context_string(self, session_id: str) -> str:
        """
        Build a compact conversation summary for use as LLM context.
        Includes the last 3 turns and a brief note on what data was found
        in each domain (gmail emails, calls, SMS, notifications).
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        recent = history[-3:]
        lines = []

        for turn in recent:
            lines.append(f"User: {turn.user_message}")
            response_preview = turn.assistant_response[:300]
            if len(turn.assistant_response) > 300:
                response_preview += "..."
            lines.append(f"Assistant: {response_preview}")

            # ── Domain-aware context summary ───────────────────────────────
            # Legacy: gmail emails stored in retrieved_emails
            if turn.retrieved_emails and not turn.domain_results:
                email_refs = [
                    f"  - '{e.get('subject', 'no subject')}' "
                    f"from {e.get('sender', 'unknown')}"
                    for e in turn.retrieved_emails[:3]
                ]
                lines.append(
                    f"[Emails in this turn: {len(turn.retrieved_emails)}]"
                )
                lines.extend(email_refs)

            # Unified: all-domain results stored in domain_results
            for dr in turn.domain_results:
                domain  = dr.get("domain", "unknown")
                data    = dr.get("data", [])
                count   = len(data)
                if count == 0:
                    continue

                if domain == "gmail":
                    email_refs = [
                        f"  - '{e.get('subject', 'no subject')}' "
                        f"from {e.get('sender', 'unknown')}"
                        for e in data[:3]
                    ]
                    lines.append(f"[Emails in this turn: {count}]")
                    lines.extend(email_refs)

                elif domain == "phone" or domain == "calls":
                    names = [
                        r.get("name") or r.get("number", "?") for r in data[:3]
                    ]
                    lines.append(f"[Calls in this turn: {count} — {', '.join(names)}]")

                elif domain == "sms":
                    platforms = list({
                        r.get("platform") or r.get("name") or "?"
                        for r in data[:3]
                    })
                    lines.append(
                        f"[SMS in this turn: {count} — {', '.join(platforms)}]"
                    )

                elif domain == "notifications":
                    apps = list({
                        r.get("app_name") or "?" for r in data[:3]
                    })
                    lines.append(
                        f"[Notifications in this turn: {count} — apps: {', '.join(apps)}]"
                    )

        return "\n".join(lines)


    def clear_session(self, session_id: str):
        """Clear history — user starts a fresh conversation."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"[Memory] Cleared session '{session_id}'")


# Singleton
conversation_memory = ConversationMemoryService()