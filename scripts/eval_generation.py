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
from src.datasets import registry
from src.eval.dump import JsonlWriter
from src.eval.generation_harness import run_generation_eval
from src.generation.baseline_prompts import BASELINE_A_SYSTEM, BASELINE_B_SYSTEM

#: Il prompt finisce accanto al dump, non dentro ogni record: e' lo stesso per
#: tutte le query, e ripeterlo su ognuna seppellirebbe le risposte che il file
#: esiste per mostrare. Stessa scelta dell'harness delle citazioni.
_PROMPTS = {"A": BASELINE_A_SYSTEM, "B": BASELINE_B_SYSTEM}

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generation baseline evaluation")
    parser.add_argument("--baseline", choices=["A", "B"], default="A",
                        help="A=permissive (E-04), B=strict (E-05)")
    parser.add_argument("--dataset", choices=registry.cli_choices(),
                        default="open_ragbench")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N answerable queries (smoke test)")
    parser.add_argument("--queries", choices=["answerable", "unanswerable"],
                        default="answerable",
                        help="unanswerable = E-02, per il gate della Fase 4")
    parser.add_argument("--model", default=None,
                        help=f"LLM model name (default: {cfg.LLM_MODEL})")
    parser.add_argument("--no-write", action="store_true",
                        help="stampa soltanto, non archivia ne EvalRun ne risposte: "
                             "per calibrazioni e smoke test, che misure non sono")
    args = parser.parse_args()

    datasets = (
        registry.resolve(args.dataset)
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for dataset_id in datasets:
        golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
        if not golden_path.exists():
            print(f"[ERROR] {golden_path} not found. Run build_golden.py first.")
            sys.exit(1)

        print(f"\n=== Baseline {args.baseline}: {dataset_id} ===", flush=True)

        # The population is part of the file's identity: a baseline run over the
        # unanswerable set measures something else entirely.
        suffix = "" if args.queries == "answerable" else "_unanswerable"
        stem = f"{dataset_id}_baseline{args.baseline.lower()}{suffix}"
        # Q-02: le risposte per query, scritte mentre la run gira. Il nome si
        # sceglie prima, perche' e' il file in cui i record si accumulano.
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        writer = None if args.no_write else JsonlWriter(
            RESULTS_DIR / "baselines" / f"{ts}_{stem}.jsonl", sidecar=_PROMPTS[args.baseline]
        )

        run = run_generation_eval(
            dataset_id=dataset_id,
            golden_path=golden_path,
            baseline=args.baseline,
            limit=args.limit,
            model=args.model,
            queries=args.queries,
            writer=writer,
        )

        print(f"\nMetrics ({dataset_id}, baseline {args.baseline}):")
        for k, v in run.metrics.items():
            print(f"  {k}: {v:.3f}")

        if args.no_write:
            print("Niente salvato (--no-write).")
            continue
        writer.finish()
        out_path = RESULTS_DIR / f"{ts}_{stem}.json"
        out_path.write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Saved -> {out_path.relative_to(ROOT)}")
        print(f"         {writer.path.relative_to(ROOT)}  ({writer.n} query)")


if __name__ == "__main__":
    main()
