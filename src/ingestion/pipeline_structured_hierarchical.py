"""I-04: structured_hierarchical pipeline — section-aware chunking.

Applied to documents where doc_genre == "academic_pdf". Each section's text
starts with a Markdown heading (e.g. "## 3.2 Model\n\nBody..."). The pipeline:

  1. Extracts the heading (level + text) from the first line of each section
  2. Maintains a level-aware stack to build section_path ("Methods > Model")
  3. Sub-chunks long section bodies on paragraph boundaries (reuses I-03 helpers)

section_path enables retrieval filters (R-04) and makes the routing benefit
measurable in R-07: the same query on "what does the Methods section say about X"
can be answered with and without this structural information.
"""

from __future__ import annotations

import re

from src.datasets.schema import Chunk
from src.ingestion.pipeline_continuous_text import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    _group_paragraphs,
    _split_paragraphs,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)")


def _parse_section(text: str) -> tuple[int, str, str]:
    """Extract (level, heading, body) from a section text.

    The heading is the first line when it starts with one or more '#'.
    Returns (0, "", text) when no Markdown heading is found, so callers
    can still produce a chunk — just without a path contribution.
    """
    newline = text.find("\n")
    first_line = text[:newline].strip() if newline >= 0 else text.strip()
    m = _HEADING_RE.match(first_line)
    if not m:
        return 0, "", text
    level = len(m.group(1))
    heading = m.group(2).strip().rstrip(". ")
    body = text[newline:].lstrip("\n") if newline >= 0 else ""
    return level, heading, body


class _PathTracker:
    """Builds section_path strings from a stream of (level, heading) pairs.

    The stack mirrors document hierarchy: when a heading at level N arrives,
    all stack entries at level >= N are popped (they are siblings or children
    of the new heading, not ancestors), then the new entry is pushed.

    Example:
        push(2, "Methods")   → "Methods"
        push(3, "Model")     → "Methods > Model"
        push(3, "Results")   → "Methods > Results"   (sibling, not child)
        push(1, "Appendix")  → "Appendix"            (new top-level)
    """

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, heading: str) -> str:
        """Update the stack and return the current section_path."""
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, heading))
        return " > ".join(h for _, h in self._stack)


def chunk_document(
    sections: list[dict],
    *,
    doc_id: str,
    dataset_id: str,
    doc_genre: str,
    source_uri: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Chunk a structured document into section-aware chunks.

    Args:
        sections:   list of section dicts, each with a "text" key whose first
                    line is a Markdown heading. Optional "tables" and "images"
                    dicts are used to derive content_type.
        doc_id:     document identifier
        dataset_id: dataset the document belongs to
        doc_genre:  genre label (from assign_genre)
        source_uri: URL/URI pointing to the original document
        chunk_size: target character count for body sub-chunks
        overlap:    minimum character overlap between consecutive body sub-chunks

    Returns:
        List of Chunk objects with section_path populated; empty if all
        sections are blank.
    """
    tracker = _PathTracker()
    chunks: list[Chunk] = []
    seq = 0

    for sec in sections:
        text = sec.get("text", "").strip()
        if not text:
            continue

        tables = sec.get("tables", {})
        images = sec.get("images", {})
        level, heading, body = _parse_section(text)
        body = body.strip()

        if level > 0:
            section_path = tracker.push(level, heading)
        else:
            # No heading found — inherit the current path without altering stack
            section_path = " > ".join(h for _, h in tracker._stack)

        has_table = bool(tables)
        has_image = bool(images)
        if has_table and (body or has_image):
            content_type = "mixed"
        elif has_table:
            content_type = "table"
        elif has_image and not body:
            content_type = "figure_caption"
        else:
            content_type = "text"

        # Sub-chunk long bodies; short bodies (or heading-only) → single chunk
        if not body:
            groups = [heading]
        elif len(body) <= chunk_size:
            groups = [body]
        else:
            groups = _group_paragraphs(
                _split_paragraphs(body),
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
                    pipeline="structured_hierarchical",
                    section_path=section_path,
                    page=sec.get("page", 0),
                    bbox=None,
                    content_type=content_type,
                    text=group,
                    source_uri=source_uri,
                )
            )
            seq += 1

    return chunks
