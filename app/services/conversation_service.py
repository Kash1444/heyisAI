# app/services/conversation_service.py

import logging
from collections import defaultdict
from app.schemas.chat import ConversationTurn

logger = logging.getLogger(__name__)

# In-memory session store
# Key: session_id, Value: list of ConversationTurn
# In production: replace with Redis or a database
_sessions: dict[str, list[ConversationTurn]] = defaultdict(list)

MAX_HISTORY_TURNS = 10  # keep last 10 exchanges to avoid huge prompts


class ConversationService:
    """
    Manages per-session conversation history.

    Why in-memory for now?
    Simple, fast, zero dependencies.
    Downside: history lost on server restart.

    Production upgrade path:
    Replace _sessions dict with Redis calls.
    The interface (get/add/clear) stays identical.
    Nothing else in the codebase changes.
    That's the value of isolating this in a service.
    """

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        """Get conversation history for a session."""
        return _sessions[session_id][-MAX_HISTORY_TURNS:]

    def add_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ):
        """Append a user/assistant exchange to session history."""
        _sessions[session_id].append(
            ConversationTurn(role="user", content=user_message)
        )
        _sessions[session_id].append(
            ConversationTurn(role="assistant", content=assistant_message)
        )
        logger.debug(
            f"Session '{session_id}' now has "
            f"{len(_sessions[session_id])} turns"
        )

    def clear_session(self, session_id: str):
        """Clear history for a session (user starts fresh)."""
        if session_id in _sessions:
            del _sessions[session_id]
            logger.info(f"Cleared session '{session_id}'")

    def build_context_prompt(
        self,
        session_id: str,
        current_question: str,
    ) -> str:
        """
        Build a prompt that includes conversation history.

        This is how the agent 'remembers' previous turns.
        We literally include past messages in the prompt.
        This is called 'prompt-based memory' — the simplest
        and most reliable memory approach for Phase 1.
        """
        history = self.get_history(session_id)

        if not history:
            return current_question

        history_text = "\n".join([
            f"{turn.role.capitalize()}: {turn.content}"
            for turn in history
        ])

        return (
            f"Previous conversation:\n"
            f"{history_text}\n\n"
            f"Current question: {current_question}"
        )


conversation_service = ConversationService()