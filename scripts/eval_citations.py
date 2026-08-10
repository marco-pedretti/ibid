#!/usr/bin/env python3
"""C-01: citation-format evaluation CLI.

Retrieves context, generates a cited answer per golden query, and measures how
often the raw output respects the citation format of ROADMAP §3.2.  Acceptance
criterion: format_compliance >= 0.95.

Two files per run:
    eval/results/<ts>_<dataset>_citations.json          the EvalRun
    eval/results/generations/<ts>_<dataset>.jsonl       the raw generations
    eval/results/generations/<ts>_<dataset>.prompt.txt  the prompt under test

The JSONL is the input to C-02 — the parser has to be built against outputs the
model actually produced.

Prerequisites:
    - eval/golden/{dataset_id}.jsonl built
    - Qdrant up with the dataset ingested
    - LLM server at LLM_BASE_URL

Usage:
    python scripts/eval_citations.py --dataset open_ragbench --limit 50
    python scripts/eval_citations.py --dataset ledger --model gemma4:12b --limit 50
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.citation_harness import GenerationWriter, run_citation_eval
from src.generation.citation_format import COMPLIANCE_TARGET, VIOLATION_KINDS
from src.generation.prompt import SYSTEM

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"
GENERATIONS_DIR = RESULTS_DIR / "generations"


def main() -> None:
    p = argparse.ArgumentParser(description="C-01 citation format evaluation")
    p.add_argument("--dataset", choices=["open_ragbench", "ledger", "all"],
                   default="open_ragbench")
    p.add_argument("--top-k", type=int, default=cfg.TOP_K,
                   help="chunks placed in context")
    p.add_argument("--retrieval-mode", choices=["dense", "sparse", "hybrid"],
                   default="dense")
    p.add_argument("--collection", default=None,
                   help="Qdrant collection (default: dataset name)")
    p.add_argument("--pipeline-mode", choices=["generic", "routed"], default="generic")
    p.add_argument("--limit", type=int, default=None,
                   help="first N answerable queries only")
    p.add_argument("--model", default=None, help=f"LLM (default: {cfg.LLM_MODEL})")
    args = p.parse_args()

    datasets = ["open_ragbench", "ledger"] if args.dataset == "all" else [args.dataset]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for dataset_id in datasets:
        golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
        if not golden_path.exists():
            print(f"[ERROR] {golden_path} not found. Run build_golden.py first.")
            sys.exit(1)

        # The timestamp is taken before the run, not after: it names the file
        # the generations are streaming into while the run is still going.
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        gen_path = GENERATIONS_DIR / f"{ts}_{dataset_id}.jsonl"
        writer = GenerationWriter(gen_path, SYSTEM)

        print(f"\n=== C-01 citation format — {dataset_id} ===", flush=True)
        print(f"  generazioni in {writer.tmp.relative_to(ROOT)}", flush=True)
        run, records = run_citation_eval(
            dataset_id=dataset_id,
            golden_path=golden_path,
            top_k=args.top_k,
            retrieval_mode=args.retrieval_mode,
            collection=args.collection,
            limit=args.limit,
            model=args.model,
            pipeline_mode=args.pipeline_mode,
            system_prompt=SYSTEM,
            writer=writer,
        )
        writer.finish()

        out_path = RESULTS_DIR / f"{ts}_{dataset_id}_citations.json"
        out_path.write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        compliance = run.metrics["format_compliance"]
        lower = run.metrics["format_compliance_lower95"]
        # Verdict on the observed rate — see ComplianceSummary.meets_target.
        # The interval is printed beside it as context on the sample size.
        verdict = "PASS" if compliance >= COMPLIANCE_TARGET else "FAIL"
        print(f"\n{dataset_id}: format_compliance = {compliance:.4f} "
              f"(95% CI lower {lower:.4f}) -> {verdict}, target {COMPLIANCE_TARGET}")
        print(f"  answers {len(records)}  abstained {sum(r.abstained for r in records)}"
              f"  markers/answer {run.metrics['markers_per_answer']:.2f}")
        # Printed unconditionally, including at zero: a truncated answer looks
        # like a format failure, so the rate has to be read next to the verdict.
        print(f"  truncated {run.metrics['truncation_rate']:.3f}"
              f"  empty {run.metrics['empty_answer_rate']:.3f}"
              f"  reasoning_effort={run.config['reasoning_effort']}"
              f"  max_new_tokens={run.config['max_new_tokens']}")
        offenders = [
            (k, run.metrics[f"violation_{k}"]) for k in VIOLATION_KINDS
            if run.metrics[f"violation_{k}"] > 0
        ]
        if offenders:
            print("  violations (share of scored answers):")
            for kind, rate in sorted(offenders, key=lambda x: -x[1]):
                print(f"    {kind:<16} {rate:.3f}")
        else:
            print("  no violations")
        print(f"Saved -> {out_path.relative_to(ROOT)}")
        print(f"         {gen_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
