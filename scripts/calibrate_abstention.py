#!/usr/bin/env python3
"""Derive the abstention thresholds from data (C-04).

The human picks a budget — how many answerable questions may be refused.  This
script turns that budget into a threshold per collection, which is what makes
the gate "decided by code" (ROADMAP §15) instead of a number somebody liked.

**Unanswerable queries never enter the calibration.**  The threshold is the
budget-th percentile of top-1 scores over *answerable* queries only, so the
correct-abstention rate reported on E-02 is measured out of sample.  The report
below also holds out a second, disjoint set of answerable queries, so even the
false-abstention rate it prints was not fitted.

Re-run after any re-ingestion or embedding-model change: the numbers are cosine
scores from a specific index and mean nothing against a different one.

Usage:
    python scripts/calibrate_abstention.py
    python scripts/calibrate_abstention.py --budget 0.02 --dataset ledger
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from src.retrieval.backends import RETRIEVERS
from src.index.store import get_client

#: Answerable queries used to derive the threshold, and a disjoint set of the
#: same size used only to report what it costs.
N_CALIBRATION = 150
N_HOLDOUT = 150


def top1_scores(client, collection, queries, mode, top_k):
    retrieve = RETRIEVERS[mode]
    cands = retrieve(client, collection, [q["query_text"] for q in queries], top_k, None)
    return [c.scores[0] if c.scores else 0.0 for c in cands]


def calibrate(dataset: str, budget: float, mode: str, top_k: int, seed: int = 1) -> dict:
    rows = [json.loads(x) for x in
            (ROOT / "eval" / "golden" / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()]
    unanswerable = [r for r in rows if r.get("answerable") is False]
    answerable = [r for r in rows if r.get("answerable") is not False]
    random.Random(seed).shuffle(answerable)

    cal = answerable[:N_CALIBRATION]
    holdout = answerable[N_CALIBRATION:N_CALIBRATION + N_HOLDOUT]
    if len(holdout) < 20:
        raise SystemExit(f"{dataset}: troppe poche query rispondibili per un holdout")

    client = get_client(cfg.QDRANT_URL)
    s_cal = top1_scores(client, dataset, cal, mode, top_k)
    s_hold = top1_scores(client, dataset, holdout, mode, top_k)
    s_un = top1_scores(client, dataset, unanswerable, mode, top_k)

    # Percentile of the calibration scores: by construction `budget` of them
    # would be refused, and the threshold has never seen an unanswerable query.
    idx = max(1, int(budget * 1000)) - 1
    threshold = statistics.quantiles(s_cal, n=1000)[idx]

    false_abstention = sum(1 for s in s_hold if s < threshold) / len(s_hold)
    correct_abstention = sum(1 for s in s_un if s < threshold) / len(s_un) if s_un else 0.0
    return {
        "dataset": dataset,
        "threshold": round(threshold, 4),
        "budget": budget,
        "mode": mode,
        "n_calibration": len(cal),
        "n_holdout": len(holdout),
        "n_unanswerable": len(s_un),
        "false_abstention_holdout": false_abstention,
        "correct_abstention_e02": correct_abstention,
        "median_answerable": round(statistics.median(s_cal), 4),
        "median_unanswerable": round(statistics.median(s_un), 4) if s_un else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget", type=float, default=cfg.ABSTENTION_BUDGET)
    ap.add_argument("--dataset", choices=registry.dataset_ids())
    ap.add_argument("--mode", default=cfg.ABSTENTION_CALIBRATED_MODE)
    ap.add_argument("--top-k", type=int, default=cfg.TOP_K)
    args = ap.parse_args()

    datasets = [args.dataset] if args.dataset else registry.dataset_ids()
    out = {}
    for dataset in datasets:
        r = calibrate(dataset, args.budget, args.mode, args.top_k)
        out[dataset] = r["threshold"]
        print(f"\n{dataset}  (budget {args.budget:.0%}, modo {args.mode}, top_k {args.top_k})")
        print(f"  soglia derivata            {r['threshold']:.4f}")
        print(f"  mediana rispondibili       {r['median_answerable']:.4f}")
        print(f"  mediana NON rispondibili   {r['median_unanswerable']:.4f}")
        print(f"  falsa astensione (holdout) {r['false_abstention_holdout']:.1%} "
              f"su {r['n_holdout']} query mai viste in calibrazione")
        print(f"  astensione corretta su E-02 {r['correct_abstention_e02']:.1%} "
              f"su {r['n_unanswerable']} query mai viste in calibrazione")

    print("\nDa incollare in src/config.py se diverso da quanto c'è:")
    print("ABSTENTION_THRESHOLDS: dict[str, float] = {")
    for k, v in out.items():
        print(f'    "{k}": {v},')
    print("}")
    for k, v in out.items():
        if abs(cfg.ABSTENTION_THRESHOLDS.get(k, -1) - v) > 1e-4:
            print(f"  ATTENZIONE: {k} in config è {cfg.ABSTENTION_THRESHOLDS.get(k)}, qui esce {v}")


if __name__ == "__main__":
    main()
