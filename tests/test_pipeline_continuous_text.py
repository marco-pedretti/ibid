"""I-03: unit tests for the continuous_text chunking pipeline."""

from __future__ import annotations


from src.datasets.schema import Chunk
from src.ingestion.pipeline_continuous_text import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OVERLAP,
    _group_paragraphs,
    _split_paragraphs,
    chunk_document,
)


# --- _split_paragraphs ---

def test_split_empty():
    assert _split_paragraphs("") == []


def test_split_single_para():
    assert _split_paragraphs("Hello world.") == ["Hello world."]


def test_split_two_paras():
    result = _split_paragraphs("First.\n\nSecond.")
    assert result == ["First.", "Second."]


def test_split_strips_whitespace():
    result = _split_paragraphs("  First.  \n\n  Second.  ")
    assert result == ["First.", "Second."]


def test_split_ignores_blank_paragraphs():
    result = _split_paragraphs("A.\n\n\n\nB.")
    assert result == ["A.", "B."]


def test_split_single_newline_not_split():
    # Single \n is NOT a paragraph boundary — only \n\n is.
    result = _split_paragraphs("Line one.\nLine two.")
    assert result == ["Line one.\nLine two."]


# --- _group_paragraphs ---

def test_group_empty():
    assert _group_paragraphs([], chunk_size=100, overlap=20) == []


def test_group_single_short_para():
    result = _group_paragraphs(["Hello."], chunk_size=1000, overlap=200)
    assert result == ["Hello."]


def test_group_two_short_paras_fit_in_one_chunk():
    # Both paragraphs are short; together they fit under chunk_size.
    result = _group_paragraphs(["A.", "B."], chunk_size=1000, overlap=200)
    assert result == ["A.\n\nB."]


def test_group_splits_when_exceeding_chunk_size():
    long = "x" * 600
    result = _group_paragraphs([long, long], chunk_size=1000, overlap=200)
    assert len(result) == 2


def test_group_overlap_content_shared():
    # P1 (800 chars) + P2 (800 chars) → two chunks, P2 appears in both.
    p1 = "a" * 800
    p2 = "b" * 800
    chunks = _group_paragraphs([p1, p2], chunk_size=1000, overlap=300)
    assert len(chunks) == 2
    assert p2 in chunks[0]  # P2 appears at end of first chunk
    assert p2 in chunks[1]  # P2 also starts second chunk


def test_group_paragraph_longer_than_chunk_size():
    # A paragraph longer than chunk_size is emitted as its own chunk.
    giant = "g" * 5000
    chunks = _group_paragraphs([giant], chunk_size=1000, overlap=200)
    assert chunks == [giant]


def test_group_no_empty_chunks():
    paras = ["x" * 300] * 10
    chunks = _group_paragraphs(paras, chunk_size=500, overlap=100)
    assert all(len(c) > 0 for c in chunks)


def test_group_always_advances():
    # When overlap >= chunk_size the algorithm must still terminate and produce
    # at most N chunks for N paragraphs (no infinite loop from a stuck window).
    paras = [f"para{i} " * 20 for i in range(5)]  # distinct content
    chunks = _group_paragraphs(paras, chunk_size=80, overlap=200)
    assert 1 <= len(chunks) <= len(paras) + 1  # bounded output
    # No empty chunk.
    assert all(c for c in chunks)


def test_group_zero_overlap():
    # overlap=0 means windows do not share paragraphs.
    p1, p2 = "a" * 600, "b" * 600
    chunks = _group_paragraphs([p1, p2], chunk_size=500, overlap=0)
    # p1 alone fills chunk_size; then p2 is separate.
    assert len(chunks) == 2
    assert p2 not in chunks[0]


# --- chunk_document ---

def _base_kwargs(**overrides) -> dict:
    return {
        "doc_id": "doc1",
        "dataset_id": "ds",
        "doc_genre": "continuous_text",
        "source_uri": "https://example.com/doc1",
        **overrides,
    }


def test_chunk_document_empty_text():
    chunks = chunk_document("", **_base_kwargs())
    assert chunks == []


def test_chunk_document_returns_chunk_objects():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = chunk_document(text, **_base_kwargs(), chunk_size=100, overlap=10)
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunk_document_schema_fields():
    text = "A paragraph with enough words to matter here."
    chunks = chunk_document(text, **_base_kwargs())
    c = chunks[0]
    assert c.dataset_id == "ds"
    assert c.doc_id == "doc1"
    assert c.doc_genre == "continuous_text"
    assert c.pipeline == "continuous_text"
    assert c.section_path == ""
    assert c.bbox is None
    assert c.content_type == "text"
    assert c.source_uri == "https://example.com/doc1"


def test_chunk_document_chunk_id_format():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_document(text, **_base_kwargs(), chunk_size=1, overlap=0)
    assert chunks[0].chunk_id == "ds:doc1:0000"
    assert chunks[1].chunk_id == "ds:doc1:0001"
    assert chunks[2].chunk_id == "ds:doc1:0002"


def test_chunk_document_seq_offset():
    text = "Single paragraph."
    chunks = chunk_document(text, **_base_kwargs(), seq_offset=10)
    assert chunks[0].chunk_id == "ds:doc1:0010"


def test_chunk_document_page_field():
    text = "A page of text."
    chunks = chunk_document(text, **_base_kwargs(), page=5)
    assert chunks[0].page == 5


def test_chunk_document_no_empty_text_chunks():
    text = "\n\n".join(["word " * 50] * 20)
    chunks = chunk_document(text, **_base_kwargs(), chunk_size=200, overlap=50)
    assert all(c.text.strip() for c in chunks)


def test_chunk_document_default_params_exist():
    # Smoke test: default chunk_size and overlap produce valid output.
    text = "\n\n".join(["A sentence. " * 20] * 10)
    chunks = chunk_document(text, **_base_kwargs())
    assert len(chunks) >= 1
    assert DEFAULT_CHUNK_SIZE > 0
    assert DEFAULT_OVERLAP > 0
    assert DEFAULT_OVERLAP < DEFAULT_CHUNK_SIZE
