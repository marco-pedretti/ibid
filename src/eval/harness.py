"""Retrieval evaluation harness (E-03).

Orchestrates: load golden queries -> embed -> search Qdrant -> compute IR metrics -> EvalRun.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import src.config as cfg
from ir_measures import Recall
from src.datasets.golden import GoldenQuery
from src.datasets.schema import EvalRun
from src.eval.metrics import (
    DEFAULT_MEASURES,
    METRIC_DEPTH,
    build_qrels,
    build_run,
    compute_metrics,
)
from src.eval.provenance import git_commit, load_golden
from src.eval.retrieval_backends import RETRIEVERS
from src.eval.run_config import build_config
from src.index.store import get_client
import ir_measures

from src.retrieval.doc_aggregation import doc_id_from_chunk_id
from src.retrieval.metadata_filter import build_content_type_filter, infer_content_type
from src.retrieval.query_rewrite import rewrite_batch
from src.retrieval.reranker import rerank as cross_encode


def _build_doc_qrels(answerable: list[GoldenQuery]) -> list[ir_measures.Qrel]:
    """Derive document-level qrels from chunk-level qrels.

    A document is relevant at the max relevance of any of its chunks.
    """
    best: dict[tuple[str, str], int] = {}  # (query_id, doc_id) -> max relevance
    for q in answerable:
        for qr in q.qrels:
            if qr.relevance > 0:
                doc_id = doc_id_from_chunk_id(qr.chunk_id)
                key = (q.query_id, doc_id)
                best[key] = max(best.get(key, 0), qr.relevance)
    return [
        ir_measures.Qrel(query_id=qid, doc_id=did, relevance=rel)
        for (qid, did), rel in best.items()
    ]


def _build_doc_run(chunk_run: list[ir_measures.ScoredDoc]) -> list[ir_measures.ScoredDoc]:
    """Aggregate chunk-level ScoredDoc run to document-level via max-pooling.

    Multiple chunks from the same document in the same query are collapsed to
    the one with the highest score.  Result is sorted by score within each query.
    """
    from collections import defaultdict

    best: dict[tuple[str, str], float] = {}  # (query_id, doc_id) -> max score
    for sd in chunk_run:
        doc_id = doc_id_from_chunk_id(sd.doc_id)
        key = (sd.query_id, doc_id)
        if key not in best or sd.score > best[key]:
            best[key] = sd.score

    by_query: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (qid, did), score in best.items():
        by_query[qid].append((did, score))

    doc_run: list[ir_measures.ScoredDoc] = []
    for qid, items in by_query.items():
        items.sort(key=lambda x: x[1], reverse=True)
        for did, score in items:
            doc_run.append(ir_measures.ScoredDoc(query_id=qid, doc_id=did, score=score))
    return doc_run


def _config_hash(
    top_k: int,
    pipeline_mode: str,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
    collection: str | None = None,
    dataset_id: str | None = None,
    eval_depth: int | None = None,
) -> str:
    """Stable identity of a config: same hash means directly comparable numbers.

    Changed three times.  On 2026-08-07 by adding `eval_depth`, and on
    2026-08-13 by adding `sparse_idf` (R-08) and `sparse_query_embed` (R-09).
    The rule against touching this function exists so that a silent change
    cannot make old and new runs look comparable when they are not — and that is
    exactly why all three changes were required rather than forbidden: fixing
    the retrieval depth altered R@10/nDCG@10/RR@10, and each half of OQ-03
    altered every sparse score, so pre-fix runs must *not* share a hash with
    post-fix ones.  Archived runs keep their original hashes; the archive is
    read-only (see eval/results/archive/README.md).

    Contrast with `n_queries` below, which looks like the same case and is not.
    The IDF modifier changes *what the system computes*; the query count changes
    only how precisely we observe it.  The first has to split the identity, the
    second must not — see the docstring of `citation_harness._config_hash`.

    The human-readable flag dict lives in `EvalRun.config` — see
    `src/eval/run_config.py`.  Sample size (`n_queries`) is deliberately NOT
    here: it is not a configuration, and the dashboard already flags it as a
    differing parameter when two runs used different query counts.
    """
    params = {
        "embedding_model": cfg.EMBEDDING_MODEL,
        "top_k": top_k,
        "pipeline_mode": pipeline_mode,
        "retrieval_mode": retrieval_mode,
        "qdrant_url": cfg.QDRANT_URL,
    }
    if eval_depth is not None:
        params["eval_depth"] = eval_depth
    if retrieval_mode in ("sparse", "hybrid"):
        # R-08. Hardcoded True because it is no longer optional: the index is
        # created with the modifier and `ensure_collection` repairs it if not.
        # It appears only for the modes that read the sparse vectors, so dense
        # runs keep the identity they had — C-06 and the whole Fase 4 depend on
        # being able to compare against them.
        params["sparse_idf"] = True
        # R-09, same argument, different half: the query encoding changes what
        # the sparse branch computes, so a run from before it must not share a
        # name with one from after.  Two keys and not one, because the two
        # corrections were measured separately (§15) and the three states —
        # neither, IDF only, both — each need their own identity.
        params["sparse_query_embed"] = True
    # R-11. Compare **solo quando e' acceso**: spento, l'hash resta quello di
    # sempre e ogni misura gia' fatta continua a valere. E' la differenza fra un
    # parametro nuovo e una correzione -- R-08 andava applicata a tutti, questo
    # e' una scelta, e finche' resta al default non c'e' niente da distinguere.
    if cfg.SEARCH_EXACT:
        params["search_exact"] = True
    elif cfg.HNSW_EF is not None:
        params["hnsw_ef"] = cfg.HNSW_EF
    if rerank:
        params["reranker_model"] = cfg.RERANKER_MODEL
    if query_rewrite:
        params["query_rewrite_model"] = cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL
    if filter_content_type:
        params["filter_content_type"] = filter_content_type
    # `doc_aggregate` NON e' qui, ed e' l'unica voce tolta invece che aggiunta.
    # Da R-05 le metriche documentali sono sempre riportate, quindi il flag non
    # cambia piu' un solo numero: due run che differiscono solo per lui
    # producono metriche identiche, e sono percio' **direttamente
    # confrontabili** -- che e' esattamente cio' che condividere un hash
    # significa. Tenerlo dentro dava nomi diversi alla stessa misura: lo
    # specchio del difetto che R-08 e R-09 hanno corretto nell'altro verso.
    #
    # Nessuna run viva ne e' toccata: `doc_aggregate=true` compare solo in 5 run
    # di `eval/results/archive/`, che conservano i propri hash per politica e
    # gia' non si riproducono (sono anteriori a `eval_depth`).
    if collection and collection != dataset_id:
        params["collection"] = collection
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


def run_retrieval_eval(
    dataset_id: str,
    golden_path: Path,
    top_k: int | None = None,
    pipeline_mode: str = "generic",
    retrieval_mode: str = "dense",
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
    limit: int | None = None,
    collection: str | None = None,
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
        doc_aggregate: kept for API compatibility; document-level metrics are
            now always reported (see below).  Since it changes no number, it is
            deliberately **not** part of `config_hash` — it only survives in
            `EvalRun.config` and in the filename slug, so archived runs stay
            readable.
        limit: evaluate only first N answerable queries (for smoke tests)
        collection: Qdrant collection name to query. Defaults to dataset_id.
            Use a non-default name to evaluate against an alternative index
            (e.g. "open_ragbench_routed" for the R-07 routing ablation).

    Returns:
        EvalRun whose metrics dict always contains the same keys: the chunk-level
        DEFAULT_MEASURES plus doc_R@5 / doc_R@10.  Every run reports every
        metric, so any two runs are comparable without checking which flags were
        on when they were produced.
    """
    if top_k is None:
        top_k = cfg.TOP_K
    qdrant_collection = collection if collection else dataset_id

    # Evaluation depth is decoupled from serving depth. `top_k` is what the
    # system would return to a user; METRIC_DEPTH is what the reported measures
    # need to mean what their names say. Tying the two together is what made
    # every run before 2026-08-07 report R@10 over a 5-document ranking.
    eval_depth = max(top_k, METRIC_DEPTH)

    # When reranking, fetch a larger initial candidate pool so the cross-encoder
    # has more to choose from before truncating.
    fetch_k = max(cfg.RERANK_FETCH_K, eval_depth) if rerank else eval_depth

    # See citation_harness.run_citation_eval: captured before the run, not
    # when the EvalRun is built.
    commit = git_commit()

    all_queries = load_golden(golden_path)
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

    retrieve = RETRIEVERS[retrieval_mode]
    all_candidates = retrieve(client, qdrant_collection, texts, fetch_k, query_filters)

    print(f"  Retrieval done, {'reranking' if rerank else 'scoring'} {n} queries...", flush=True)
    t0 = time.time()
    for i, (query, cand) in enumerate(zip(answerable, all_candidates), 1):
        if rerank:
            reranked = cross_encode(
                query.query_text, cand.payloads, cfg.RERANKER_MODEL, top_n=eval_depth
            )
            chunk_ids = [r.payload["chunk_id"] for r in reranked]
            scores = [r.score for r in reranked]
        else:
            chunk_ids = cand.chunk_ids[:eval_depth]
            scores = cand.scores[:eval_depth]
        run.extend(build_run(query.query_id, chunk_ids, scores))
        if i % report_every == 0 or i == n:
            _progress(i, n, t0)

    metrics = compute_metrics(qrels, run, DEFAULT_MEASURES)

    # Document-level metrics are pure post-processing of the same run: no extra
    # retrieval, no extra embedding, no measurable cost. Gating them behind a
    # flag meant most runs lacked doc_R@5 — the metric the routing claim (§0.2)
    # actually rests on — and so could not be compared with the ones that had it.
    doc_run = _build_doc_run(run)
    doc_qrels = _build_doc_qrels(answerable)
    doc_metrics = compute_metrics(doc_qrels, doc_run, [Recall @ 5, Recall @ 10])
    for k, v in doc_metrics.items():
        metrics[f"doc_{k}"] = v

    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=commit,
        config_hash=_config_hash(
            top_k, pipeline_mode, retrieval_mode, rerank, query_rewrite,
            filter_content_type, doc_aggregate, qdrant_collection, dataset_id,
            eval_depth,
        ),
        dataset_id=dataset_id,
        model="retrieval_only",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode=pipeline_mode,
        config=build_config(
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            rerank=rerank,
            query_rewrite=query_rewrite,
            filter_content_type=filter_content_type,
            doc_aggregate=doc_aggregate,
            collection=qdrant_collection,
            eval_depth=eval_depth,
            n_queries=n,
        ),
        metrics=metrics,
    )
