# app/services/clarification_store.py
#
# Tracks pending clarification state per session.
# Stores the original query so it can be re-executed after the user responds.

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ClarificationState:
    original_query: str                  # the query that triggered the question
    clarification_question: str          # what the LLM asked the user
    resolved: bool = False
    resolved_query: Optional[str] = None # merged query after user answers


# session_id → ClarificationState
_store: Dict[str, ClarificationState] = {}


def set_pending(session_id: str, original_query: str, question: str) -> None:
    _store[session_id] = ClarificationState(
        original_query=original_query,
        clarification_question=question,
    )


def get_pending(session_id: str) -> Optional[ClarificationState]:
    return _store.get(session_id)


def resolve(session_id: str, resolved_query: str) -> None:
    state = _store.get(session_id)
    if state:
        state.resolved = True
        state.resolved_query = resolved_query


def clear(session_id: str) -> None:
    _store.pop(session_id, None)


def has_pending(session_id: str) -> bool:
    state = _store.get(session_id)
    return state is not None and not state.resolved