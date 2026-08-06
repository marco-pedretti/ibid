"""Tests for R-06: automatic pipeline routing (router.py).

Covers:
  - route_sections: dispatch to structured_hierarchical for academic_pdf,
    continuous_text for table_heavy and continuous_text
  - route_text: dispatch to table_heavy pipeline for table_heavy genre,
    continuous_text for academic_pdf and continuous_text genres
  - section_path populated when routing academic_pdf via route_sections
  - table atomicity preserved when routing table_heavy via route_text
  - PIPELINE_FOR_GENRE mapping completeness
  - iter_chunks_routed integration via loader helpers (no filesystem access)
"""

from __future__ import annotations

import pytest

from src.ingestion.router import PIPELINE_FOR_GENRE, route_sections, route_text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE = dict(doc_id="doc1", dataset_id="test", source_uri="http://example.com")

_SIMPLE_SECTIONS = [
    {"text": "## Introduction\n\nThis is the intro paragraph. " * 5},
    {"text": "## Methods\n\nThis describes the methods. " * 5},
]

_TABLE_SECTIONS = [
    {"text": "Summary section with tables."},
    {"text": "More text.", "tables": {"t1": "| A | B |\n| 1 | 2 |"}},
]

_PLAIN_TEXT = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\n" * 10

_TABLE_TEXT = (
    "Intro paragraph.\n\n"
    "<table><tr><td>A</td><td>B</td></tr></table>\n\n"
    "Outro paragraph.\n\n"
    "<table><tr><td>X</td></tr></table>"
)


# ---------------------------------------------------------------------------
# PIPELINE_FOR_GENRE
# ---------------------------------------------------------------------------

class TestPipelineForGenre:
    def test_all_genres_present(self):
        assert set(PIPELINE_FOR_GENRE) == {"academic_pdf", "table_heavy", "continuous_text"}

    def test_academic_pdf_maps_to_structured(self):
        assert PIPELINE_FOR_GENRE["academic_pdf"] == "structured_hierarchical"

    def test_table_heavy_maps_to_table_heavy(self):
        assert PIPELINE_FOR_GENRE["table_heavy"] == "table_heavy"

    def test_continuous_text_maps_to_continuous_text(self):
        assert PIPELINE_FOR_GENRE["continuous_text"] == "continuous_text"


# ---------------------------------------------------------------------------
# route_sections
# ---------------------------------------------------------------------------

