"""Hybrid dense+sparse retrieval with Reciprocal Rank Fusion (R-01).

RRF fuses two ranked lists into a single ranking without requiring score
normalization across embedding spaces.

Formula: score(d) = Σ_i 1 / (k + rank_i(d))
  where rank is 1-based and k is a smoothing constant (default 60).
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector

from src.index.store import search


@dataclass
class HybridResult:
    """Minimal search result compatible with the harness (.payload / .score)."""

    payload: dict
    score: float


def rrf_fuse(
    ranked_lists: list[list[str]],
    k: int = 60,
    top_n: int | None = None,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion over multiple ranked lists of chunk IDs.

    Args:
        ranked_lists: Each inner list is chunk_ids sorted by descending score.
        k: Smoothing constant — higher k reduces the impact of top ranks.
        top_n: If given, return only the top_n results.

    Returns:
        List of (chunk_id, rrf_score) sorted descending by score.
    """
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if top_n is not None:
        fused = fused[:top_n]
    return fused


def hybrid_search(
    client: QdrantClient,
    collection: str,
    dense_vec: list[float],
    sparse_vec: SparseVector,
    top_k: int,
    rrf_k: int = 60,
    fetch_k: int = 20,
) -> list[HybridResult]:
    """Query both dense and sparse indexes, fuse with RRF, return top_k results.

    Args:
        client: Qdrant client.
        collection: Collection name (dataset_id).
        dense_vec: Dense embedding for the query.
        sparse_vec: Sparse BM25 vector for the query.
        top_k: Number of results to return after fusion.
        rrf_k: RRF smoothing constant.
        fetch_k: Number of candidates to fetch from each index before fusion.
                 Clamped to max(fetch_k, top_k) to avoid missing results.

    Returns:
        List of HybridResult ordered by RRF score descending.
    """
    fetch_k = max(fetch_k, top_k)

    dense_hits = search(client, collection, dense_vec, top_k=fetch_k, using="dense")
    sparse_hits = search(client, collection, sparse_vec, top_k=fetch_k, using="sparse")

    payload_map: dict[str, dict] = {}
    for hit in dense_hits + sparse_hits:
        cid = hit.payload["chunk_id"]
        if cid not in payload_map:
            payload_map[cid] = hit.payload

    dense_ids = [h.payload["chunk_id"] for h in dense_hits]
    sparse_ids = [h.payload["chunk_id"] for h in sparse_hits]

    fused = rrf_fuse([dense_ids, sparse_ids], k=rrf_k, top_n=top_k)

    return [HybridResult(payload=payload_map[cid], score=score) for cid, score in fused]
