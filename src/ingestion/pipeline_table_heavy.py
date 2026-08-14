"""I-05: table_heavy pipeline — table as atomic unit, never split mid-table.

Applied to documents where doc_genre == "table_heavy". A page's content is
split into alternating text and table segments. Each <table>…</table> block
becomes its own chunk regardless of size. Text segments between tables are
chunked on paragraph boundaries if long (reuses I-03 helpers).

Acceptance criterion (ROADMAP I-05): no chunk contains a truncated table —
every chunk that contains '<table' also contains a matching '</table>'.

Assumption: tables in the target corpus (LEDGER annual reports in Mathpix
Markdown) are flat, not nested. A nested <table> inside a <td> would break
the regex segmenter; no such nesting has been observed in the LEDGER corpus.
"""

from __future__ import annotations

import re

from src.datasets.schema import Chunk
from src.ingestion.ocr_tables import split_segments
from src.ingestion.pipeline_continuous_text import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    _group_paragraphs,
    _split_paragraphs,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)


def _first_heading(text: str) -> str:
    """Return the first Markdown heading found in text, stripped of trailing punctuation."""
    m = _HEADING_RE.search(text)
    return m.group(2).strip().rstrip(". ") if m else ""


def chunk_document(
    text: str,
    *,
    doc_id: str,
    dataset_id: str,
    doc_genre: str,
    source_uri: str,
    page: int = 0,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    seq_offset: int = 0,
) -> list[Chunk]:
    """Chunk a table-heavy page; each <table> block is a single atomic chunk.

    Args:
        text:        page content (Markdown + embedded HTML tables)
        doc_id:      document identifier
        dataset_id:  dataset the document belongs to
        doc_genre:   genre label (from assign_genre)
        source_uri:  URL/URI pointing to the original document
        page:        page number within the document
        chunk_size:  target char count for text sub-chunks
        overlap:     minimum char overlap between consecutive text sub-chunks
        seq_offset:  starting sequence number for chunk_ids (multi-page docs)

    Returns:
        List of Chunk objects. Table chunks always contain one complete table.
        Text chunks use paragraph-aware splitting from I-03.
    """
    segments = split_segments(text)
    chunks: list[Chunk] = []
    seq = seq_offset
    current_section = ""  # last Markdown heading seen — carried into table chunks

    for kind, segment in segments:
        if kind == "text":
            heading = _first_heading(segment)
            if heading:
                current_section = heading

            groups = _group_paragraphs(
                _split_paragraphs(segment),
                chunk_size=chunk_size,
                overlap=overlap,
            )
            for group in groups:
                chunks.append(
                    Chunk(
                        chunk_id=f"{dataset_id}:{doc_id}:{seq:04d}",
                        dataset_id=dataset_id,
                        doc_id=doc_id,
                        doc_genre=doc_genre,
                        pipeline="table_heavy",
                        section_path=current_section,
                        page=page,
                        bbox=None,
                        content_type="text",
                        text=group,
                        source_uri=source_uri,
                    )
                )
                seq += 1

        else:  # table — one chunk, whole block, never split
            chunks.append(
                Chunk(
                    chunk_id=f"{dataset_id}:{doc_id}:{seq:04d}",
                    dataset_id=dataset_id,
                    doc_id=doc_id,
                    doc_genre=doc_genre,
                    pipeline="table_heavy",
                    section_path=current_section,
                    page=page,
                    bbox=None,
                    content_type="table",
                    text=segment,
                    source_uri=source_uri,
                )
            )
            seq += 1

    return chunks
