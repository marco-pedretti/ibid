"""E-02: Append unanswerable queries to eval/golden/{dataset_id}.jsonl.

Usage:
    python scripts/build_unanswerable.py [--dataset open_ragbench|ledger|all]

Requires eval/golden/{dataset_id}.jsonl to already exist (run build_golden.py first).
Appends answerable=False entries; skips if they are already present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.datasets import registry
from src.datasets.golden import validate_golden_file

GOLDEN_DIR = ROOT / "eval" / "golden"


def _already_has_unanswerable(path: Path) -> bool:
    """Return True if the file already contains any answerable=False entry."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            if '"answerable": false' in line or '"answerable":false' in line:
                return True
    return False


def append_unanswerable(dataset_id: str) -> None:
    path = GOLDEN_DIR / f"{dataset_id}.jsonl"
    if not path.exists():
        print(f"  ERROR: {path} not found: run build_golden.py first.")
        return

    if _already_has_unanswerable(path):
        print(f"  {dataset_id}: unanswerable queries already present, skipping.")
        return

    queries = registry.get(dataset_id).build_unanswerable(GOLDEN_DIR)

    with open(path, "a", encoding="utf-8") as f:
        for q in queries:
            f.write(q.model_dump_json() + "\n")

    total = validate_golden_file(path)
    n_added = len(queries)
    cross = sum(1 for q in queries if q.meta.get("source", "").startswith("cross_dataset"))
    manual = sum(1 for q in queries if q.meta.get("source") == "manual")
    print(f"  {dataset_id}: added {n_added} unanswerable ({cross} cross-dataset + {manual} manual) -> {total} total")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append unanswerable queries (E-02)")
    parser.add_argument(
        "--dataset",
        choices=registry.cli_choices(),
        default="all",
    )
    args = parser.parse_args()

    for ds in registry.resolve(args.dataset):
        print(f"=== {ds} ===")
        append_unanswerable(ds)


if __name__ == "__main__":
    main()
