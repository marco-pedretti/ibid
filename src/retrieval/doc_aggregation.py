"""Document-level aggregation over chunk retrieval results (R-05).

Chunk ranking and document ranking are distinct objectives:
  - Chunks are ranked to assemble LLM context (exact text passages).
  - Documents are ranked to build the "file list" shown to the user
    (which source files are relevant, deduplicated by doc_id).

The two lists need not be identical: a document may surface in the file
list even if only one of its many chunks scored well.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocResult:
    """A document entry in the aggregated file list."""
    doc_id: str
    score: float        # aggregated score (max or sum across chunks)
    top_chunk_id: str   # chunk with the highest individual score
    chunk_count: int    # how many chunks from this doc were in the input


def doc_id_from_chunk_id(chunk_id: str) -> str:
    """Extract doc_id from a chunk_id formatted as '{dataset_id}:{doc_id}:{seq}'.

    Uses split(..., 2) so doc_ids that contain colons are handled correctly.
    """
    parts = chunk_id.split(":", 2)
    return parts[1] if len(parts) >= 2 else chunk_id


def aggregate_to_docs(
    chunk_scores: list[tuple[str, float]],
    strategy: str = "max",
) -> list[DocResult]:
    """Aggregate (chunk_id, score) pairs to document-level DocResult list.

    Args:
        chunk_scores: ranked list of (chunk_id, score) from retrieval.
            Assumed to be sorted by score descending (Qdrant output order).
        strategy: "max" — document score = highest chunk score (default);
                  "sum" — document score = sum of all chunk scores.

    Returns:
        List of DocResult sorted by aggregated score descending.
    """
    docs: dict[str, DocResult] = {}

    for chunk_id, score in chunk_scores:
        doc_id = doc_id_from_chunk_id(chunk_id)
        if doc_id not in docs:
            docs[doc_id] = DocResult(
                doc_id=doc_id,
                score=score,
                top_chunk_id=chunk_id,
                chunk_count=1,
            )
        else:
            entry = docs[doc_id]
            entry.chunk_count += 1
            if strategy == "sum":
                entry.score += score
            else:  # max
                if score > entry.score:
                    entry.score = score
                    entry.top_chunk_id = chunk_id

    results = list(docs.values())
    results.sort(key=lambda r: r.score, reverse=True)
    return results
