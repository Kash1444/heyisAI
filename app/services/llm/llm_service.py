# app/services/llm/llm_service.py

from app.services.llm.factory import get_structured_llm
from app.services.llm.schemas.call_query import CallQueryResult
from app.services.llm.schemas.domain_plan import DomainPlan
from app.services.llm.schemas.execution_plan import ExecutionPlan
from app.services.llm.prompts.planner import build_planner_prompt, build_domain_classifier_prompt
from app.services.llm.prompts.response_generator import build_response_prompt, build_unified_response_prompt
from app.services.llm.prompts.clarification_resolver import build_clarification_resolver_prompt
from app.services.llm.prompts.call_query import (
    build_call_query_prompt,
    build_call_response_prompt,
)

llm = get_structured_llm()


def plan_query(query: str) -> ExecutionPlan:
    prompt = build_planner_prompt(query)
    return llm.generate(prompt, schema=ExecutionPlan, temperature=0.01)


def classify_domains(query: str, conversation_history: str = "") -> DomainPlan:
    """
    Fast routing call: decide which data domains (gmail/calls/sms/notifications)
    are needed to answer the query and whether to run them in parallel or sequentially.
    """
    prompt = build_domain_classifier_prompt(query, conversation_history)
    return llm.generate(prompt, schema=DomainPlan, temperature=0.0)



def generate_response(query: str, context: str) -> str:
    prompt = build_response_prompt(query, context)
    return llm.chat(prompt, temperature=0.3)


def resolve_clarification(
    original_query: str,
    clarification_question: str,
    user_answer: str,
) -> str:
    """
    Merges the user's clarification answer into the original query.
    Returns a clean, single rewritten query string.
    """
    prompt = build_clarification_resolver_prompt(
        original_query, clarification_question, user_answer
    )
    return llm.chat(prompt, temperature=0.0).strip()


# ── LEGACY ────────────────────────────────────────────────────────────────────

def parse_call_query(query: str) -> CallQueryResult:
    """[LEGACY] Superseded by plan_query()."""
    prompt = build_call_query_prompt(query)
    return llm.generate(prompt, schema=CallQueryResult, temperature=0.01)


def generate_call_response(query: str, context: str) -> str:
    """[LEGACY] Superseded by generate_response()."""
    prompt = build_call_response_prompt(query, context)
    return llm.chat(prompt, temperature=0.3)