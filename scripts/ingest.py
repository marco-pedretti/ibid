#!/usr/bin/env python3
"""I-07: Full ingestion — chunk, embed (dense + sparse), upsert to Qdrant.

One collection per dataset, named vectors:
  - "dense"  : intfloat/multilingual-e5-large via DirectML (AMD GPU)
  - "sparse" : Qdrant/bm25 via fastembed SparseTextEmbedding (CPU)

Prerequisites:
    docker compose --profile full up qdrant -d

Usage:
    python scripts/ingest.py                        # both datasets
    python scripts/ingest.py --dataset open_ragbench
    python scripts/ingest.py --dataset ledger
    python scripts/ingest.py --skip-download        # use cached corpus
    python scripts/ingest.py --drop                 # recreate collections from scratch
    python scripts/ingest.py --limit 500            # quick smoke test
    python scripts/ingest.py --batch-size 64        # override embed batch size
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import ledger, open_ragbench
from src.datasets.schema import Chunk
from src.index.embed import encode, encode_sparse, vector_size
from src.index.store import delete_collection, ensure_collection, get_client, upsert


def _check_qdrant(url: str) -> None:
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(f"{url}/", timeout=5)
    except (urllib.error.URLError, OSError):
        print(f"ERROR: Qdrant non raggiungibile su {url}", file=sys.stderr)
        print("Avvia Qdrant con: docker compose --profile full up qdrant -d", file=sys.stderr)
        sys.exit(1)


def _load_chunks(dataset_id: str, data_dir: Path, skip_download: bool, limit: int | None) -> list[Chunk]:
    if dataset_id == "open_ragbench":
        dataset_dir = data_dir / open_ragbench.DATASET_ID
        corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"
        if not skip_download or not corpus_dir.exists():
            print(f"  Downloading {open_ragbench.REPO_ID} ...")
            open_ragbench.download(data_dir)
        chunks = list(open_ragbench.iter_chunks(dataset_dir))
    elif dataset_id == "ledger":
        dataset_dir = data_dir / ledger.DATASET_ID
        mmd_dir = dataset_dir / "eval" / "mmd"
        if not skip_download or not mmd_dir.exists():
            print(f"  Downloading {ledger.REPO_ID} ...")
            ledger.download(data_dir)
        chunks = list(ledger.iter_chunks(dataset_dir))
    else:
        raise ValueError(f"Unknown dataset: {dataset_id}")

    if limit:
        chunks = chunks[:limit]
    return chunks


def _embed_chunks(
    chunks: list[Chunk],
    dense_model: str,
    sparse_model: str,
    batch_size: int,
    label: str,
) -> tuple[list[list[float]], list]:
    texts = [c.text for c in chunks]
    n = len(texts)

    # Dense (GPU via DirectML)
    print(f"  Dense embedding ({dense_model}, batch={batch_size}) ...", flush=True)
    t0 = time.time()
    dense_vecs: list[list[float]] = []
    for start in range(0, n, batch_size):
        batch = texts[start : start + batch_size]
        dense_vecs.extend(encode(batch, dense_model, batch_size))
        done = min(start + batch_size, n)
        elapsed = time.time() - t0
        rate = done / elapsed if elapsed > 0 else 0
        eta = (n - done) / rate if rate > 0 else 0
        print(f"    {done}/{n}  {rate:.1f}/s  ETA {eta:.0f}s", end="\r", flush=True)
    dense_elapsed = time.time() - t0
    print(f"    {n}/{n}  {n/dense_elapsed:.1f}/s  [{dense_elapsed:.1f}s]          ")

    # Sparse (CPU — statistical, no warm-up cost)
    print(f"  Sparse embedding ({sparse_model}) ...", end=" ", flush=True)
    t1 = time.time()
    sparse_vecs = encode_sparse(texts, sparse_model)
    sparse_elapsed = time.time() - t1
    print(f"{len(sparse_vecs)} vettori in {sparse_elapsed:.1f}s")

    return dense_vecs, sparse_vecs


def _ingest_dataset(
    dataset_id: str,
    *,
    data_dir: Path,
    skip_download: bool,
    drop: bool,
    limit: int | None,
    batch_size: int,
    client,
    dense_model: str,
    sparse_model: str,
    dim: int,
) -> None:
    print(f"\n=== {dataset_id} ===")

    # Load chunks
    print("  Caricamento chunk ...", end=" ", flush=True)
    t0 = time.time()
    chunks = _load_chunks(dataset_id, data_dir, skip_download, limit)
    n_docs = len({c.doc_id for c in chunks})
    print(f"{len(chunks)} chunk da {n_docs} documenti ({time.time()-t0:.1f}s)")

    # Recreate collection if requested
    if drop:
        print(f"  Drop collection '{dataset_id}' ...")
        delete_collection(client, dataset_id)
    ensure_collection(client, dataset_id, dim)

    # Embed
    dense_vecs, sparse_vecs = _embed_chunks(
        chunks, dense_model, sparse_model, batch_size, label=dataset_id
    )

    # Upsert
    print(f"  Upsert su Qdrant (collection={dataset_id}) ...", end=" ", flush=True)
    t2 = time.time()
    upsert(client, dataset_id, chunks, dense_vecs, sparse_vecs)
    print(f"{len(chunks)} punti in {time.time()-t2:.1f}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="I-07 ingestion — dense + sparse, named vectors")
    parser.add_argument(
        "--dataset",
        default="all",
        choices=["open_ragbench", "ledger", "all"],
        help="Dataset to ingest (default: all)",
    )
    parser.add_argument("--data-dir", type=Path, default=cfg.DATA_DIR)
    parser.add_argument("--skip-download", action="store_true", help="Use cached corpus")
    parser.add_argument("--drop", action="store_true", help="Drop and recreate collection")
    parser.add_argument("--limit", type=int, default=None, help="Ingest only first N chunks")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=cfg.EMBEDDING_BATCH,
        help=f"Dense embedding batch size (default: {cfg.EMBEDDING_BATCH})",
    )
    args = parser.parse_args()

    _check_qdrant(cfg.QDRANT_URL)
    client = get_client(cfg.QDRANT_URL)

    # Warm up model to get vector dim before the main loop
    print(f"Warm-up modello denso ({cfg.EMBEDDING_MODEL}) ...", end=" ", flush=True)
    t_warmup = time.time()
    dim = vector_size(cfg.EMBEDDING_MODEL)
    print(f"dim={dim}  ({time.time()-t_warmup:.1f}s)")

    datasets = (
        ["open_ragbench", "ledger"] if args.dataset == "all" else [args.dataset]
    )

    t_total = time.time()
    for ds in datasets:
        _ingest_dataset(
            ds,
            data_dir=args.data_dir,
            skip_download=args.skip_download,
            drop=args.drop,
            limit=args.limit,
            batch_size=args.batch_size,
            client=client,
            dense_model=cfg.EMBEDDING_MODEL,
            sparse_model=cfg.SPARSE_EMBEDDING_MODEL,
            dim=dim,
        )

    total = time.time() - t_total
    print(f"\nIngestion completa in {total/60:.1f} minuti.")


if __name__ == "__main__":
    main()
