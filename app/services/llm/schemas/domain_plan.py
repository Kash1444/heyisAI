# app/services/llm/schemas/domain_plan.py
#
# The structured output the Domain Classifier LLM must produce.
# This is a fast, lightweight classification call — NOT a full execution plan.

from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# All data domains the unified orchestrator can route to.
DomainName = Literal["gmail", "calls", "sms", "notifications"]


class DomainPlan(BaseModel):
    """
    Routing decision produced by the Domain Classifier LLM.

    The Unified Orchestrator reads this to decide:
      - Which sub-pipelines to activate.
      - Whether they should run in parallel or sequentially.
      - Whether clarification is needed before routing.
    """

    domains: List[DomainName] = Field(
        description=(
            "List of data domains required to answer the query. "
            "Include only what is explicitly needed. "
            "Possible values: 'gmail', 'calls', 'sms', 'notifications'."
        )
    )

    strategy: Literal["parallel", "sequential"] = Field(
        default="parallel",
        description=(
            "Execution strategy for multiple domains.\n"
            "  - 'parallel'   : run all domains concurrently (most queries).\n"
            "  - 'sequential' : one domain's output is needed as input for another "
            "(e.g. get gmail timestamp → find notification at that time)."
        )
    )

    reasoning: str = Field(
        description=(
            "One sentence explaining why these domains were selected. "
            "Used only for logging and debugging."
        )
    )

    needs_clarification: bool = Field(
        default=False,
        description=(
            "Set to true when the query is too vague to route reliably. "
            "When true, domains may be empty and clarification_question must be set."
        )
    )

    clarification_question: Optional[str] = Field(
        default=None,
        description=(
            "The exact question to ask the user when needs_clarification is true. "
            "Should be short and specific. "
            "Example: 'Do you mean emails, SMS messages, or both?'"
        )
    )
