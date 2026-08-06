"""E-03 / E-06 / R-01–R-05: Run retrieval evaluation and write EvalRun JSON to eval/results/.

Usage:
    python scripts/eval.py [--dataset open_ragbench|ledger|all] [--top-k N] [--limit N]
    python scripts/eval.py --retrieval-mode sparse               # E-06 lexical-only baseline
    python scripts/eval.py --retrieval-mode hybrid               # R-01 hybrid RRF
    python scripts/eval.py --rerank                              # R-02 cross-encoder reranker
    python scripts/eval.py --retrieval-mode hybrid --rerank      # hybrid + reranker
    python scripts/eval.py --query-rewrite                       # R-03 query rewriting
    python scripts/eval.py --query-rewrite --rerank              # R-03 + R-02
    python scripts/eval.py --filter-content-type text            # R-04 text-only filter
    python scripts/eval.py --filter-content-type auto            # R-04 keyword-inferred filter
    python scripts/eval.py --doc-aggregate                       # R-05 doc-level file list

Options:
    --dataset              Which dataset(s) to evaluate (default: all)
    --top-k                Retrieval depth (default: cfg.TOP_K = 5)
    --limit                Evaluate only first N answerable queries per dataset (smoke test)
    --retrieval-mode       dense (default) | sparse | hybrid
    --rerank               Apply cross-encoder reranking after initial retrieval (R-02)
    --query-rewrite        Rewrite queries with LLM before embedding (R-03)
    --filter-content-type  text | table | mixed | auto (R-04 metadata filter)
    --doc-aggregate        Aggregate chunks to doc-level and report doc_R@5/doc_R@10 (R-05)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.harness import run_retrieval_eval

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"


def run_dataset(
    dataset_id: str,
    top_k: int,
    limit: int | None,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
) -> None:
    golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
    if not golden_path.exists():
        print(f"  ERROR: {golden_path} not found — run build_golden.py first.")
        return

    base_mode_map = {"sparse": "baseline_c", "hybrid": "hybrid_rrf"}
    base_mode = base_mode_map.get(retrieval_mode, "generic")
    suffixes = []
    if query_rewrite:
        suffixes.append("rewritten")
    if rerank:
        suffixes.append("reranked")
    if filter_content_type:
        suffixes.append(f"filtered_{filter_content_type}")
    if doc_aggregate:
        suffixes.append("docagg")
    pipeline_mode = "_".join([base_mode] + suffixes) if suffixes else base_mode

    n_desc = f"first {limit}" if limit else "all"
    extras = "".join(f" + {s}" for s in suffixes)
    print(
        f"  Evaluating {n_desc} queries against {dataset_id} "
        f"(top_k={top_k}, retrieval={retrieval_mode}{extras})...",
        flush=True,
    )
    t0 = time.time()

    eval_run = run_retrieval_eval(
        dataset_id=dataset_id,
        golden_path=golden_path,
        top_k=top_k,
        pipeline_mode=pipeline_mode,
        retrieval_mode=retrieval_mode,
        rerank=rerank,
        query_rewrite=query_rewrite,
        filter_content_type=filter_content_type,
        doc_aggregate=doc_aggregate,
        limit=limit,
    )

    elapsed = time.time() - t0
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = eval_run.timestamp.strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"{ts}_{dataset_id}_{eval_run.pipeline_mode}.json"
    out.write_text(eval_run.model_dump_json(indent=2), encoding="utf-8")

    print(f"  Done in {elapsed:.1f}s -> {out.name}")
    for name, value in sorted(eval_run.metrics.items()):
        print(f"    {name}: {value:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval evaluation (E-03/E-06)")
    parser.add_argument("--dataset", choices=["open_ragbench", "ledger", "all"], default="all")
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K)
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N answerable queries (smoke test)")
    parser.add_argument("--retrieval-mode", choices=["dense", "sparse", "hybrid"], default="dense",
                        help="dense=E-03 (default), sparse=E-06 lexical-only BM25, hybrid=R-01 RRF")
    parser.add_argument("--rerank", action="store_true",
                        help="Apply cross-encoder reranking after initial retrieval (R-02)")
    parser.add_argument("--query-rewrite", action="store_true",
                        help="Rewrite queries with LLM before embedding (R-03)")
    parser.add_argument("--filter-content-type",
                        choices=["text", "table", "mixed", "auto"], default=None,
                        help="Apply metadata filter: text|table|mixed=static, auto=keyword-inferred (R-04)")
    parser.add_argument("--doc-aggregate", action="store_true",
                        help="Aggregate chunk results to doc-level; adds doc_R@5/doc_R@10 to metrics (R-05)")
    args = parser.parse_args()

    datasets = ["open_ragbench", "ledger"] if args.dataset == "all" else [args.dataset]
    for ds in datasets:
        print(f"=== {ds} ===")
        run_dataset(ds, args.top_k, args.limit, args.retrieval_mode, args.rerank,
                    args.query_rewrite, args.filter_content_type, args.doc_aggregate)


if __name__ == "__main__":
    main()
