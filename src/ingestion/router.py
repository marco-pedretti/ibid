"""R-06: Automatic pipeline routing — doc_genre → ingestion pipeline.

Route table:
  "academic_pdf"    → pipeline_structured_hierarchical  (I-04)
  "table_heavy"     → pipeline_table_heavy               (I-05)
  "continuous_text" → pipeline_continuous_text           (I-03)

Two entry points, one per data shape:

  route_sections(sections, genre, ...)
      For structured corpora (open_ragbench): each section is a dict with
      "text", "tables", "images" keys. academic_pdf gets structured_hierarchical
      with section_path populated; other genres get continuous_text (table content
      in open_ragbench is Markdown, not HTML, so pipeline_table_heavy is
      inappropriate for that corpus).

  route_text(text, genre, ...)
      For page-level corpora (ledger): each page is raw text that may include
      HTML <table> blocks. table_heavy genre gets pipeline_table_heavy, which
      preserves table atomicity; others get continuous_text.

The router is intentionally separate from the loaders so R-07 can import it
for the ablation without touching the eval harness.
"""

from __future__ import annotations

from src.datasets.schema import Chunk
from src.ingestion import (
    pipeline_continuous_text,
    pipeline_structured_hierarchical,
    pipeline_table_heavy,
)

# Maps each genre to the pipeline name string stored in Chunk.pipeline.
# Used by the eval harness to tag EvalRuns with the routing decision.
PIPELINE_FOR_GENRE: dict[str, str] = {
    "academic_pdf": "structured_hierarchical",
    "table_heavy": "table_heavy",
    "continuous_text": "continuous_text",
}


def _sections_to_text(sections: list[dict]) -> str:
    """Flatten section dicts to plain text for continuous_text routing.

    Appends Markdown table content (open_ragbench stores tables as Markdown
    strings inside the "tables" dict, not as HTML) after each section body.
    """
    parts: list[str] = []
    for s in sections:
        text = s.get("text", "").strip()
        if text:
            parts.append(text)
        for tbl in s.get("tables", {}).values():
            if isinstance(tbl, str) and tbl.strip():
                parts.append(tbl)
    return "\n\n".join(parts)


def route_sections(
    sections: list[dict],
    genre: str,
    *,
    doc_id: str,
    dataset_id: str,
    source_uri: str,
) -> list[Chunk]:
    """Route a structured document through the genre-appropriate pipeline.

    Args:
        sections:   list of section dicts (open_ragbench format):
                    each may have "text", "tables", "images" keys.
        genre:      doc_genre from assign_genre() — one of "academic_pdf",
                    "table_heavy", "continuous_text".
        doc_id:     document identifier
        dataset_id: dataset the document belongs to
        source_uri: URL/URI pointing to the original document

    Returns:
        List of Chunk objects produced by the genre-appropriate pipeline.
        chunk_id uses 4-digit zero-padded sequential numbers.
    """
    if genre == "academic_pdf":
        return pipeline_structured_hierarchical.chunk_document(
            sections,
            doc_id=doc_id,
            dataset_id=dataset_id,
            doc_genre=genre,
            source_uri=source_uri,
        )
    # table_heavy and continuous_text: flatten to text then use continuous_text.
    # pipeline_table_heavy expects HTML <table> blocks (ledger format); open_ragbench
    # stores tables as Markdown strings, so continuous_text is the correct fallback.
    text = _sections_to_text(sections)
    return pipeline_continuous_text.chunk_document(
        text,
        doc_id=doc_id,
        dataset_id=dataset_id,
        doc_genre=genre,
        source_uri=source_uri,
    )


def route_text(
    text: str,
    genre: str,
    *,
    doc_id: str,
    dataset_id: str,
    source_uri: str,
    page: int = 0,
    seq_offset: int = 0,
) -> list[Chunk]:
    """Route a text block through the genre-appropriate pipeline.

    Args:
        text:       page/document text, may include HTML <table> blocks.
        genre:      doc_genre — one of "table_heavy", "academic_pdf",
                    "continuous_text".
        doc_id:     document identifier
        dataset_id: dataset the document belongs to
        source_uri: URL/URI pointing to the original document
        page:       page number within the document (for ledger multi-page docs)
        seq_offset: starting sequence number for chunk_ids (accumulated across
                    pages so chunk_ids are unique within a document)

    Returns:
        List of Chunk objects. For "table_heavy" genre, each HTML table block
        is guaranteed to be a single atomic chunk (never split).
    """
    if genre == "table_heavy":
        return pipeline_table_heavy.chunk_document(
            text,
            doc_id=doc_id,
            dataset_id=dataset_id,
            doc_genre=genre,
            source_uri=source_uri,
            page=page,
            seq_offset=seq_offset,
        )
    # academic_pdf and continuous_text: paragraph-aware overlap chunking.
    # For academic_pdf, the full section structure is not available here
    # (only raw text), so continuous_text is the correct fallback.
    return pipeline_continuous_text.chunk_document(
        text,
        doc_id=doc_id,
        dataset_id=dataset_id,
        doc_genre=genre,
        source_uri=source_uri,
        page=page,
        seq_offset=seq_offset,
    )
