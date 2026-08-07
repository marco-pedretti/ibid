"""T-04: unit tests for schema validation and open_ragbench chunk normalization."""

import json
from pathlib import Path


from src.datasets.schema import Chunk
from src.datasets.open_ragbench import iter_chunks, DATASET_ID


# ---------------------------------------------------------------------------
# Chunk schema
# ---------------------------------------------------------------------------

def _make_chunk(**overrides) -> dict:
    base = dict(
        chunk_id="open_ragbench:2405.08806v2:3",
        dataset_id="open_ragbench",
        doc_id="2405.08806v2",
        doc_genre="academic_pdf",
        pipeline="continuous_text",
        section_path="",
        page=0,
        bbox=None,
        content_type="text",
        text="Some section text.",
        source_uri="https://arxiv.org/abs/2405.08806",
    )
    base.update(overrides)
    return base


def test_chunk_valid():
    chunk = Chunk(**_make_chunk())
    assert chunk.dataset_id == "open_ragbench"
    assert chunk.bbox is None


def test_chunk_with_bbox():
    chunk = Chunk(**_make_chunk(bbox=(10.0, 20.0, 300.0, 400.0)))
    assert chunk.bbox == (10.0, 20.0, 300.0, 400.0)


def test_chunk_id_format():
    chunk = Chunk(**_make_chunk())
    parts = chunk.chunk_id.split(":")
    assert len(parts) == 3
    assert parts[0] == chunk.dataset_id
    assert parts[1] == chunk.doc_id


# ---------------------------------------------------------------------------
# open_ragbench iter_chunks
# ---------------------------------------------------------------------------

def _write_corpus(tmp_path: Path, doc_id: str, sections: list) -> None:
    corpus_dir = tmp_path / "pdf" / "arxiv" / "corpus"
    corpus_dir.mkdir(parents=True)
    doc = {"id": doc_id, "title": "Test Paper", "sections": sections,
           "authors": [], "categories": [], "abstract": "", "updated": "", "published": ""}
    (corpus_dir / f"{doc_id}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_iter_chunks_text_section(tmp_path):
    _write_corpus(tmp_path, "2401.00001v1", [
        {"section_id": 0, "text": "Introduction text.", "tables": {}, "images": {}},
    ])
    chunks = list(iter_chunks(tmp_path))
    assert len(chunks) == 1
    assert chunks[0].content_type == "text"
    assert chunks[0].dataset_id == DATASET_ID
    assert chunks[0].chunk_id == f"{DATASET_ID}:2401.00001v1:0"


def test_iter_chunks_table_section(tmp_path):
    _write_corpus(tmp_path, "2401.00002v1", [
        {"section_id": 1, "text": "", "tables": {"table_0": "| A | B |\n|---|---|\n| 1 | 2 |"}, "images": {}},
    ])
    chunks = list(iter_chunks(tmp_path))
    assert len(chunks) == 1
    assert chunks[0].content_type == "table"
    assert "| A | B |" in chunks[0].text


def test_iter_chunks_mixed_section(tmp_path):
    _write_corpus(tmp_path, "2401.00003v1", [
        {"section_id": 2, "text": "Some text.", "tables": {"table_0": "| X |\n|---|\n| 1 |"}, "images": {}},
    ])
    chunks = list(iter_chunks(tmp_path))
    assert len(chunks) == 1
    assert chunks[0].content_type == "mixed"
    assert "Some text." in chunks[0].text
    assert "| X |" in chunks[0].text


def test_iter_chunks_empty_section_skipped(tmp_path):
    _write_corpus(tmp_path, "2401.00004v1", [
        {"section_id": 0, "text": "", "tables": {}, "images": {}},
        {"section_id": 1, "text": "Real content.", "tables": {}, "images": {}},
    ])
    chunks = list(iter_chunks(tmp_path))
    assert len(chunks) == 1
    assert chunks[0].text == "Real content."


def test_iter_chunks_figure_caption(tmp_path):
    _write_corpus(tmp_path, "2401.00005v1", [
        {"section_id": 3, "text": "", "tables": {},
         "images": {"img-0.jpeg": "data:image/jpeg;base64,AAAA"}},
    ])
    chunks = list(iter_chunks(tmp_path))
    # image-only section with no text → skipped (no text content to index)
    assert len(chunks) == 0


def test_iter_chunks_source_uri(tmp_path):
    _write_corpus(tmp_path, "2401.00001v2", [
        {"section_id": 0, "text": "Text.", "tables": {}, "images": {}},
    ])
    chunks = list(iter_chunks(tmp_path))
    assert chunks[0].source_uri == "https://arxiv.org/abs/2401.00001"
