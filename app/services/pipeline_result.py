# app/services/pipeline_result.py
#
# Shared output contract for all sub-pipelines (Gmail, Phone).
# The Unified Orchestrator receives a list of PipelineResult objects
# and uses them to build the final unified answer.

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineResult:
    """
    Standardised output from any sub-pipeline.

    Fields
    ------
    domain      : Which data domain produced this result.
                  One of: "gmail" | "calls" | "sms" | "notifications"
    data        : Raw records returned by the tool(s), for context building.
    context_str : Pre-formatted, labelled context string ready for the LLM.
    has_results : True if at least one record was returned.
    sources     : Citation objects (used by Gmail; empty for phone data).
    error       : If not None, the pipeline encountered a partial failure.
                  The orchestrator will surface this note to the user.
    """
    domain:      str
    data:        list[dict]        = field(default_factory=list)
    context_str: str               = ""
    has_results: bool              = False
    sources:     list[dict]        = field(default_factory=list)
    error:       str | None        = None

    # Extra metadata each pipeline may populate (e.g. gmail queries used)
    meta:        dict[str, Any]    = field(default_factory=dict)