class TestRouteSectionsAcademicPdf:
    def test_returns_chunks(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        assert len(chunks) > 0

    def test_pipeline_is_structured_hierarchical(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        assert all(c.pipeline == "structured_hierarchical" for c in chunks)

    def test_section_path_populated(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        paths = [c.section_path for c in chunks if c.section_path]
        assert len(paths) > 0

    def test_doc_genre_preserved(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        assert all(c.doc_genre == "academic_pdf" for c in chunks)

    def test_chunk_ids_contain_doc_id(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        assert all("doc1" in c.chunk_id for c in chunks)

    def test_chunk_ids_are_unique(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf", **_BASE)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


class TestRouteSectionsTableHeavy:
    def test_returns_chunks(self):
        chunks = route_sections(_TABLE_SECTIONS, "table_heavy", **_BASE)
        assert len(chunks) > 0

    def test_pipeline_is_continuous_text(self):
        # ORB tables are Markdown strings, not HTML — continuous_text is correct
        chunks = route_sections(_TABLE_SECTIONS, "table_heavy", **_BASE)
        assert all(c.pipeline == "continuous_text" for c in chunks)

    def test_doc_genre_preserved(self):
        chunks = route_sections(_TABLE_SECTIONS, "table_heavy", **_BASE)
        assert all(c.doc_genre == "table_heavy" for c in chunks)


class TestRouteSectionsContinuousText:
    def test_pipeline_is_continuous_text(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "continuous_text", **_BASE)
        assert all(c.pipeline == "continuous_text" for c in chunks)

    def test_doc_genre_preserved(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "continuous_text", **_BASE)
        assert all(c.doc_genre == "continuous_text" for c in chunks)


class TestRouteSectionsEmpty:
    def test_empty_sections(self):
        assert route_sections([], "academic_pdf", **_BASE) == []

    def test_blank_text_sections(self):
        chunks = route_sections([{"text": ""}], "academic_pdf", **_BASE)
        assert chunks == []


# ---------------------------------------------------------------------------
# route_text
# ---------------------------------------------------------------------------

class TestRouteTextTableHeavy:
    def test_returns_chunks(self):
        chunks = route_text(_TABLE_TEXT, "table_heavy", **_BASE)
        assert len(chunks) > 0

    def test_pipeline_is_table_heavy(self):
        chunks = route_text(_TABLE_TEXT, "table_heavy", **_BASE)
        assert all(c.pipeline == "table_heavy" for c in chunks)

    def test_table_chunks_are_atomic(self):
        chunks = route_text(_TABLE_TEXT, "table_heavy", **_BASE)
        table_chunks = [c for c in chunks if "<table" in c.text.lower()]
        for tc in table_chunks:
            assert tc.text.lower().count("<table") == tc.text.lower().count("</table>"), (
                f"Truncated table in chunk: {tc.chunk_id}"
            )

    def test_doc_genre_preserved(self):
        chunks = route_text(_TABLE_TEXT, "table_heavy", **_BASE)
        assert all(c.doc_genre == "table_heavy" for c in chunks)

    def test_page_number_stored(self):
        chunks = route_text(_TABLE_TEXT, "table_heavy", **_BASE, page=3)
        assert all(c.page == 3 for c in chunks)

    def test_seq_offset_applied(self):
        chunks = route_text(_PLAIN_TEXT, "table_heavy", **_BASE, seq_offset=10)
        first_seq = int(chunks[0].chunk_id.split(":")[-1])
        assert first_seq == 10


class TestRouteTextContinuousText:
    def test_pipeline_is_continuous_text(self):
        chunks = route_text(_PLAIN_TEXT, "continuous_text", **_BASE)
        assert all(c.pipeline == "continuous_text" for c in chunks)

    def test_returns_chunks(self):
        chunks = route_text(_PLAIN_TEXT, "continuous_text", **_BASE)
        assert len(chunks) > 0


class TestRouteTextAcademicPdf:
    def test_falls_back_to_continuous_text(self):
        # Without section dicts, academic_pdf falls back to continuous_text
        chunks = route_text(_PLAIN_TEXT, "academic_pdf", **_BASE)
        assert all(c.pipeline == "continuous_text" for c in chunks)

    def test_doc_genre_preserved(self):
        chunks = route_text(_PLAIN_TEXT, "academic_pdf", **_BASE)
        assert all(c.doc_genre == "academic_pdf" for c in chunks)


class TestRouteTextEmpty:
    def test_empty_text(self):
        assert route_text("", "table_heavy", **_BASE) == []

    def test_whitespace_only(self):
        assert route_text("   \n  ", "continuous_text", **_BASE) == []


# ---------------------------------------------------------------------------
# Cross-cutting: dataset_id and source_uri propagation
# ---------------------------------------------------------------------------

class TestFieldPropagation:
    def test_dataset_id_in_chunk_id(self):
        chunks = route_sections(_SIMPLE_SECTIONS, "academic_pdf",
                                doc_id="mypaper", dataset_id="myds",
                                source_uri="http://x.com")
        assert all(c.chunk_id.startswith("myds:") for c in chunks)

    def test_source_uri_stored(self):
        chunks = route_text(_PLAIN_TEXT, "continuous_text",
                            doc_id="d1", dataset_id="ds", source_uri="http://example.org")
        assert all(c.source_uri == "http://example.org" for c in chunks)
