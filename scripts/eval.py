"""E-03 / E-06 / R-01: Run retrieval evaluation and write EvalRun JSON to eval/results/.

Usage:
    python scripts/eval.py [--dataset open_ragbench|ledger|all] [--top-k N] [--limit N]
    python scripts/eval.py --retrieval-mode sparse   # E-06 lexical-only baseline
    python scripts/eval.py --retrieval-mode hybrid   # R-01 hybrid RRF

Options:
    --dataset        Which dataset(s) to evaluate (default: all)
    --top-k          Retrieval depth (default: cfg.TOP_K = 5)
    --limit          Evaluate only first N answerable queries per dataset (smoke test)
    --retrieval-mode dense (default) | sparse | hybrid
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
) -> None:
    golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
    if not golden_path.exists():
        print(f"  ERROR: {golden_path} not found — run build_golden.py first.")
        return

    pipeline_mode_map = {"sparse": "baseline_c", "hybrid": "hybrid_rrf"}
    pipeline_mode = pipeline_mode_map.get(retrieval_mode, "generic")
    n_desc = f"first {limit}" if limit else "all"
    print(
        f"  Evaluating {n_desc} queries against {dataset_id} "
        f"(top_k={top_k}, retrieval={retrieval_mode})...",
        flush=True,
    )
    t0 = time.time()

    eval_run = run_retrieval_eval(
        dataset_id=dataset_id,
        golden_path=golden_path,
        top_k=top_k,
        pipeline_mode=pipeline_mode,
        retrieval_mode=retrieval_mode,
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
    args = parser.parse_args()

    datasets = ["open_ragbench", "ledger"] if args.dataset == "all" else [args.dataset]
    for ds in datasets:
        print(f"=== {ds} ===")
        run_dataset(ds, args.top_k, args.limit, args.retrieval_mode)


if __name__ == "__main__":
    main()
