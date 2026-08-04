#!/usr/bin/env python3
"""T-04: Download dataset from HuggingFace and print document/chunk counts.

Usage:
    python scripts/fetch_dataset.py
    python scripts/fetch_dataset.py --skip-download        # use cached data
    python scripts/fetch_dataset.py --data-dir /path/to/data
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.datasets import open_ragbench

DEFAULT_DATA_DIR = ROOT / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="T-04 dataset loader")
    parser.add_argument("--dataset", default="open_ragbench",
                        choices=["open_ragbench"],
                        help="Dataset to load")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help=f"Local data directory (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--skip-download", action="store_true",
                        help="Use cached files; skip HuggingFace download")
    args = parser.parse_args()

    dataset_dir = args.data_dir / open_ragbench.DATASET_ID
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"

    if not args.skip_download or not corpus_dir.exists():
        print(f"Downloading {open_ragbench.REPO_ID} → {dataset_dir} ...")
        open_ragbench.download(args.data_dir)
        print("Download complete.\n")
    else:
        print(f"Using cached data in {dataset_dir}\n")

    doc_ids: set[str] = set()
    chunk_count = 0
    content_type_counts: dict[str, int] = {}

    for chunk in open_ragbench.iter_chunks(dataset_dir):
        doc_ids.add(chunk.doc_id)
        chunk_count += 1
        ct = chunk.content_type
        content_type_counts[ct] = content_type_counts.get(ct, 0) + 1

    print(f"Dataset:    {open_ragbench.DATASET_ID}")
    print(f"Documents:  {len(doc_ids)}")
    print(f"Chunks:     {chunk_count}")
    print("By content_type:")
    for ct, count in sorted(content_type_counts.items()):
        print(f"  {ct:<20} {count:>6}")


if __name__ == "__main__":
    main()
