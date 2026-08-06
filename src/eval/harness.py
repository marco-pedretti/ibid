"""Retrieval evaluation harness (E-03).

Orchestrates: load golden queries -> embed -> search Qdrant -> compute IR metrics -> EvalRun.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import src.config as cfg
from src.datasets.golden import GoldenQuery
from src.datasets.schema import EvalRun
from src.eval.metrics import DEFAULT_MEASURES, build_qrels, build_run, compute_metrics
from src.index.embed import encode, encode_sparse
from src.index.store import get_client, search_batch
from src.retrieval.hybrid import rrf_fuse
from src.retrieval.metadata_filter import build_content_type_filter, infer_content_type
from src.retrieval.query_rewrite import rewrite_batch
from src.retrieval.reranker import rerank as cross_encode


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _config_hash(
    top_k: int,
    pipeline_mode: str,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
) -> str:
    params = {
        "embedding_model": cfg.EMBEDDING_MODEL,
        "top_k": top_k,
        "pipeline_mode": pipeline_mode,
        "retrieval_mode": retrieval_mode,
        "qdrant_url": cfg.QDRANT_URL,
    }
    if rerank:
        params["reranker_model"] = cfg.RERANKER_MODEL
    if query_rewrite:
        params["query_rewrite_model"] = cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL
    if filter_content_type:
        params["filter_content_type"] = filter_content_type
    return hashlib.md5(
        json.dumps(params, sort_keys=True).encode()
    ).hexdigest()[:8]


def _progress(i: int, total: int, t0: float, label: str = "") -> None:
    elapsed = time.time() - t0
    rate = i / elapsed if elapsed > 0 else 0
    eta = (total - i) / rate if rate > 0 else 0
    suffix = f"  {label}" if label else ""
    print(
        f"  [{i}/{total}] elapsed {elapsed:.0f}s  ETA {eta:.0f}s{suffix}",
        flush=True,
    )


def _load_golden(path: Path) -> list[GoldenQuery]:
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(GoldenQuery.model_validate_json(line))
    return queries


def run_retrieval_eval(
    dataset_id: str,
    golden_path: Path,
    top_k: int | None = None,
    pipeline_mode: str = "generic",
    retrieval_mode: str = "dense",
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    limit: int | None = None,
) -> EvalRun:
    """Run retrieval evaluation on answerable golden queries and compute IR metrics.

    Args:
        dataset_id: "open_ragbench" | "ledger"
        golden_path: path to eval/golden/{dataset_id}.jsonl
        top_k: number of results per query (default: cfg.TOP_K)
        pipeline_mode: "generic" | "routed" | "baseline_c" | "dense_reranked" | …
        retrieval_mode: "dense" | "sparse" | "hybrid"
        rerank: if True, apply cross-encoder reranking after initial retrieval (R-02)
        query_rewrite: if True, rewrite queries with LLM before embedding (R-03)
        filter_content_type: "text" | "table" | "mixed" | "auto" | None.
            "auto" infers the filter per query from keywords (R-04).
        limit: evaluate only first N answerable queries (for smoke tests)

    Returns:
        EvalRun with metrics dict.
    """
    if top_k is None:
        top_k = cfg.TOP_K

    # When reranking, fetch a larger initial candidate pool so the cross-encoder
    # has more to choose from before truncating to top_k.
    rerank_fetch_k = max(cfg.RERANK_FETCH_K, top_k) if rerank else top_k

    all_queries = _load_golden(golden_path)
    answerable = [q for q in all_queries if q.answerable and q.dataset_id == dataset_id]
    if limit is not None:
        answerable = answerable[:limit]

    client = get_client(cfg.QDRANT_URL)
    qrels = build_qrels(answerable)
    run: list = []
    n = len(answerable)
    report_every = max(1, n // 10)

    raw_texts = [q.query_text for q in answerable]
    if query_rewrite:
        print(f"  Rewriting {n} queries...", flush=True)
        t_rw = time.time()
        texts = rewrite_batch(
            raw_texts,
            base_url=cfg.LLM_BASE_URL,
            model=cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL,
        )
        print(f"  Rewriting done in {time.time() - t_rw:.1f}s", flush=True)
    else:
        texts = raw_texts

    # Build per-query filters (R-04): None list means no filter applied.
    if filter_content_type == "auto":
        query_filters = [
            build_content_type_filter(ct) if (ct := infer_content_type(t)) else None
            for t in texts
        ]
    elif filter_content_type:
        f = build_content_type_filter(filter_content_type)
        query_filters: list | None = [f] * n
    else:
        query_filters = None

    if retrieval_mode == "hybrid":
        hybrid_fetch = max(cfg.HYBRID_FETCH_K, rerank_fetch_k)
        print(f"  Embedding {n} queries (dense)...", flush=True)
        t_enc = time.time()
        dense_vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
        print(f"  Dense embeddings done in {time.time() - t_enc:.1f}s", flush=True)
        sparse_vecs = encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL)
        dense_all = search_batch(client, dataset_id, dense_vecs, top_k=hybrid_fetch, using="dense", filters=query_filters)
        sparse_all = search_batch(client, dataset_id, sparse_vecs, top_k=hybrid_fetch, using="sparse", filters=query_filters)
        print(f"  Retrieval done, {'reranking' if rerank else 'fusing'} {n} queries...", flush=True)
        t0 = time.time()
        for i, (query, dense_hits, sparse_hits) in enumerate(zip(answerable, dense_all, sparse_all), 1):
            payload_map = {h.payload["chunk_id"]: h.payload for h in dense_hits + sparse_hits}
            dense_ids = [h.payload["chunk_id"] for h in dense_hits]
            sparse_ids = [h.payload["chunk_id"] for h in sparse_hits]
            fused = rrf_fuse([dense_ids, sparse_ids], k=cfg.RRF_K, top_n=rerank_fetch_k)
            if rerank:
                payloads = [payload_map[cid] for cid, _ in fused]
                reranked = cross_encode(query.query_text, payloads, cfg.RERANKER_MODEL, top_n=top_k)
                chunk_ids = [r.payload["chunk_id"] for r in reranked]
                scores = [r.score for r in reranked]
            else:
                chunk_ids = [cid for cid, _ in fused]
                scores = [s for _, s in fused]
            run.extend(build_run(query.query_id, chunk_ids, scores))
            if i % report_every == 0 or i == n:
                _progress(i, n, t0)
    elif retrieval_mode == "sparse":
        vecs = encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL)
        results_all = search_batch(client, dataset_id, vecs, top_k=rerank_fetch_k, using="sparse", filters=query_filters)
        print(f"  Retrieval done, {'reranking' if rerank else 'scoring'} {n} queries...", flush=True)
        t0 = time.time()
        for i, (query, results) in enumerate(zip(answerable, results_all), 1):
            if rerank:
                payloads = [p.payload for p in results]
                reranked = cross_encode(query.query_text, payloads, cfg.RERANKER_MODEL, top_n=top_k)
                chunk_ids = [r.payload["chunk_id"] for r in reranked]
                scores = [r.score for r in reranked]
            else:
                chunk_ids = [p.payload["chunk_id"] for p in results]
                scores = [p.score for p in results]
            run.extend(build_run(query.query_id, chunk_ids, scores))
            if i % report_every == 0 or i == n:
                _progress(i, n, t0)
    else:  # dense
        print(f"  Embedding {n} queries...", flush=True)
        t_enc = time.time()
        vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
        print(f"  Embeddings done in {time.time() - t_enc:.1f}s", flush=True)
        results_all = search_batch(client, dataset_id, vecs, top_k=rerank_fetch_k, using="dense", filters=query_filters)
        print(f"  Retrieval done, {'reranking' if rerank else 'scoring'} {n} queries...", flush=True)
        t0 = time.time()
        for i, (query, results) in enumerate(zip(answerable, results_all), 1):
            if rerank:
                payloads = [p.payload for p in results]
                reranked = cross_encode(query.query_text, payloads, cfg.RERANKER_MODEL, top_n=top_k)
                chunk_ids = [r.payload["chunk_id"] for r in reranked]
                scores = [r.score for r in reranked]
            else:
                chunk_ids = [p.payload["chunk_id"] for p in results]
                scores = [p.score for p in results]
            run.extend(build_run(query.query_id, chunk_ids, scores))
            if i % report_every == 0 or i == n:
                _progress(i, n, t0)

    metrics = compute_metrics(qrels, run, DEFAULT_MEASURES)

    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=_git_commit(),
        config_hash=_config_hash(top_k, pipeline_mode, retrieval_mode, rerank, query_rewrite, filter_content_type),
        dataset_id=dataset_id,
        model="retrieval_only",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode=pipeline_mode,
        metrics=metrics,
    )
