# app/services/llm/prompts/call_query.py

from __future__ import annotations
import json, re
from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator

# ── All allowed intents (used by constrained decoder, not injected into prompt) ──
CALL_INTENTS = [
    "recent_calls", "missed_calls", "outgoing_calls", "incoming_calls",
    "total_calls", "calls_by_date", "unanswered_calls", "rejected_calls",
    "declined_calls", "auto_rejected_calls", "contact_history",
    "most_contacted", "least_contacted", "never_called_back", "mutual_calls",
    "one_sided_calls", "unknown_numbers", "blocked_calls", "new_contacts",
    "frequent_callers", "contact_last_call", "contact_call_count",
    "longest_call", "shortest_call", "average_call_duration",
    "total_call_duration", "calls_over_duration", "duration_by_contact",
    "duration_by_period", "last_call_time", "first_call_time",
    "busiest_day", "busiest_hour", "quietest_period", "call_frequency",
    "calls_at_time", "late_night_calls", "weekend_calls", "weekday_calls",
    "search_by_number", "search_by_keyword", "voicemail_calls",
    "international_calls", "short_calls", "calls_by_carrier",
    "calls_by_device", "calls_by_location", "call_comparison", "call_trend",
    "period_over_period", "contact_rank", "call_streak", "no_call_days",
    "peak_call_day", "call_gap", "remind_to_call", "follow_up_calls",
    "call_summary", "export_calls", "delete_calls", "call_stats", "unknown",
]

IntentLiteral = Literal[tuple(CALL_INTENTS)]  # type: ignore[valid-type]


# ── Pydantic schema — the real guardrail ─────────────────────────────────────
class CallQueryResult(BaseModel):
    intent: IntentLiteral
    contact_name: Optional[str] = None
    relative: Optional[Literal[
        "today", "yesterday", "this_week", "last_week",
        "this_month", "last_month", "this_year", "last_year"
    ]] = None
    date: Optional[str] = None
    time_from: Optional[str] = None
    time_to: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    duration_min: Optional[int] = Field(None, ge=0)
    duration_max: Optional[int] = Field(None, ge=0)
    phone_number: Optional[str] = None
    keyword: Optional[str] = None
    compare_a: Optional[str] = None
    compare_b: Optional[str] = None
    rank_by: Optional[Literal["count", "duration", "recency"]] = None
    limit: Optional[int] = Field(None, ge=1, le=100)
    granularity: Optional[Literal["daily", "weekly", "monthly"]] = None
    area_code: Optional[str] = None
    country_code: Optional[str] = None
    device: Optional[str] = None
    carrier: Optional[str] = None

    @model_validator(mode="after")
    def _date_exclusive(self) -> "CallQueryResult":
        filled = sum([
            self.relative is not None,
            self.date is not None,
            self.date_from is not None or self.date_to is not None,
        ])
        if filled > 1:
            raise ValueError("Only one date structure allowed.")
        return self

    @classmethod
    def json_schema_str(cls) -> str:
        return json.dumps(cls.model_json_schema(), indent=2)


# ── Minimal prompt — just the task + schema + 3 shots ────────────────────────
def build_call_query_prompt(query: str) -> str:
    """
    Minimal prompt. Guardrails live in Pydantic + constrained decoding,
    NOT in prompt length. Reduces attention dilution on smaller HF models.
    """
    schema = CallQueryResult.json_schema_str()

    return f"""\
Extract call log query intent. Output ONLY valid JSON matching this schema:
{schema}

Examples:
Q: show missed calls from Sarah this week
A: {{"intent":"missed_calls","contact_name":"Sarah","relative":"this_week"}}

Q: calls longer than 30 minutes
A: {{"intent":"calls_over_duration","duration_min":30}}

Q: ????
A: {{"intent":"unknown"}}

Q: {query}
A:"""


def build_call_response_prompt(query: str, context: str) -> str:
    """Grounded response prompt — output must be Markdown (rendered on Android via Markwon)."""
    return f"""\
Answer using ONLY the data below. If data is insufficient, say so honestly.

**Always respond in Markdown format**:
- Start with a 1-sentence plain-language summary.
- Use a bullet list (`-`) for each call record.
- Use **bold** for names, call types, and durations.
- Use `inline code` for phone numbers.

Query: {query}
Data: {context}
Answer:"""


# ── Parser + validation (same safety net, unchanged) ─────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_OBJ   = re.compile(r"\{[\s\S]*\}", re.DOTALL)

def parse_llm_response(raw: str) -> CallQueryResult:
    fence = _FENCE.search(raw)
    candidate = fence.group(1).strip() if fence else raw.strip()
    obj = _OBJ.search(candidate)
    if not obj:
        return CallQueryResult(intent="unknown")
    try:
        data = json.loads(obj.group())
        return CallQueryResult.model_validate(data)
    except Exception:
        return CallQueryResult(intent="unknown")


# ── HF inference with constrained decoding ───────────────────────────────────
def run_call_query_inference(query, model, tokenizer) -> CallQueryResult:
    """
    The prompt is tiny. The schema constraint (outlines/lm-format-enforcer)
    does the heavy lifting — it physically blocks invalid tokens at decode time.
    """
    from outlines.integrations.transformers import JSONLogitsProcessor

    prompt = build_call_query_prompt(query)
    processor = JSONLogitsProcessor(CallQueryResult.model_json_schema(), tokenizer)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output_ids = model.generate(
        **inputs,
        logits_processor=[processor],   # ← hard schema enforcement
        do_sample=False,                 # ← greedy, deterministic
        max_new_tokens=128,              # ← tight cap, JSON is short
        pad_token_id=tokenizer.eos_token_id,
    )
    new_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
    raw = tokenizer.decode(new_ids, skip_special_tokens=True)
    return parse_llm_response(raw)