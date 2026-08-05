"""I-03: continuous_text pipeline — paragraph-aware chunking with overlap.

Applied to documents where doc_genre == "continuous_text" (and provisionally
to "academic_pdf" until I-04 is live). Paragraphs are separated by blank lines
and are treated as atomic units — never split mid-paragraph.

Overlap is achieved by keeping trailing paragraphs from the previous window in
the next one, so a sentence near a chunk boundary is retrievable from either
side. Parameters are module-level defaults intended to be swept in config.py
(ablation = loop over config, not a code change — per ROADMAP §12).
"""

from __future__ import annotations

from src.datasets.schema import Chunk

DEFAULT_CHUNK_SIZE: int = 1000  # target chars per chunk (≈ 150–200 words)
DEFAULT_OVERLAP: int = 200      # min chars carried forward to next chunk


def _split_paragraphs(text: str) -> list[str]:
    """Split text by blank lines; discard empty paragraphs."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _group_paragraphs(
    paragraphs: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Group paragraphs into overlapping windows of ≥ chunk_size chars.

    Each window is grown until its total length reaches chunk_size, then
    emitted as a chunk. The window is trimmed from the front while keeping
    at least `overlap` trailing chars, ensuring the next chunk starts with
    content that also appeared at the end of the previous one.

    A paragraph longer than chunk_size is never split — it forms a chunk
    by itself.
    """
    if not paragraphs:
        return []

    chunks: list[str] = []
    window: list[tuple[str, int]] = []  # (paragraph, len)
    window_len = 0

    for para in paragraphs:
        window.append((para, len(para)))
        window_len += len(para)

        if window_len >= chunk_size:
            chunks.append("\n\n".join(p for p, _ in window))

            # Always advance at least one paragraph to avoid infinite loops
            # when a single paragraph fills the chunk.
            _, removed = window.pop(0)
            window_len -= removed

            # Drop further paragraphs from the front as long as removing one
            # would still leave enough chars to satisfy the overlap budget.
            while window and window_len - window[0][1] > overlap:
                _, removed = window.pop(0)
                window_len -= removed

    # Emit whatever remains; skip if identical to the last chunk (can happen
    # when the final window shrank to exactly the overlap content).
    if window:
        tail = "\n\n".join(p for p, _ in window)
        if not chunks or tail != chunks[-1]:
            chunks.append(tail)

    return chunks


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
    """Chunk a single document into overlapping paragraph-boundary chunks.

    Args:
        text:        full document text (paragraphs separated by blank lines)
        doc_id:      document identifier
        dataset_id:  dataset the document belongs to
        doc_genre:   genre label (from assign_genre)
        source_uri:  URL/URI pointing to the original document
        page:        page number if known (default 0)
        chunk_size:  target character count per chunk
        overlap:     minimum character overlap between consecutive chunks
        seq_offset:  starting sequence number for chunk_ids (for multi-page docs)

    Returns:
        List of Chunk objects, one per paragraph group. Empty if text is blank.
    """
    groups = _group_paragraphs(
        _split_paragraphs(text),
        chunk_size=chunk_size,
        overlap=overlap,
    )
    return [
        Chunk(
            chunk_id=f"{dataset_id}:{doc_id}:{seq_offset + i:04d}",
            dataset_id=dataset_id,
            doc_id=doc_id,
            doc_genre=doc_genre,
            pipeline="continuous_text",
            section_path="",
            page=page,
            bbox=None,
            content_type="text",
            text=group,
            source_uri=source_uri,
        )
        for i, group in enumerate(groups)
    ]
