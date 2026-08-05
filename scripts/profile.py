#!/usr/bin/env python3
"""I-01: document profiler CLI — prints a tabular report for a dataset.

Usage:
    python scripts/profile.py
    python scripts/profile.py --dataset open_ragbench --data-dir data
    python scripts/profile.py --json   # also dump per-doc profiles as JSON
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import open_ragbench
from src.profiling.profiler import format_report, profile_from_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="I-01 document profiler")
    parser.add_argument("--dataset", default="open_ragbench", choices=["open_ragbench"])
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--json", action="store_true", help="Also print per-doc JSON")
    args = parser.parse_args()

    dataset_dir = args.data_dir / open_ragbench.DATASET_ID
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"

    if not corpus_dir.exists():
        print(
            f"ERROR: corpus not found at {corpus_dir}\n"
            "Run: python scripts/fetch_dataset.py",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Profiling {args.dataset} from {corpus_dir} ...", flush=True)
    chunks = list(open_ragbench.iter_chunks(dataset_dir))
    profiles = profile_from_chunks(chunks)

    print(format_report(profiles))

    if args.json:
        import dataclasses
        rows = [dataclasses.asdict(p) for p in profiles]
        print("\n--- per-doc JSON ---")
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
