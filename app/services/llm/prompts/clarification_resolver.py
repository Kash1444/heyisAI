# app/services/llm/prompts/clarification_resolver.py
#
# Merges a user's clarification answer into the original query,
# producing a single clean query the planner can re-run.


def build_clarification_resolver_prompt(
    original_query: str,
    clarification_question: str,
    user_answer: str,
) -> str:
    return f"""\
A user submitted a query. An assistant asked a clarifying question. \
The user has now answered it.

Rewrite the original query as a single, clear, complete sentence that \
incorporates the user's answer. Output ONLY the rewritten query — no prose, \
no explanation, no quotes.

Original query: {original_query}
Clarifying question: {clarification_question}
User's answer: {user_answer}

Rewritten query:"""