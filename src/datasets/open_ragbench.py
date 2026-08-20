"""Loader for vectara/open_ragbench — normalizes corpus sections to Chunk schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from huggingface_hub import snapshot_download

from src.profiling.genre import assign_genre
from src.ingestion.router import route_sections
from .schema import PIPELINE_GENERIC, Chunk

REPO_ID = "vectara/open_ragbench"
DATASET_ID = "open_ragbench"


def download(data_dir: Path) -> Path:
    """Download corpus JSON files to data_dir/open_ragbench/. Returns that path."""
    local_dir = data_dir / DATASET_ID
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=str(local_dir),
        allow_patterns=["pdf/arxiv/*.json", "pdf/arxiv/corpus/*.json"],
    )
    return local_dir


def iter_chunks_routed(dataset_dir: Path) -> Iterator[Chunk]:
    """Yield Chunk objects using genre-appropriate pipeline routing (R-06).

    Dispatches each document through the pipeline selected by its doc_genre:
      academic_pdf    → structured_hierarchical (section_path populated, body sub-chunked)
      table_heavy     → continuous_text (Markdown tables; HTML not present in ORB)
      continuous_text → continuous_text (paragraph overlap)

    chunk_id uses 4-digit zero-padded sequential numbers; section_ids from the
    original JSON are not preserved. Use doc_id_from_chunk_id() for doc-level eval.
    """
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"
    for corpus_file in sorted(corpus_dir.glob("*.json")):
        doc_id = corpus_file.stem
        with open(corpus_file, encoding="utf-8") as f:
            doc = json.load(f)

        arxiv_base = doc_id.split("v")[0]
        sections = doc.get("sections", [])

        n = len(sections)
        n_table_sec = sum(1 for s in sections if s.get("tables"))
        n_chars = sum(len(s.get("text", "")) for s in sections)
        td = n_table_sec / n if n > 0 else 0.0
        asl = n_chars / n if n > 0 else 0.0
        doc_genre = assign_genre(td, asl)

        source_uri = f"https://arxiv.org/abs/{arxiv_base}"
        yield from route_sections(
            sections, doc_genre,
            doc_id=doc_id, dataset_id=DATASET_ID, source_uri=source_uri,
        )


def iter_chunks(dataset_dir: Path) -> Iterator[Chunk]:
    """Yield Chunk objects from all corpus files in dataset_dir."""
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"
    for corpus_file in sorted(corpus_dir.glob("*.json")):
        doc_id = corpus_file.stem
        with open(corpus_file, encoding="utf-8") as f:
            doc = json.load(f)

        arxiv_base = doc_id.split("v")[0]
        sections = doc.get("sections", [])

        # Compute per-doc profile features for genre assignment (I-02)
        n = len(sections)
        n_table_sec = sum(1 for s in sections if s.get("tables"))
        n_chars = sum(len(s.get("text", "")) for s in sections)
        td = n_table_sec / n if n > 0 else 0.0
        asl = n_chars / n if n > 0 else 0.0
        doc_genre = assign_genre(td, asl)

        for section in sections:
            section_id: int = section["section_id"]
            text: str = section.get("text", "").strip()
            tables: dict = section.get("tables", {})
            images: dict = section.get("images", {})

            # Append Markdown table rows; skip base64 image blobs
            parts = [text] if text else []
            for tbl_content in tables.values():
                if isinstance(tbl_content, str):
                    parts.append(tbl_content)
            full_text = "\n\n".join(parts).strip()

            if not full_text:
                continue

            has_table = bool(tables)
            has_image = bool(images)
            if has_table and (text or has_image):
                content_type = "mixed"
            elif has_table:
                content_type = "table"
            elif has_image and not text:
                content_type = "figure_caption"
            else:
                content_type = "text"

            yield Chunk(
                chunk_id=f"{DATASET_ID}:{doc_id}:{section_id}",
                dataset_id=DATASET_ID,
                doc_id=doc_id,
                doc_genre=doc_genre,
                # Una sezione per chunk, cosi' come sta nel JSON: nessuna delle
                # tre pipeline ha girato. Diceva `continuous_text`, che e' il
                # nome di una pipeline vera -- paragrafi raggruppati a ~1000
                # caratteri con 200 di sovrapposizione -- e non e' cio' che
                # succede qui.
                pipeline=PIPELINE_GENERIC,
                section_path="",
                page=0,
                bbox=None,
                content_type=content_type,
                text=full_text,
                source_uri=f"https://arxiv.org/abs/{arxiv_base}",
            )
