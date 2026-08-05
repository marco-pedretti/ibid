#!/usr/bin/env python3
"""E-04 / E-05: generation baseline evaluation CLI.

Runs the LLM without any retrieved context and measures abstention,
correctness, and wrong answer rates via LLM-as-judge.

Baseline A (--baseline A, E-04): permissive prompt — model answers freely.
Baseline B (--baseline B, E-05): strict prompt — model is instructed to abstain
    when not confident.

Prerequisites:
    - eval/golden/{dataset_id}.jsonl built (build_golden.py + build_unanswerable.py)
    - LLM server running at LLM_BASE_URL (default: http://localhost:11434/v1)

Usage:
    python scripts/eval_generation.py --baseline A --dataset open_ragbench --limit 50
    python scripts/eval_generation.py --baseline B --dataset ledger
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.generation_harness import run_generation_eval

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generation baseline evaluation")
    parser.add_argument("--baseline", choices=["A", "B"], default="A",
                        help="A=permissive (E-04), B=strict (E-05)")
    parser.add_argument("--dataset", choices=["open_ragbench", "ledger", "all"],
                        default="open_ragbench")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N answerable queries (smoke test)")
    parser.add_argument("--model", default=None,
                        help=f"LLM model name (default: {cfg.LLM_MODEL})")
    args = parser.parse_args()

    datasets = (
        ["open_ragbench", "ledger"] if args.dataset == "all" else [args.dataset]
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for dataset_id in datasets:
        golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
        if not golden_path.exists():
            print(f"[ERROR] {golden_path} not found. Run build_golden.py first.")
            sys.exit(1)

        print(f"\n=== Baseline {args.baseline} — {dataset_id} ===", flush=True)
        run = run_generation_eval(
            dataset_id=dataset_id,
            golden_path=golden_path,
            baseline=args.baseline,
            limit=args.limit,
            model=args.model,
        )

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = RESULTS_DIR / f"{ts}_{dataset_id}_baseline{args.baseline.lower()}.json"
        out_path.write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"\nMetrics ({dataset_id}, baseline {args.baseline}):")
        for k, v in run.metrics.items():
            print(f"  {k}: {v:.3f}")
        print(f"Saved -> {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
