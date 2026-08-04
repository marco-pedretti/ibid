"""Loader for vectara/open_ragbench — normalizes corpus sections to Chunk schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from huggingface_hub import snapshot_download

from .schema import Chunk

REPO_ID = "vectara/open_ragbench"
DATASET_ID = "open_ragbench"

# T-04 placeholders — replaced by profilatore (I-02) and routing (I-03/I-04/I-05)
_DOC_GENRE = "academic_pdf"
_PIPELINE = "continuous_text"


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


def iter_chunks(dataset_dir: Path) -> Iterator[Chunk]:
    """Yield Chunk objects from all corpus files in dataset_dir."""
    corpus_dir = dataset_dir / "pdf" / "arxiv" / "corpus"
    for corpus_file in sorted(corpus_dir.glob("*.json")):
        doc_id = corpus_file.stem
        with open(corpus_file, encoding="utf-8") as f:
            doc = json.load(f)

        arxiv_base = doc_id.split("v")[0]

        for section in doc.get("sections", []):
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
                doc_genre=_DOC_GENRE,
                pipeline=_PIPELINE,
                section_path="",
                page=0,
                bbox=None,
                content_type=content_type,
                text=full_text,
                source_uri=f"https://arxiv.org/abs/{arxiv_base}",
            )
