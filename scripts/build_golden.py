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
from src.datasets import registry
from src.datasets.golden import save_golden, validate_golden_file

GOLDEN_DIR = ROOT / "eval" / "golden"


def build(dataset_id: str) -> None:
    """Costruisce il golden set di un dataset. Uguale per tutti.

    Erano due funzioni quasi identiche, e l'unica differenza vera -- LEDGER deve
    scaricare un parquet separato prima di poter leggere query e qrel -- ora sta
    nel registro come `prepare_golden`, che e' dove il sapere sul dataset
    appartiene.
    """
    print(f"=== {dataset_id} ===")
    t0 = time.time()
    spec = registry.get(dataset_id)

    if not spec.golden_is_ready(cfg.DATA_DIR):
        print("  Scarico i file di query e qrel ...", flush=True)
        spec.prepare_golden(cfg.DATA_DIR)
        print("  Download completo.", flush=True)

    print("Loading queries + qrels ...", flush=True)
    queries = spec.load_golden(cfg.DATA_DIR)
    print(f"  {len(queries)} queries loaded", flush=True)

    out = GOLDEN_DIR / f"{dataset_id}.jsonl"
    save_golden(queries, out)
    count = validate_golden_file(out)
    print(f"  Written and validated: {out} ({count} queries, {time.time() - t0:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build eval/golden JSONL files (E-01)")
    parser.add_argument(
        "--dataset",
        choices=registry.cli_choices(),
        default=registry.ALL,
    )
    args = parser.parse_args()

    for dataset_id in registry.resolve(args.dataset):
        build(dataset_id)


if __name__ == "__main__":
    main()
