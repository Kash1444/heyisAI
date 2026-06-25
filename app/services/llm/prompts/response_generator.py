# app/services/llm/prompts/response_generator.py
#
# Prompt template for the Response Generator LLM.
# Takes the unified context built by the Context Builder and produces
# a natural language answer for the user.
#
# Rendered on Android via Markwon — keep formatting proportional to content size.




def build_response_prompt(query: str, context: str) -> str:
    return f"""\
You are a helpful AI assistant replying inside a mobile chat app.

Answer the user's question using ONLY the retrieved data below.

Your response must feel clean, compact, and easy to read in a phone chat bubble.

Rules:
- Keep answers proportional to the question.
- Prefer plain sentences over heavy formatting.
- Never use #, ##, or markdown headings.
- Use bullets only for 3+ short items.
- Keep bullets short and single-line.
- Avoid using "|" separators unless absolutely necessary.
- Prefer natural spacing and indentation instead of symbolic separators.
- For related details, place secondary information on the next indented line.

Example:
- Rahul
  Missed call at 8:42 PM

Instead of:
- Rahul | Missed call | 8:42 PM

- Use **bold** sparingly for only the most important detail.
- Do not use tables, nested lists, or code blocks.
- Leave only a single blank line between sections.
- Avoid filler phrases and introductions.
- If no data exists, say so briefly.
- Never invent or assume information.

Good examples:

Q: who called me last?
A: Your last call was from **Rahul** at 8:42 PM.

Q: show missed calls
A:
- Mom
  10:14 AM

- Aman
  Yesterday

- Swiggy Delivery
  Yesterday

Q: how many calls today?
A: You had **12 calls** today.

User question:
{query}

Retrieved data:
{context}
"""


# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED RESPONSE PROMPT
# Handles answers spanning multiple domains (gmail + calls + sms + notifications)
# ─────────────────────────────────────────────────────────────────────────────

def build_unified_response_prompt(
    query: str,
    domain_contexts: list[tuple[str, str]],
    conversation_history: str = "",
    partial_errors: list[str] | None = None,
) -> str:
    """
    Build a response prompt that merges context from multiple data domains.

    Parameters
    ----------
    query              : The original user question.
    domain_contexts    : List of (domain_label, context_string) tuples.
                         e.g. [("Gmail", "..."), ("SMS", "...")]
    conversation_history: Recent conversation for follow-up context.
    partial_errors     : List of domain names that failed (for partial-failure note).
    """
    # Build the combined context block
    context_blocks = []
    for label, ctx in domain_contexts:
        if ctx.strip():
            context_blocks.append(f"=== {label.upper()} DATA ===\n{ctx.strip()}")

    combined_context = "\n\n".join(context_blocks) if context_blocks else "No data was retrieved."

    # Build the optional history section
    history_section = ""
    if conversation_history and conversation_history.strip():
        history_section = f"\nRecent conversation:\n{conversation_history.strip()}\n"

    # Build optional partial-failure note
    failure_note = ""
    if partial_errors:
        failed = ", ".join(partial_errors)
        failure_note = (
            f"\nNote: The following data sources could not be reached: {failed}. "
            f"Answer only from the data that was retrieved successfully.\n"
        )

    return f"""\
You are a helpful AI assistant replying inside a mobile chat app.

Answer the user's question using ONLY the retrieved data shown below.
The data may come from multiple sources (emails, calls, SMS, notifications) — \
synthesise them into a single, coherent answer.

Rules:
- Keep answers proportional to the question.
- Prefer plain sentences over heavy formatting.
- Never use #, ##, or markdown headings.
- Use bullets only for 3+ short items. Keep bullets short.
- Prefer natural indentation over "|" separators.
- Use **bold** sparingly for the single most important detail.
- Do not use tables, nested lists, or code blocks.
- Leave only a single blank line between sections.
- Avoid filler phrases and introductions.
- If a source has no data, say so briefly and move on.
- Never invent or assume information not present in the data.
- When data comes from multiple sources, weave them together naturally.
  Do NOT repeat section headers from the raw data in your answer.
{failure_note}{history_section}
User question:
{query}

Retrieved data:
{combined_context}
"""

