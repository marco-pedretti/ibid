#!/usr/bin/env python3
"""I-01: document profiler CLI — prints a tabular report for a dataset.

Usage:
    python scripts/profile.py
    python scripts/profile.py --dataset open_ragbench
    python scripts/profile.py --dataset ledger
    python scripts/profile.py --dataset all       # profile all downloaded datasets
    python scripts/profile.py --json              # also dump per-doc profiles as JSON
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import ledger, open_ragbench
from src.profiling.profiler import format_report, profile_from_chunks

_LOADERS = {
    "open_ragbench": lambda data_dir: (
        open_ragbench.iter_chunks(data_dir / open_ragbench.DATASET_ID),
        data_dir / open_ragbench.DATASET_ID / "pdf" / "arxiv" / "corpus",
    ),
    "ledger": lambda data_dir: (
        ledger.iter_chunks(data_dir / ledger.DATASET_ID),
        data_dir / ledger.DATASET_ID / "eval" / "mmd",
    ),
}


def _profile_one(dataset_name: str, data_dir: Path) -> None:
    iter_fn, corpus_path = _LOADERS[dataset_name](data_dir)
    if not corpus_path.exists():
        print(f"  SKIP {dataset_name}: corpus not found at {corpus_path}", file=sys.stderr)
        return
    print(f"Profiling {dataset_name} ...", flush=True)
    profiles = profile_from_chunks(iter_fn)
    print(format_report(profiles))


def main() -> None:
    parser = argparse.ArgumentParser(description="I-01 document profiler")
    parser.add_argument(
        "--dataset", default="open_ragbench",
        choices=[*_LOADERS, "all"],
    )
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--json", action="store_true", help="Also print per-doc JSON")
    args = parser.parse_args()

    datasets = list(_LOADERS) if args.dataset == "all" else [args.dataset]

    all_chunks = []
    for name in datasets:
        iter_fn, corpus_path = _LOADERS[name](args.data_dir)
        if not corpus_path.exists():
            print(f"SKIP {name}: corpus not found at {corpus_path}", file=sys.stderr)
            continue
        print(f"Loading {name} ...", flush=True)
        all_chunks.extend(iter_fn)

    if not all_chunks:
        print("No datasets found. Run the fetch scripts first.", file=sys.stderr)
        sys.exit(1)

    profiles = profile_from_chunks(all_chunks)
    print(format_report(profiles))

    if args.json:
        import dataclasses
        rows = [dataclasses.asdict(p) for p in profiles]
        print("\n--- per-doc JSON ---")
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
