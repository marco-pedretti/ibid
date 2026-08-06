"""Query rewriting for improved retrieval (R-03).

Rewrites each query with an LLM before embedding so the dense/sparse
retrieval sees a more informative text. Falls back to the original
query on any error so the pipeline degrades gracefully when the LLM
endpoint is unavailable.
"""

from __future__ import annotations

import src.config as cfg
from src.generation.chat import generate

_SYSTEM_PROMPT = (
    "Rewrite the following question as a concise search query that maximizes "
    "recall from a document collection. "
    "Return only the rewritten query — no explanation, no prefix, no quotes."
)


def rewrite(query: str, base_url: str | None = None, model: str | None = None) -> str:
    """Return a rewritten version of *query* optimised for retrieval.

    Falls back to the original query on any error.
    """
    base_url = base_url or cfg.LLM_BASE_URL
    model = model or cfg.LLM_MODEL
    try:
        return generate(
            base_url=base_url,
            model=model,
            system=_SYSTEM_PROMPT,
            user=query,
            temperature=0.0,
            max_tokens=128,
        ).strip()
    except Exception:
        return query


def rewrite_batch(
    queries: list[str],
    base_url: str | None = None,
    model: str | None = None,
) -> list[str]:
    """Rewrite a list of queries, preserving order and length."""
    return [rewrite(q, base_url, model) for q in queries]
