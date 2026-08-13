#!/usr/bin/env python3
"""T-04: Download dataset from HuggingFace and print document/chunk counts.

Usage:
    python scripts/fetch_dataset.py
    python scripts/fetch_dataset.py --dataset ledger
    python scripts/fetch_dataset.py --dataset all
    python scripts/fetch_dataset.py --skip-download        # use cached data
    python scripts/fetch_dataset.py --data-dir /path/to/data

**`--dataset` ora viene onorato.**  Fino a Q-06 questo script lo accettava e poi
lo ignorava: `choices` elencava soltanto `open_ragbench` e il corpo del programma
lo nominava esplicitamente sei volte.  Non poteva sbagliare -- l'unico valore
ammesso era anche l'unico implementato -- ma l'opzione era decorativa, e il
criterio di Q-06 ("aggiungere un dataset non richiede di toccare nessuno
script") sarebbe rimasto falso proprio qui.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.datasets import registry

DEFAULT_DATA_DIR = ROOT / "data"


def report(dataset_id: str, data_dir: Path, skip_download: bool) -> None:
    spec = registry.get(dataset_id)
    dataset_dir = spec.dataset_dir(data_dir)

    if not skip_download or not spec.corpus_dir(data_dir).exists():
        print(f"Downloading {spec.repo_id} → {dataset_dir} ...")
        spec.download(data_dir)
        print("Download complete.\n")
    else:
        print(f"Using cached data in {dataset_dir}\n")

    doc_ids: set[str] = set()
    chunk_count = 0
    content_type_counts: dict[str, int] = {}

    for chunk in spec.chunks(data_dir):
        doc_ids.add(chunk.doc_id)
        chunk_count += 1
        ct = chunk.content_type
        content_type_counts[ct] = content_type_counts.get(ct, 0) + 1

    print(f"Dataset:    {dataset_id}")
    print(f"Documents:  {len(doc_ids)}")
    print(f"Chunks:     {chunk_count}")
    print("By content_type:")
    for ct, count in sorted(content_type_counts.items()):
        print(f"  {ct:<20} {count:>6}")


def main() -> None:
    parser = argparse.ArgumentParser(description="T-04 dataset loader")
    parser.add_argument("--dataset", default="open_ragbench",
                        choices=registry.cli_choices(),
                        help="Dataset to load")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help=f"Local data directory (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--skip-download", action="store_true",
                        help="Use cached files; skip HuggingFace download")
    args = parser.parse_args()

    for dataset_id in registry.resolve(args.dataset):
        print(f"=== {dataset_id} ===")
        report(dataset_id, args.data_dir, args.skip_download)


if __name__ == "__main__":
    main()
