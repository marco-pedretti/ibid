"""Single-query retrieval, for interactive debugging.

Why this is not `src/eval/harness.py`: the harness embeds thousands of queries
in one batch, streams progress, and reports IR metrics.  The dashboard needs the
opposite — one query, every intermediate result kept, no metrics.  Sharing the
code would mean bending the harness around a case it does not have.

What it does share is the *ordering semantics* (RRF fusion parameters, rerank
fetch depth), so that what you see here is what the eval measured.  Those come
from `src.config`, not from local constants — if they ever diverge, the config
is the bug.

No Streamlit import: testable without a running app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import src.config as cfg
from src.index.embed import encode, encode_sparse
from src.index.store import search
from src.retrieval.hybrid import rrf_fuse
from src.retrieval.reranker import rerank as cross_encode

RETRIEVAL_MODES = ("dense", "sparse", "hybrid")


@dataclass(frozen=True)
class ProbeConfig:
    """One retrieval configuration to run a query against."""

    collection: str
    retrieval_mode: str = "dense"
    rerank: bool = False
    top_k: int = 5

    def label(self) -> str:
        parts = [self.collection, self.retrieval_mode]
        if self.rerank:
            parts.append("rerank")
        return " · ".join(parts)


@dataclass
class ProbeHit:
    rank: int  # 1-based
    chunk_id: str
    score: float
    payload: dict[str, Any]


def list_collections(client) -> list[str]:
    """Collection names present in Qdrant, sorted.

    The dashboard used to hardcode ["open_ragbench", "ledger"], which made the
    R-07 `*_routed` collections unreachable from the only tool built to inspect
    them.  Ask the server instead.
    """
    return sorted(c.name for c in client.get_collections().collections)


def dataset_of_collection(collection: str, known_datasets: tuple[str, ...]) -> str:
    """Map a collection name back to the dataset whose golden set describes it.

    "ledger_routed" -> "ledger".  Longest match wins so a hypothetical
    "ledger_v2" dataset would not be swallowed by "ledger".
    """
    for ds in sorted(known_datasets, key=len, reverse=True):
        if collection == ds or collection.startswith(ds + "_"):
            return ds
    return collection


def fetch_chunks_by_id(client, collection: str, chunk_ids: list[str]) -> dict[str, dict]:
    """Look up chunk payloads by their `chunk_id` field.

    Needed to show what the qrels actually point at.  Showing only the id (as
    the old golden browser did) makes it impossible to tell a bad retrieval from
    a bad label — the two demand opposite fixes.

    Returns {chunk_id: payload}; ids absent from the collection are simply
    missing from the result, which is itself the answer when a golden chunk_id
    does not exist in the collection being queried.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    if not chunk_ids:
        return {}
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="chunk_id", match=MatchAny(any=list(chunk_ids)))]
        ),
        limit=len(chunk_ids),
        with_payload=True,
    )
    return {(p.payload or {}).get("chunk_id", ""): (p.payload or {}) for p in points}


def _to_hits(points: list, start_rank: int = 1) -> list[ProbeHit]:
    return [
        ProbeHit(
            rank=start_rank + i,
            chunk_id=(p.payload or {}).get("chunk_id", ""),
            score=p.score,
            payload=p.payload or {},
        )
        for i, p in enumerate(points)
    ]


def probe(client, query_text: str, config: ProbeConfig) -> list[ProbeHit]:
    """Run one query against one collection and return ranked hits.

    Mirrors the harness paths: sparse uses BM25, hybrid fuses dense+sparse with
    RRF, and reranking re-scores a deeper candidate pool before truncation.
    """
    fetch_k = max(cfg.RERANK_FETCH_K, config.top_k) if config.rerank else config.top_k

    if config.retrieval_mode == "hybrid":
        hybrid_fetch = max(cfg.HYBRID_FETCH_K, fetch_k)
        dense_vec = encode([query_text], cfg.EMBEDDING_MODEL, batch_size=1)[0]
        sparse_vec = encode_sparse([query_text], cfg.SPARSE_EMBEDDING_MODEL)[0]
        dense_pts = search(client, config.collection, dense_vec, top_k=hybrid_fetch, using="dense")
        sparse_pts = search(client, config.collection, sparse_vec, top_k=hybrid_fetch, using="sparse")
        payload_map = {
            (p.payload or {}).get("chunk_id", ""): (p.payload or {})
            for p in list(dense_pts) + list(sparse_pts)
        }
        fused = rrf_fuse(
            [
                [(p.payload or {}).get("chunk_id", "") for p in dense_pts],
                [(p.payload or {}).get("chunk_id", "") for p in sparse_pts],
            ],
            k=cfg.RRF_K,
            top_n=fetch_k,
        )
        hits = [
            ProbeHit(rank=i, chunk_id=cid, score=score, payload=payload_map.get(cid, {}))
            for i, (cid, score) in enumerate(fused, 1)
        ]
    else:
        if config.retrieval_mode == "sparse":
            vec = encode_sparse([query_text], cfg.SPARSE_EMBEDDING_MODEL)[0]
        else:
            vec = encode([query_text], cfg.EMBEDDING_MODEL, batch_size=1)[0]
        points = search(
            client, config.collection, vec, top_k=fetch_k, using=config.retrieval_mode
        )
        hits = _to_hits(list(points))

    if config.rerank:
        reranked = cross_encode(
            query_text, [h.payload for h in hits], cfg.RERANKER_MODEL, top_n=config.top_k
        )
        hits = [
            ProbeHit(
                rank=i,
                chunk_id=(r.payload or {}).get("chunk_id", ""),
                score=r.score,
                payload=r.payload or {},
            )
            for i, r in enumerate(reranked, 1)
        ]

    return hits[: config.top_k]


@dataclass
class ProbeComparison:
    """How two result lists differ — the actual question in an A/B."""

    shared: list[str]
    only_a: list[str]
    only_b: list[str]
    shared_docs: list[str]
    jaccard: float
    doc_jaccard: float


def _doc_of(chunk_id: str) -> str:
    from src.retrieval.doc_aggregation import doc_id_from_chunk_id

    return doc_id_from_chunk_id(chunk_id)


def compare_hits(a: list[ProbeHit], b: list[ProbeHit]) -> ProbeComparison:
    """Overlap between two probes, at chunk level and at document level.

    Document level matters because a routed collection re-chunks everything:
    chunk_ids never match across the two, so chunk overlap is always 0 and only
    doc overlap says whether the same source was found.  This is the same reason
    R-07 had to be read on doc_R@5.
    """
    ids_a = [h.chunk_id for h in a]
    ids_b = [h.chunk_id for h in b]
    set_a, set_b = set(ids_a), set(ids_b)
    docs_a = {_doc_of(c) for c in ids_a if c}
    docs_b = {_doc_of(c) for c in ids_b if c}

    def _jac(x: set, y: set) -> float:
        union = x | y
        return len(x & y) / len(union) if union else 0.0

    return ProbeComparison(
        shared=[c for c in ids_a if c in set_b],
        only_a=[c for c in ids_a if c not in set_b],
        only_b=[c for c in ids_b if c not in set_a],
        shared_docs=sorted(docs_a & docs_b),
        jaccard=_jac(set_a, set_b),
        doc_jaccard=_jac(docs_a, docs_b),
    )
