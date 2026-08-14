"""The three retrieval modes, in one shape.

Extracted from `harness.py`, where they were private helpers.  They stopped
being private the moment a second consumer appeared: `scripts/compare_runs.py`
already imported `_RETRIEVERS` through the underscore, and the C-01 citation
harness needs the same candidates — with their payloads — to build a prompt.

`Candidates` is what every mode returns, so whatever follows retrieval (metric
scoring, reranking, prompt building) is written once instead of once per mode.

**Stava in `src/eval/`, ed e' stato spostato qui da A-02.** La collocazione
descriveva il primo chiamante, non la funzione: questo *e'* il retrieval, e da
A-01 lo attraversa anche il percorso di servizio.  Una richiesta HTTP che per
recuperare dei chunk deve passare dal pacchetto di valutazione ha il verso delle
dipendenze rovesciato — la valutazione consuma la pipeline, non viceversa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import src.config as cfg
from src.index.embed import encode, encode_sparse_query
from src.index.store import search_batch
from src.retrieval.hybrid import rrf_fuse


@dataclass
class Candidates:
    """One query's ranked candidates, in the same shape whatever mode produced them.

    The three retrieval modes used to each carry their own copy of the scoring
    loop that follows them — dense and sparse were identical character for
    character.  Normalising the output here leaves one loop instead of three.
    """

    chunk_ids: list[str]
    scores: list[float]
    payloads: list[dict]


def points_to_candidates(points: list) -> Candidates:
    return Candidates(
        chunk_ids=[p.payload["chunk_id"] for p in points],
        scores=[p.score for p in points],
        payloads=[p.payload for p in points],
    )


def retrieve_dense(client, collection, texts, fetch_k, filters) -> list[Candidates]:
    print(f"  Embedding {len(texts)} queries...", flush=True)
    t0 = time.time()
    vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    print(f"  Embeddings done in {time.time() - t0:.1f}s", flush=True)
    hits = search_batch(client, collection, vecs, top_k=fetch_k,
                        using="dense", filters=filters)
    return [points_to_candidates(h) for h in hits]


def retrieve_sparse(client, collection, texts, fetch_k, filters) -> list[Candidates]:
    vecs = encode_sparse_query(texts, cfg.SPARSE_EMBEDDING_MODEL)
    hits = search_batch(client, collection, vecs, top_k=fetch_k,
                        using="sparse", filters=filters)
    return [points_to_candidates(h) for h in hits]


def retrieve_hybrid(client, collection, texts, fetch_k, filters) -> list[Candidates]:
    """Dense and sparse fused with RRF (R-01).

    Fetches at least HYBRID_FETCH_K from each index so the fusion has something
    to work with even when fetch_k is small.
    """
    hybrid_fetch = max(cfg.HYBRID_FETCH_K, fetch_k)
    print(f"  Embedding {len(texts)} queries (dense)...", flush=True)
    t0 = time.time()
    dense_vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    print(f"  Dense embeddings done in {time.time() - t0:.1f}s", flush=True)
    sparse_vecs = encode_sparse_query(texts, cfg.SPARSE_EMBEDDING_MODEL)

    dense_all = search_batch(client, collection, dense_vecs, top_k=hybrid_fetch,
                             using="dense", filters=filters)
    sparse_all = search_batch(client, collection, sparse_vecs, top_k=hybrid_fetch,
                              using="sparse", filters=filters)

    out: list[Candidates] = []
    for dense_hits, sparse_hits in zip(dense_all, sparse_all):
        payload_map = {h.payload["chunk_id"]: h.payload
                       for h in list(dense_hits) + list(sparse_hits)}
        fused = rrf_fuse(
            [[h.payload["chunk_id"] for h in dense_hits],
             [h.payload["chunk_id"] for h in sparse_hits]],
            k=cfg.RRF_K, top_n=fetch_k,
        )
        out.append(Candidates(
            chunk_ids=[cid for cid, _ in fused],
            scores=[s for _, s in fused],
            payloads=[payload_map[cid] for cid, _ in fused],
        ))
    return out


#: Mode name -> retriever.  The keys are the accepted values of
#: `--retrieval-mode` everywhere in the repo.
RETRIEVERS = {
    "dense": retrieve_dense,
    "sparse": retrieve_sparse,
    "hybrid": retrieve_hybrid,
}
