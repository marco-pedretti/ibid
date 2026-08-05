"""E-01: Build eval/golden/{dataset_id}.jsonl from raw dataset QA files.

Usage:
    python scripts/build_golden.py [--dataset open_ragbench|ledger|all]

Downloads QA files if not already present, writes JSONL, validates output.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets.golden import (
    load_ledger_golden,
    load_open_ragbench_golden,
    save_golden,
    validate_golden_file,
)
from src.datasets.ledger import download_qa as ledger_download_qa

GOLDEN_DIR = ROOT / "eval" / "golden"


def build_open_ragbench() -> None:
    print("=== open_ragbench ===")
    t0 = time.time()

    print("Loading queries + qrels from JSON files...", flush=True)
    queries = load_open_ragbench_golden(cfg.DATA_DIR)
    print(f"  {len(queries)} queries loaded", flush=True)

    out = GOLDEN_DIR / "open_ragbench.jsonl"
    save_golden(queries, out)
    count = validate_golden_file(out)
    print(f"  Written and validated: {out} ({count} queries, {time.time() - t0:.1f}s)")


def build_ledger() -> None:
    print("=== ledger ===")
    t0 = time.time()

    eval_dir = cfg.DATA_DIR / "ledger" / "eval"
    if not any(eval_dir.glob("data-*-of-*.parquet")):
        print("  Downloading eval/data.parquet from HuggingFace...", flush=True)
        ledger_download_qa(cfg.DATA_DIR)
        print("  Download complete.", flush=True)

    print("Loading queries + qrels from parquet...", flush=True)
    queries = load_ledger_golden(cfg.DATA_DIR)
    print(f"  {len(queries)} queries loaded", flush=True)

    out = GOLDEN_DIR / "ledger.jsonl"
    save_golden(queries, out)
    count = validate_golden_file(out)
    print(f"  Written and validated: {out} ({count} queries, {time.time() - t0:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build eval/golden JSONL files (E-01)")
    parser.add_argument(
        "--dataset",
        choices=["open_ragbench", "ledger", "all"],
        default="all",
    )
    args = parser.parse_args()

    if args.dataset in ("open_ragbench", "all"):
        build_open_ragbench()
    if args.dataset in ("ledger", "all"):
        build_ledger()


if __name__ == "__main__":
    main()
