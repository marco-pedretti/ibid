"""Batch retrieval over a golden set, ranked worst-first.

The old Golden Query Browser showed the first 500 queries in file order and made
you click a button per query to see retrieval.  Queries that succeed teach
nothing; this module runs a batch and sorts by failure so the ones that broke
surface first.

Both chunk-level and document-level recall are computed.  They answer different
questions and can disagree loudly: a routed collection re-chunks the corpus, so
its chunk_ids never match the qrels and chunk recall is structurally 0 while doc
recall is meaningful.  Reporting only one of them is how that gets misread.

No Streamlit import: testable without a running app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import src.config as cfg
from src.datasets.golden import GoldenQuery
from src.index.embed import encode, encode_sparse
from src.index.store import search_batch
from src.retrieval.doc_aggregation import doc_id_from_chunk_id
from src.retrieval.hybrid import rrf_fuse
from src.retrieval.reranker import rerank as cross_encode

from dashboard.retrieval_probe import ProbeConfig


@dataclass
class QueryOutcome:
    """What one golden query got back, and whether it was right."""

    query: GoldenQuery
    retrieved_ids: list[str]
    payloads: list[dict] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    recall: float = 0.0
    doc_recall: float = 0.0

    @property
    def golden_ids(self) -> set[str]:
        return {qr.chunk_id for qr in self.query.qrels if qr.relevance >= 1}

    @property
    def golden_docs(self) -> set[str]:
        return {doc_id_from_chunk_id(c) for c in self.golden_ids}

    @property
    def is_failure(self) -> bool:
        """Nothing relevant retrieved, at either granularity."""
        return self.doc_recall == 0.0

    @property
    def top_score(self) -> float:
        return self.scores[0] if self.scores else 0.0


def _recall(relevant: set[str], retrieved: list[str]) -> float:
    if not relevant:
        return 0.0
    return len(relevant & set(retrieved)) / len(relevant)


def score_outcome(outcome: QueryOutcome) -> QueryOutcome:
    """Fill in chunk-level and document-level recall."""
    outcome.recall = _recall(outcome.golden_ids, outcome.retrieved_ids)
    retrieved_docs = [doc_id_from_chunk_id(c) for c in outcome.retrieved_ids if c]
    outcome.doc_recall = _recall(outcome.golden_docs, retrieved_docs)
    return outcome


def evaluate_queries(
    client,
    queries: list[GoldenQuery],
    config: ProbeConfig,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[QueryOutcome]:
    """Run `queries` against `config.collection` and score each one.

    Embedding and search are batched (one round trip per 256 queries) because
    doing this one query at a time on DirectML is slow enough to make the page
    unusable.  Reranking, when enabled, is necessarily per-query.
    """
    if not queries:
        return []

    texts = [q.query_text for q in queries]
    fetch_k = max(cfg.RERANK_FETCH_K, config.top_k) if config.rerank else config.top_k

    if config.retrieval_mode == "hybrid":
        hybrid_fetch = max(cfg.HYBRID_FETCH_K, fetch_k)
        dense_all = search_batch(
            client, config.collection,
            encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH),
            top_k=hybrid_fetch, using="dense",
        )
        sparse_all = search_batch(
            client, config.collection,
            encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL),
            top_k=hybrid_fetch, using="sparse",
        )
        results_all = []
        for dense_hits, sparse_hits in zip(dense_all, sparse_all):
            payload_map = {
                (h.payload or {}).get("chunk_id", ""): (h.payload or {})
                for h in list(dense_hits) + list(sparse_hits)
            }
            fused = rrf_fuse(
                [
                    [(h.payload or {}).get("chunk_id", "") for h in dense_hits],
                    [(h.payload or {}).get("chunk_id", "") for h in sparse_hits],
                ],
                k=cfg.RRF_K, top_n=fetch_k,
            )
            results_all.append(
                [(cid, score, payload_map.get(cid, {})) for cid, score in fused]
            )
    else:
        if config.retrieval_mode == "sparse":
            vecs = encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL)
        else:
            vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
        raw = search_batch(
            client, config.collection, vecs, top_k=fetch_k, using=config.retrieval_mode
        )
        results_all = [
            [((h.payload or {}).get("chunk_id", ""), h.score, h.payload or {}) for h in hits]
            for hits in raw
        ]

    outcomes: list[QueryOutcome] = []
    total = len(queries)
    for i, (query, triples) in enumerate(zip(queries, results_all), 1):
        if config.rerank:
            reranked = cross_encode(
                query.query_text, [p for _, _, p in triples],
                cfg.RERANKER_MODEL, top_n=config.top_k,
            )
            triples = [
                ((r.payload or {}).get("chunk_id", ""), r.score, r.payload or {})
                for r in reranked
            ]
        triples = triples[: config.top_k]
        outcomes.append(
            score_outcome(
                QueryOutcome(
                    query=query,
                    retrieved_ids=[c for c, _, _ in triples],
                    scores=[s for _, s, _ in triples],
                    payloads=[p for _, _, p in triples],
                )
            )
        )
        if on_progress:
            on_progress(i, total)

    return outcomes


def sort_by_failure(outcomes: list[QueryOutcome]) -> list[QueryOutcome]:
    """Worst first: lowest doc recall, then lowest chunk recall."""
    return sorted(outcomes, key=lambda o: (o.doc_recall, o.recall))


def failure_summary(outcomes: list[QueryOutcome]) -> dict[str, float]:
    """Aggregate over one dataset only — never mix datasets here (§11)."""
    n = len(outcomes)
    if n == 0:
        return {"n": 0, "mean_recall": 0.0, "mean_doc_recall": 0.0,
                "n_failures": 0, "failure_rate": 0.0}
    n_fail = sum(1 for o in outcomes if o.is_failure)
    return {
        "n": n,
        "mean_recall": sum(o.recall for o in outcomes) / n,
        "mean_doc_recall": sum(o.doc_recall for o in outcomes) / n,
        "n_failures": n_fail,
        "failure_rate": n_fail / n,
    }


def chunk_id_mismatch(outcomes: list[QueryOutcome]) -> bool:
    """True when chunk recall is structurally zero but documents are found.

    Signals that the collection was built with a different chunking pipeline
    than the one the qrels were written against — the R-07 situation.  Without
    this check a routed collection just looks catastrophically broken.
    """
    if not outcomes:
        return False
    return (
        all(o.recall == 0.0 for o in outcomes)
        and any(o.doc_recall > 0.0 for o in outcomes)
    )
