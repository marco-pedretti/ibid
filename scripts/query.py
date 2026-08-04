#!/usr/bin/env python3
"""T-05: CLI query — retrieves chunks and generates answer with citation markers.

Prerequisites:
    1. docker compose --profile full up qdrant -d
    2. python scripts/ingest.py --skip-download
    3. Ollama running with gemma4 loaded

Usage:
    python scripts/query.py "your question here"
    python scripts/query.py --top-k 3 "What is the standard deviation of RMSE for Ridge Regression?"
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets.schema import Chunk
from src.generation.chat import generate
from src.generation.prompt import SYSTEM, build_user_message
from src.index.embed import encode
from src.index.store import get_client, search


def _payload_to_chunk(p: dict) -> Chunk:
    return Chunk(
        chunk_id=p["chunk_id"],
        dataset_id=p["dataset_id"],
        doc_id=p["doc_id"],
        doc_genre=p.get("doc_genre", ""),
        pipeline="",
        section_path="",
        page=p.get("page", 0),
        bbox=None,
        content_type=p.get("content_type", "text"),
        text=p["text"],
        source_uri=p["source_uri"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="T-05 query CLI")
    parser.add_argument("query", help="Question to answer")
    parser.add_argument("--dataset", default="open_ragbench")
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K)
    parser.add_argument("--model", default=cfg.LLM_MODEL)
    args = parser.parse_args()

    # 1. Embed query
    print(f"Encoding query con {cfg.EMBEDDING_MODEL} ...", flush=True)
    [q_vec] = encode([args.query], cfg.EMBEDDING_MODEL)

    # 2. Retrieve
    client = get_client(cfg.QDRANT_URL)
    hits = search(client, args.dataset, q_vec, args.top_k)
    chunks = [_payload_to_chunk(h.payload) for h in hits]

    print(f"\nTop {len(chunks)} chunk recuperati:")
    for i, (chunk, hit) in enumerate(zip(chunks, hits)):
        preview = chunk.text[:80].replace("\n", " ")
        print(f"  [{i+1}] {chunk.doc_id} (score={hit.score:.3f}): {preview}...")

    # 3. Generate
    print(f"\nGenerazione risposta con {args.model} ...")
    user_msg = build_user_message(args.query, chunks)
    answer = generate(
        base_url=cfg.LLM_BASE_URL,
        model=args.model,
        system=SYSTEM,
        user=user_msg,
        temperature=cfg.TEMPERATURE,
        max_tokens=cfg.MAX_NEW_TOKENS,
    )

    print("\n" + "=" * 60)
    print("RISPOSTA:")
    print("=" * 60)
    print(answer)
    print("=" * 60)

    print("\nFonti:")
    for i, chunk in enumerate(chunks):
        print(f"  [{i+1}] {chunk.source_uri}  ({chunk.doc_id})")


if __name__ == "__main__":
    main()
