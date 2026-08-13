#!/usr/bin/env python3
"""I-01: document profiler CLI — prints a tabular report for a dataset.

Usage:
    python scripts/profile_docs.py
    python scripts/profile_docs.py --dataset open_ragbench
    python scripts/profile_docs.py --dataset ledger
    python scripts/profile_docs.py --dataset all       # profile all downloaded datasets
    python scripts/profile_docs.py --json              # also dump per-doc profiles as JSON
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from src.profiling.profiler import format_report, profile_from_chunks


def _profile_one(dataset_name: str, data_dir: Path) -> None:
    spec = registry.get(dataset_name)
    corpus_path = spec.corpus_dir(data_dir)
    if not corpus_path.exists():
        print(f"  SKIP {dataset_name}: corpus not found at {corpus_path}", file=sys.stderr)
        return
    print(f"Profiling {dataset_name} ...", flush=True)
    profiles = profile_from_chunks(spec.chunks(data_dir))
    print(format_report(profiles))


def main() -> None:
    parser = argparse.ArgumentParser(description="I-01 document profiler")
    parser.add_argument(
        "--dataset", default="open_ragbench",
        choices=registry.cli_choices(),
    )
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--json", action="store_true", help="Also print per-doc JSON")
    args = parser.parse_args()

    datasets = registry.resolve(args.dataset)

    all_chunks = []
    for name in datasets:
        spec = registry.get(name)
        corpus_path = spec.corpus_dir(args.data_dir)
        if not corpus_path.exists():
            print(f"SKIP {name}: corpus not found at {corpus_path}", file=sys.stderr)
            continue
        print(f"Loading {name} ...", flush=True)
        all_chunks.extend(spec.chunks(args.data_dir))

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
