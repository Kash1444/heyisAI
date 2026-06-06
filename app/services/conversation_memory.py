# app/services/conversation_memory.py
#
# Stores conversation history per session.
# Each turn stores: user message, assistant response, AND
# the retrieved emails — so follow-up questions can
# reference the same emails without re-searching Gmail.
#
# Why store emails in memory?
# "Summarize it" needs to know what "it" is.
# The emails from the previous search ARE "it".
# Without storing them, every follow-up starts from scratch.

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

MAX_TURNS = 10  # keep last 10 exchanges per session


@dataclass
class ConversationTurn:
    """
    One complete exchange in a conversation.
    Stores everything needed to answer follow-up questions.
    """
    user_message: str
    assistant_response: str
    retrieved_emails: list[dict] = field(default_factory=list)
    gmail_queries_used: list[str] = field(default_factory=list)


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

    def get_context_string(self, session_id: str) -> str:
        """
        Build a conversation history string for the LLM prompt.

        The LLM needs to see previous turns to understand
        references like "it", "that email", "the order".
        We pass the last 3 turns — enough context without
        bloating the prompt.
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        # Last 3 turns is sufficient for most follow-ups
        recent = history[-3:]
        lines = []

        for turn in recent:
            lines.append(f"User: {turn.user_message}")
            # Truncate long responses to save prompt space
            response_preview = turn.assistant_response[:300]
            if len(turn.assistant_response) > 300:
                response_preview += "..."
            lines.append(f"Assistant: {response_preview}")

        return "\n".join(lines)

    def clear_session(self, session_id: str):
        """Clear history — user starts a fresh conversation."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"[Memory] Cleared session '{session_id}'")


# Singleton
conversation_memory = ConversationMemoryService()