# app/services/llm/schemas/execution_plan.py
#
# The structured output schema the Planner LLM must produce.
# ExecutionPlan is parsed by StructuredLLM and drives the Executor.

from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# All tools the executor knows how to call.
# When adding a new tool, register it here AND in tools/registry.py.
# ---------------------------------------------------------------------------
ToolName = Literal[
    "search_calls",
    "search_sms",
    "get_sms_spend_summary",
    "get_sms_category_breakdown",
    "get_otp_history",
    "get_sms_timeline",
    "get_sms_stats",
    "search_notifications",
    "get_app_usage",
    "get_location_at_timestamp",
    "get_location_range",
    "search_gmail",
]


class TaskSpec(BaseModel):
    """A single tool invocation in the execution plan."""

    task_id: int = Field(
        description="Unique identifier for this task (1-based, ascending)."
    )
    tool: ToolName = Field(
        description="Name of the tool/function to invoke."
    )
    reasoning: str = Field(
        description="Why this tool is needed for answering the user query."
    )
    depends_on: List[int] = Field(
        default=[],
        description=(
            "List of task_ids whose results must be available before this task runs. "
            "The executor will inject upstream result fields into this task's params automatically."
        )
    )
    params: Dict[str, Any] = Field(
        default={},
        description=(
            "Static input parameters for the tool. "
            "Leave a field empty ('') or omit it if it will be filled from a depends_on task result."
        )
    )


class QueryUnderstanding(BaseModel):
    """High-level interpretation of what the user is asking."""

    user_intent: str = Field(
        description="One sentence describing the user's goal."
    )
    domains_required: List[str] = Field(
        description="List of data domains needed, e.g. ['calls', 'location']."
    )


class ExecutionPlan(BaseModel):
    """
    The full structured plan produced by the Planner LLM.
    Consumed by the Executor to run tools and gather results.
    """

    query_understanding: QueryUnderstanding

    needs_clarification: bool = Field(
        default=False,
        description=(
            "Set to true when the query is too ambiguous to execute reliably "
            "(e.g. partial/unclear contact name, multiple possible interpretations). "
            "When true, tasks may be empty and clarification_question must be set."
        )
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description=(
            "The exact question to return to the user when needs_clarification is true. "
            "Should be short, specific, and reference the ambiguous part of the query. "
            "Example: 'Did you mean Small Chechi USA?' or 'Which Sarah do you mean — Sarah Johnson or Sarah Thomas?'"
        )
    )

    tasks: List[TaskSpec] = Field(
        default=[],
        description=(
            "Ordered list of tool invocations. "
            "Tasks with no depends_on can run immediately. "
            "May be empty when needs_clarification is true."
        )
    )