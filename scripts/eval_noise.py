#!/usr/bin/env python3
"""E-07: Noise floor measurement — N runs of the same configuration.

Runs the same evaluation N times and reports per-metric dispersion
(mean ± std, min, max). No improvement smaller than the std should
ever be declared significant — see ROADMAP §14.

Supports two modes:
  retrieval  — runs run_retrieval_eval() N times (dense or sparse)
  generation — runs run_generation_eval() N times (baseline A or B)

Usage:
    python scripts/eval_noise.py --mode retrieval --dataset open_ragbench --n-runs 5
    python scripts/eval_noise.py --mode generation --baseline A --dataset open_ragbench --n-runs 5 --limit 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.harness import run_retrieval_eval
from src.eval.generation_harness import run_generation_eval
from src.eval.noise_floor import build_noise_floor_result

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="E-07: noise floor measurement")
    parser.add_argument("--mode", choices=["retrieval", "generation"], default="retrieval",
                        help="Which eval to repeat")
    parser.add_argument("--dataset", choices=["open_ragbench", "ledger"], default="open_ragbench")
    parser.add_argument("--n-runs", type=int, default=5,
                        help="Number of repetitions (default: 5)")
    parser.add_argument("--retrieval-mode", choices=["dense", "sparse"], default="dense",
                        help="retrieval mode only: dense=E-03, sparse=E-06")
    parser.add_argument("--baseline", choices=["A", "B"], default="A",
                        help="generation mode only: A=permissive, B=strict")
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K,
                        help="retrieval mode only")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N queries per run (smoke test)")
    args = parser.parse_args()

    golden_path = GOLDEN_DIR / f"{args.dataset}.jsonl"
    if not golden_path.exists():
        print(f"[ERROR] {golden_path} not found. Run build_golden.py first.")
        sys.exit(1)

    if args.mode == "retrieval":
        pipeline_mode = "baseline_c" if args.retrieval_mode == "sparse" else "generic"
        retrieval_label = args.retrieval_mode

        def eval_fn():
            return run_retrieval_eval(
                dataset_id=args.dataset,
                golden_path=golden_path,
                top_k=args.top_k,
                pipeline_mode=pipeline_mode,
                retrieval_mode=args.retrieval_mode,
                limit=args.limit,
            )
    else:
        retrieval_label = f"baseline_{args.baseline.lower()}"

        def eval_fn():
            return run_generation_eval(
                dataset_id=args.dataset,
                golden_path=golden_path,
                baseline=args.baseline,
                limit=args.limit,
            )

    runs = []
    print(
        f"\nE-07: {args.n_runs} runs — mode={args.mode}, dataset={args.dataset}, "
        f"retrieval={retrieval_label}",
        flush=True,
    )
    t_total = time.time()
    for i in range(1, args.n_runs + 1):
        print(f"\n--- Run {i}/{args.n_runs} ---", flush=True)
        t0 = time.time()
        run = eval_fn()
        elapsed = time.time() - t0
        runs.append(run)
        print(f"  Done in {elapsed:.1f}s. Metrics: " +
              ", ".join(f"{k}={v:.4f}" for k, v in sorted(run.metrics.items())))

    result = build_noise_floor_result(runs, retrieval_mode=retrieval_label)

    print(f"\n=== Noise floor ({args.n_runs} runs) ===")
    print(f"{'Metric':<20} {'mean':>8} {'std':>8} {'min':>8} {'max':>8}")
    print("-" * 58)
    for metric, s in sorted(result.metric_stats.items()):
        print(f"{metric:<20} {s.mean:>8.4f} {s.std:>8.4f} {s.min_val:>8.4f} {s.max_val:>8.4f}")
    print(f"\nTotal time: {time.time() - t_total:.1f}s")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"{ts}_{args.dataset}_noise_floor_{retrieval_label}.json"
    out.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
