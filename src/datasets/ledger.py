"""Loader for artefactory/ledger-long-context-KPI-QA — normalizes pages to Chunk schema.

Corpus: annual reports OCR'd to Mathpix Markdown (.mmd files), one per company-year.
Pages are split by the literal string '<--- Page Split --->'.
Tables are rendered as HTML (<table>...</table>).

doc_id format : "{EXCHANGE}_{TICKER}_{YEAR}"   (e.g. "NYSE_SHW_2017")
chunk_id      : "ledger:{doc_id}:{page:04d}"   (e.g. "ledger:NYSE_SHW_2017:0003")

Qrel doc_id mapping for E-01:
    qrel["doc_id"] == f"{chunk.doc_id}/page_{page_num:04d}"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from huggingface_hub import snapshot_download

from src.profiling.genre import assign_genre
from .schema import Chunk

REPO_ID = "artefactory/ledger-long-context-KPI-QA"
DATASET_ID = "ledger"
PAGE_SEP = "<--- Page Split --->"

_TABLE_RE = re.compile(r"<table[\s>]", re.IGNORECASE)


def download(data_dir: Path) -> Path:
    """Download .mmd corpus files to data_dir/ledger/. Returns that path."""
    local_dir = data_dir / DATASET_ID
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=str(local_dir),
        allow_patterns=["eval/mmd/*.mmd"],
    )
    return local_dir


def _content_type(page_text: str) -> str:
    """Classify a page by its dominant content."""
    has_table = bool(_TABLE_RE.search(page_text))
    # Strip HTML tags to check remaining text
    plain = re.sub(r"<[^>]+>", " ", page_text).strip()
    has_text = len(plain) > 30
    if has_table and has_text:
        return "mixed"
    if has_table:
        return "table"
    return "text"


def _parse_doc_id(mmd_file: Path) -> tuple[str, str, str]:
    """Return (exchange, ticker, year) from filename like NYSE_SHW_2017.mmd."""
    name = mmd_file.stem  # e.g. "NYSE_SHW_2017"
    parts = name.split("_")
    # exchange is first token, year is last, ticker is everything in between
    exchange = parts[0]
    year = parts[-1]
    ticker = "_".join(parts[1:-1])
    return exchange, ticker, year


def iter_chunks(dataset_dir: Path) -> Iterator[Chunk]:
    """Yield one Chunk per page from all .mmd files in dataset_dir/eval/mmd/."""
    mmd_dir = dataset_dir / "eval" / "mmd"
    for mmd_file in sorted(mmd_dir.glob("*.mmd")):
        exchange, ticker, year = _parse_doc_id(mmd_file)
        doc_id = mmd_file.stem  # "NYSE_SHW_2017"
        text = mmd_file.read_text(encoding="utf-8")
        pages = [p.strip() for p in text.split(PAGE_SEP)]
        non_empty = [p for p in pages if p]

        # Compute per-doc features for genre assignment (I-02)
        n = len(non_empty)
        n_table_pages = sum(1 for p in non_empty if _TABLE_RE.search(p))
        n_chars = sum(len(p) for p in non_empty)
        td = n_table_pages / n if n > 0 else 0.0
        asl = n_chars / n if n > 0 else 0.0
        doc_genre = assign_genre(td, asl)
        pipeline = doc_genre  # "table_heavy" | "academic_pdf" | "continuous_text"

        for page_num, page_text in enumerate(pages):
            page_text = page_text.strip()
            if not page_text:
                continue

            content_type = _content_type(page_text)
            chunk_id = f"{DATASET_ID}:{doc_id}:{page_num:04d}"

            yield Chunk(
                chunk_id=chunk_id,
                dataset_id=DATASET_ID,
                doc_id=doc_id,
                doc_genre=doc_genre,
                pipeline=pipeline,
                section_path="",
                page=page_num,
                bbox=None,
                content_type=content_type,
                text=page_text,
                source_uri=f"ledger:{exchange}:{ticker}:{year}",
            )


def qrel_doc_id(chunk: Chunk) -> str:
    """Return the qrel doc_id string for a given chunk (used by E-01).

    Maps e.g. chunk_id "ledger:NYSE_SHW_2017:0003"
    to qrel format  "NYSE_SHW_2017/page_0003".
    """
    page_num = int(chunk.chunk_id.split(":")[-1])
    return f"{chunk.doc_id}/page_{page_num:04d}"
