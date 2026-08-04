#!/usr/bin/env python3
"""T-05: One-shot ingestion — embed chunks and upsert to Qdrant.

Prerequisites:
    docker compose --profile full up qdrant -d

Usage:
    python scripts/ingest.py                        # download + ingest all
    python scripts/ingest.py --skip-download        # use cached corpus
    python scripts/ingest.py --limit 500            # quick smoke test
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import open_ragbench
from src.index.embed import encode, vector_size
from src.index.store import ensure_collection, get_client, upsert


def _check_qdrant(url: str) -> None:
    import urllib.request, urllib.error
    try:
        urllib.request.urlopen(f"{url}/", timeout=5)
    except (urllib.error.URLError, OSError):
        print(f"ERROR: Qdrant non raggiungibile su {url}", file=sys.stderr)
        print("Avvia Qdrant con: docker compose --profile full up qdrant -d", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="T-05 ingestion")
    parser.add_argument("--dataset", default="open_ragbench", choices=["open_ragbench"])
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ingest only first N chunks (for testing)")
    args = parser.parse_args()

    _check_qdrant(cfg.QDRANT_URL)

    # 1. Load corpus
    dataset_dir = args.data_dir / open_ragbench.DATASET_ID
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"
    if not args.skip_download or not corpus_dir.exists():
        print(f"Downloading {open_ragbench.REPO_ID} ...")
        open_ragbench.download(args.data_dir)

    print("Caricamento chunk ...", end=" ", flush=True)
    chunks = list(open_ragbench.iter_chunks(dataset_dir))
    if args.limit:
        chunks = chunks[: args.limit]
    n_docs = len({c.doc_id for c in chunks})
    print(f"{len(chunks)} chunk da {n_docs} documenti")

    # 2. Embed
    print(f"Embedding con {cfg.EMBEDDING_MODEL} (batch={cfg.EMBEDDING_BATCH}) ...")
    t0 = time.time()
    texts = [c.text for c in chunks]
    all_vecs: list[list[float]] = []
    for start in range(0, len(texts), cfg.EMBEDDING_BATCH):
        batch = texts[start : start + cfg.EMBEDDING_BATCH]
        all_vecs.extend(encode(batch, cfg.EMBEDDING_MODEL, cfg.EMBEDDING_BATCH))
        done = min(start + cfg.EMBEDDING_BATCH, len(texts))
        pct = done / len(texts) * 100
        print(f"  {done}/{len(texts)} ({pct:.0f}%)", end="\r", flush=True)
    elapsed = time.time() - t0
    print(f"\nEmbedded {len(all_vecs)} chunk in {elapsed:.1f}s ({len(all_vecs)/elapsed:.1f}/s)")

    # 3. Upsert
    dim = len(all_vecs[0])
    print(f"Upsert su Qdrant {cfg.QDRANT_URL} (collection={args.dataset}, dim={dim}) ...")
    client = get_client(cfg.QDRANT_URL)
    ensure_collection(client, args.dataset, dim)
    upsert(client, args.dataset, chunks, all_vecs)
    print(f"Fatto. {len(all_vecs)} punti nella collection '{args.dataset}'.")


if __name__ == "__main__":
    main()
