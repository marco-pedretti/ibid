"""IR metrics computation via ir_measures (E-03).

Wraps ir_measures to compute recall@k, nDCG@k, MRR, success@1 from
GoldenQuery objects and Qdrant search results.
"""

from __future__ import annotations

import ir_measures
from ir_measures import MRR, Recall, Success, nDCG

from src.datasets.golden import GoldenQuery

# Measures reported in every retrieval EvalRun
DEFAULT_MEASURES = [
    Recall @ 5,
    Recall @ 10,
    nDCG @ 10,
    MRR @ 10,
    Success @ 1,
]


def _required_depth(measures: list) -> int:
    """Deepest cutoff any measure asks for.

    Derived from the measure list rather than hardcoded, so adding e.g. nDCG@20
    to DEFAULT_MEASURES automatically deepens retrieval instead of silently
    producing a truncated number.
    """
    depths = [int(str(m).rsplit("@", 1)[1]) for m in measures if "@" in str(m)]
    return max(depths) if depths else 1


#: Retrieval must return at least this many results for DEFAULT_MEASURES to mean
#: what their names say.  Runs before 2026-08-07 fetched only `top_k` (5), so
#: their R@10/nDCG@10/RR@10 were computed over 5 documents and could not see
#: positions 6-10 — measured understatement of R@10: 0.78 vs 0.86.  See
#: eval/results/archive/README.md.
METRIC_DEPTH = _required_depth(DEFAULT_MEASURES)


def build_qrels(queries: list[GoldenQuery]) -> list[ir_measures.Qrel]:
    """Convert answerable GoldenQuery objects to ir_measures Qrel list.

    Only answerable queries with relevance > 0 contribute to qrels.
    Unanswerable queries (answerable=False) are excluded — they have no
    correct answer and should not penalise recall.
    """
    qrels = []
    for q in queries:
        if not q.answerable:
            continue
        for qr in q.qrels:
            if qr.relevance > 0:
                qrels.append(
                    ir_measures.Qrel(
                        query_id=q.query_id,
                        doc_id=qr.chunk_id,
                        relevance=qr.relevance,
                    )
                )
    return qrels


def build_run(
    query_id: str,
    chunk_ids: list[str],
    scores: list[float],
) -> list[ir_measures.ScoredDoc]:
    """Convert a ranked list of chunk_ids + scores to ir_measures ScoredDoc list."""
    return [
        ir_measures.ScoredDoc(query_id=query_id, doc_id=cid, score=score)
        for cid, score in zip(chunk_ids, scores)
    ]


def compute_metrics(
    qrels: list[ir_measures.Qrel],
    run: list[ir_measures.ScoredDoc],
    measures: list | None = None,
) -> dict[str, float]:
    """Compute aggregate IR metrics over all queries.

    Returns a dict with measure names as keys (e.g. "nDCG@10", "R@5").
    Queries with no retrieved results contribute 0 to recall-based measures.
    """
    if measures is None:
        measures = DEFAULT_MEASURES
    if not run:
        return {str(m): 0.0 for m in measures}

    agg = ir_measures.calc_aggregate(measures, qrels, run)
    return {str(m): float(v) for m, v in agg.items()}
