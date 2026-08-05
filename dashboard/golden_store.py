"""Helpers for loading and querying golden query sets in the dashboard.

Separated from app.py for testability — no Streamlit dependency.
"""
from __future__ import annotations

from pathlib import Path

from src.datasets.golden import GoldenQuery


def load_golden_queries(path: Path) -> list[GoldenQuery]:
    """Load a golden JSONL file. Returns empty list if path doesn't exist."""
    if not path.exists():
        return []
    queries: list[GoldenQuery] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            queries.append(GoldenQuery.model_validate_json(line))
        except Exception:
            continue
    return queries


def filter_queries(
    queries: list[GoldenQuery],
    answerable: bool | None = None,
    search: str = "",
) -> list[GoldenQuery]:
    """Filter queries by answerable flag and/or search text (case-insensitive)."""
    result = queries
    if answerable is not None:
        result = [q for q in result if q.answerable == answerable]
    if search:
        s = search.lower()
        result = [q for q in result if s in q.query_text.lower()]
    return result


def example_queries(queries: list[GoldenQuery], n: int = 6) -> list[str]:
    """Return up to n query texts from answerable queries that have qrels."""
    candidates = [q for q in queries if q.answerable and q.qrels]
    return [q.query_text for q in candidates[:n]]


def recall_at_k(query: GoldenQuery, retrieved_chunk_ids: list[str], k: int) -> float:
    """Fraction of relevant chunks found in the top-k retrieved results."""
    relevant = {qr.chunk_id for qr in query.qrels if qr.relevance >= 1}
    if not relevant:
        return 0.0
    found = relevant & set(retrieved_chunk_ids[:k])
    return len(found) / len(relevant)
