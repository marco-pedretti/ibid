"""Metadata filtering for retrieval (R-04).

Builds Qdrant Filter objects from content_type constraints, and provides a
keyword heuristic to infer the relevant content_type from a query string.
"""

from __future__ import annotations

from qdrant_client.models import FieldCondition, Filter, MatchValue

_TABLE_KEYWORDS = frozenset({
    "table", "tabella", "column", "colonna", "row", "riga",
    "figure", "figura", "graph", "grafico", "chart", "diagram", "plot",
})


def build_content_type_filter(content_type: str) -> Filter | None:
    """Return a Qdrant Filter matching content_type, or None for 'all'.

    Args:
        content_type: "text" | "table" | "mixed" | "all"

    Returns:
        Filter for Qdrant query_filter / QueryRequest.filter, or None.
    """
    if not content_type or content_type == "all":
        return None
    return Filter(must=[FieldCondition(key="content_type", match=MatchValue(value=content_type))])


def infer_content_type(query: str) -> str | None:
    """Infer content_type constraint from query keywords.

    Returns "table" when the query explicitly references tabular or figure
    content; None otherwise (no filter applied).
    """
    q = query.lower()
    if any(kw in q for kw in _TABLE_KEYWORDS):
        return "table"
    return None
