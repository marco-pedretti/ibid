#!/usr/bin/env python3
"""Paired comparison of two retrieval configurations on the same golden queries.

Answers "is B actually better than A", which the metric tables cannot: two
aggregate numbers do not say whether the difference survives the sampling error
of the query set.  See `src/eval/paired.py` for why the E-07 noise floor is the
wrong instrument here.

The success criterion is document-level: "at least one relevant document among
the top-k documents".  Document rather than chunk because a routed collection
re-chunks the corpus and its chunk_ids never match the qrels — the same reason
R-07 is read on doc_R@5.

Usage:
    python scripts/compare_runs.py --dataset ledger \
        --collection-a ledger --collection-b ledger_routed

    python scripts/compare_runs.py --dataset open_ragbench \
        --collection-a open_ragbench --collection-b open_ragbench_routed \
        --limit 200 --retrieval-mode hybrid
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.harness import load_golden
from src.eval.retrieval_backends import RETRIEVERS
from src.eval.metrics import METRIC_DEPTH
from src.eval.paired import compare_paired
from src.index.store import get_client
from src.retrieval.doc_aggregation import doc_id_from_chunk_id

GOLDEN_DIR = ROOT / "eval" / "golden"


def _top_docs(chunk_ids: list[str], k: int) -> list[str]:
    """First k distinct document ids, preserving chunk rank order."""
    docs: list[str] = []
    seen: set[str] = set()
    for cid in chunk_ids:
        doc = doc_id_from_chunk_id(cid)
        if doc not in seen:
            seen.add(doc)
            docs.append(doc)
        if len(docs) == k:
            break
    return docs


def per_query_hits(client, dataset_id, collection, queries, mode, depth, k):
    """One boolean per query: was a relevant document retrieved in the top k."""
    texts = [q.query_text for q in queries]
    candidates = RETRIEVERS[mode](client, collection, texts, depth, None)
    hits = []
    for query, cand in zip(queries, candidates):
        gold = {doc_id_from_chunk_id(qr.chunk_id) for qr in query.qrels if qr.relevance > 0}
        hits.append(bool(gold & set(_top_docs(cand.chunk_ids, k))))
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description="Paired comparison of two collections")
    ap.add_argument("--dataset", required=True, choices=["open_ragbench", "ledger"])
    ap.add_argument("--collection-a", required=True, help="baseline collection")
    ap.add_argument("--collection-b", required=True, help="collection under test")
    ap.add_argument("--retrieval-mode", default="dense", choices=["dense", "sparse", "hybrid"])
    ap.add_argument("--limit", type=int, default=None, help="first N answerable queries")
    ap.add_argument("--top-k", type=int, default=cfg.TOP_K, help="documents considered (default 5)")
    args = ap.parse_args()

    queries = [
        q for q in load_golden(GOLDEN_DIR / f"{args.dataset}.jsonl")
        if q.answerable and q.dataset_id == args.dataset and q.qrels
    ]
    if args.limit:
        queries = queries[: args.limit]

    client = get_client(cfg.QDRANT_URL)
    depth = max(args.top_k, METRIC_DEPTH)

    print(f"=== {args.dataset} · {len(queries)} query · {args.retrieval_mode} · "
          f"top-{args.top_k} documenti ===")
    hits_a = per_query_hits(client, args.dataset, args.collection_a, queries,
                            args.retrieval_mode, depth, args.top_k)
    hits_b = per_query_hits(client, args.dataset, args.collection_b, queries,
                            args.retrieval_mode, depth, args.top_k)

    res = compare_paired(hits_a, hits_b)
    print(f"\n  A  {args.collection_a:24} {res.rate_a:.4f}")
    print(f"  B  {args.collection_b:24} {res.rate_b:.4f}")
    print(f"  delta {res.delta:+.4f}")
    print(f"\n  query in cui vince solo A: {res.only_a}")
    print(f"  query in cui vince solo B: {res.only_b}")
    print(f"  discordanti: {res.discordant} su {res.n} "
          f"(le concordanti non portano informazione)")
    print(f"\n  {res.verdict()}")


if __name__ == "__main__":
    main()
