"""Retrieval evaluation harness (E-03).

Orchestrates: load golden queries -> embed -> search Qdrant -> compute IR metrics -> EvalRun.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
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


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _config_hash(top_k: int, pipeline_mode: str, retrieval_mode: str) -> str:
    params = {
        "embedding_model": cfg.EMBEDDING_MODEL,
        "top_k": top_k,
        "pipeline_mode": pipeline_mode,
        "retrieval_mode": retrieval_mode,
        "qdrant_url": cfg.QDRANT_URL,
    }
    return hashlib.md5(
        json.dumps(params, sort_keys=True).encode()
    ).hexdigest()[:8]


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
    limit: int | None = None,
) -> EvalRun:
    """Run retrieval evaluation on answerable golden queries and compute IR metrics.

    Args:
        dataset_id: "open_ragbench" | "ledger"
        golden_path: path to eval/golden/{dataset_id}.jsonl
        top_k: number of results per query (default: cfg.TOP_K)
        pipeline_mode: "generic" | "routed" | "baseline_c" (routing comes in R-06)
        retrieval_mode: "dense" (E-03) | "sparse" (E-06, lexical-only BM25)
        limit: evaluate only first N answerable queries (for smoke tests)

    Returns:
        EvalRun with metrics dict.
    """
    if top_k is None:
        top_k = cfg.TOP_K

    all_queries = _load_golden(golden_path)
    answerable = [q for q in all_queries if q.answerable and q.dataset_id == dataset_id]
    if limit is not None:
        answerable = answerable[:limit]

    client = get_client(cfg.QDRANT_URL)
    qrels = build_qrels(answerable)
    run: list = []

    texts = [q.query_text for q in answerable]

    if retrieval_mode == "hybrid":
        fetch_k = max(cfg.HYBRID_FETCH_K, top_k)
        dense_vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
        sparse_vecs = encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL)
        dense_all = search_batch(client, dataset_id, dense_vecs, top_k=fetch_k, using="dense")
        sparse_all = search_batch(client, dataset_id, sparse_vecs, top_k=fetch_k, using="sparse")
        for query, dense_hits, sparse_hits in zip(answerable, dense_all, sparse_all):
            payload_map = {h.payload["chunk_id"]: h.payload for h in dense_hits + sparse_hits}
            dense_ids = [h.payload["chunk_id"] for h in dense_hits]
            sparse_ids = [h.payload["chunk_id"] for h in sparse_hits]
            fused = rrf_fuse([dense_ids, sparse_ids], k=cfg.RRF_K, top_n=top_k)
            chunk_ids = [cid for cid, _ in fused]
            scores = [s for _, s in fused]
            run.extend(build_run(query.query_id, chunk_ids, scores))
    elif retrieval_mode == "sparse":
        vecs = encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL)
        results_all = search_batch(client, dataset_id, vecs, top_k=top_k, using="sparse")
        for query, results in zip(answerable, results_all):
            chunk_ids = [p.payload["chunk_id"] for p in results]
            scores = [p.score for p in results]
            run.extend(build_run(query.query_id, chunk_ids, scores))
    else:
        vecs = encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
        results_all = search_batch(client, dataset_id, vecs, top_k=top_k, using="dense")
        for query, results in zip(answerable, results_all):
            chunk_ids = [p.payload["chunk_id"] for p in results]
            scores = [p.score for p in results]
            run.extend(build_run(query.query_id, chunk_ids, scores))

    metrics = compute_metrics(qrels, run, DEFAULT_MEASURES)

    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=_git_commit(),
        config_hash=_config_hash(top_k, pipeline_mode, retrieval_mode),
        dataset_id=dataset_id,
        model="retrieval_only",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode=pipeline_mode,
        metrics=metrics,
    )
