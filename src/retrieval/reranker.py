"""Cross-encoder reranker using fastembed TextCrossEncoder (R-02).

Takes a query and a list of retrieved chunk payloads, re-scores every
(query, passage) pair with a cross-encoder, and returns the candidates
sorted by the new score.

The model is loaded once and cached in memory for the lifetime of the process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import onnxruntime

# Use DirectML on AMD/Intel/NVIDIA GPUs via DirectX 12 when available;
# fall back to CPU so the reranker runs everywhere.
_PROVIDERS = (
    ["DmlExecutionProvider", "CPUExecutionProvider"]
    if "DmlExecutionProvider" in onnxruntime.get_available_providers()
    else ["CPUExecutionProvider"]
)


@dataclass
class RankedResult:
    """Reranked retrieval result compatible with the harness (.payload / .score)."""

    payload: dict
    score: float


_model_cache: dict[str, Any] = {}


def _get_reranker(model_name: str) -> Any:
    if model_name not in _model_cache:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _model_cache[model_name] = TextCrossEncoder(model_name=model_name, providers=_PROVIDERS)
    return _model_cache[model_name]


def rerank(
    query: str,
    candidates: list[dict],
    model_name: str,
    top_n: int | None = None,
) -> list[RankedResult]:
    """Re-score candidates with a cross-encoder and return sorted results.

    Args:
        query: The query string.
        candidates: List of chunk payload dicts — must include a ``"text"`` key.
        model_name: fastembed cross-encoder model name (e.g. BAAI/bge-reranker-v2-m3).
        top_n: Number of results to return; ``None`` returns all candidates.

    Returns:
        Candidates re-sorted descending by cross-encoder score.
    """
    if not candidates:
        return []

    encoder = _get_reranker(model_name)
    texts = [c["text"] for c in candidates]
    scores = list(encoder.rerank(query=query, documents=texts))

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    if top_n is not None:
        ranked = ranked[:top_n]

    return [RankedResult(payload=p, score=float(s)) for p, s in ranked]
