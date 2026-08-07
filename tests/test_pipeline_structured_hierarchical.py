"""I-04: unit tests for the structured_hierarchical chunking pipeline."""

from __future__ import annotations


from src.datasets.schema import Chunk
from src.ingestion.pipeline_structured_hierarchical import (
    _PathTracker,
    _parse_section,
    chunk_document,
)


# --- _parse_section ---

def test_parse_level1_heading():
    level, heading, body = _parse_section("# Introduction\n\nBody text here.")
    assert level == 1
    assert heading == "Introduction"
    assert body == "Body text here."


def test_parse_level2_heading():
    level, heading, body = _parse_section("## 3.2 Model\n\nModel description.")
    assert level == 2
    assert heading == "3.2 Model"
    assert body == "Model description."


def test_parse_level4_heading():
    level, heading, body = _parse_section("#### Abstract\n\nThis paper studies...")
    assert level == 4
    assert heading == "Abstract"


def test_parse_strips_trailing_punctuation():
    level, heading, body = _parse_section("# 3. Methods.\n\nSome text.")
    assert heading == "3. Methods"  # trailing period stripped


def test_parse_no_heading():
    level, heading, body = _parse_section("Just plain text, no heading.")
    assert level == 0
    assert heading == ""
    assert body == "Just plain text, no heading."


def test_parse_heading_only_no_body():
    level, heading, body = _parse_section("## Conclusion")
    assert level == 2
    assert heading == "Conclusion"
    assert body == ""


def test_parse_heading_body_separation():
    text = "# Methods\n\nFirst paragraph.\n\nSecond paragraph."
    _, _, body = _parse_section(text)
    assert body == "First paragraph.\n\nSecond paragraph."


# --- _PathTracker ---

def test_tracker_single_push():
    t = _PathTracker()
    assert t.push(2, "Methods") == "Methods"


def test_tracker_child_extends_path():
    t = _PathTracker()
    t.push(2, "Methods")
    assert t.push(3, "Model") == "Methods > Model"


def test_tracker_sibling_replaces_child():
    t = _PathTracker()
    t.push(2, "Methods")
    t.push(3, "Model")
    assert t.push(3, "Results") == "Methods > Results"


def test_tracker_new_top_level_resets():
    t = _PathTracker()
    t.push(2, "Methods")
    t.push(3, "Model")
    assert t.push(1, "Appendix") == "Appendix"


def test_tracker_same_level_replaces():
    t = _PathTracker()
    t.push(1, "Introduction")
    assert t.push(1, "Methods") == "Methods"


def test_tracker_three_levels():
    t = _PathTracker()
    t.push(1, "Part A")
    t.push(2, "Chapter 1")
    path = t.push(3, "Section 1.1")
    assert path == "Part A > Chapter 1 > Section 1.1"


# --- chunk_document ---

def _base(**overrides) -> dict:
    return {
        "doc_id": "doc1",
        "dataset_id": "ds",
        "doc_genre": "academic_pdf",
        "source_uri": "https://arxiv.org/abs/1234.5678",
        **overrides,
    }


def test_empty_sections():
    assert chunk_document([], **_base()) == []


def test_blank_section_skipped():
    result = chunk_document([{"text": "   "}], **_base())
    assert result == []


def test_single_section_produces_chunk():
    secs = [{"text": "## Introduction\n\nThis paper proposes a new approach."}]
    chunks = chunk_document(secs, **_base())
    assert len(chunks) == 1
    assert isinstance(chunks[0], Chunk)


def test_section_path_populated():
    secs = [{"text": "## Methods\n\nWe used a neural network."}]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].section_path == "Methods"


def test_section_path_hierarchy():
    secs = [
        {"text": "## Methods\n\nOverview of methods."},
        {"text": "### 3.1 Dataset\n\nWe collected data."},
    ]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].section_path == "Methods"
    assert chunks[1].section_path == "Methods > 3.1 Dataset"


def test_section_path_sibling_sections():
    secs = [
        {"text": "## Methods\n\nMethods body."},
        {"text": "## Results\n\nResults body."},
    ]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].section_path == "Methods"
    assert chunks[1].section_path == "Results"


def test_pipeline_field():
    secs = [{"text": "## Abstract\n\nSummary."}]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].pipeline == "structured_hierarchical"


def test_chunk_id_format():
    secs = [
        {"text": "## Intro\n\nFirst."},
        {"text": "## Methods\n\nSecond."},
    ]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].chunk_id == "ds:doc1:0000"
    assert chunks[1].chunk_id == "ds:doc1:0001"


def test_long_section_sub_chunked():
    body = "\n\n".join(["word " * 60] * 10)  # ~3000 chars per paragraph * 10
    secs = [{"text": f"## Methods\n\n{body}"}]
    chunks = chunk_document(secs, **_base(), chunk_size=1000, overlap=200)
    assert len(chunks) > 1
    # All sub-chunks share the same section_path
    assert all(c.section_path == "Methods" for c in chunks)


def test_sub_chunks_sequential_ids():
    body = "\n\n".join(["word " * 60] * 8)
    secs = [{"text": f"## Methods\n\n{body}"}]
    chunks = chunk_document(secs, **_base(), chunk_size=500, overlap=100)
    ids = [c.chunk_id for c in chunks]
    expected = [f"ds:doc1:{i:04d}" for i in range(len(ids))]
    assert ids == expected


def test_content_type_text():
    secs = [{"text": "## Intro\n\nPlain text.", "tables": {}, "images": {}}]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].content_type == "text"


def test_content_type_mixed():
    secs = [{"text": "## Results\n\nSee table.", "tables": {"t1": "| a | b |"}, "images": {}}]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].content_type == "mixed"


def test_content_type_table_only():
    secs = [{"text": "## T\n\n", "tables": {"t1": "| a | b |"}, "images": {}}]
    chunks = chunk_document(secs, **_base())
    assert chunks[0].content_type == "table"


def test_heading_only_section():
    secs = [{"text": "## Conclusion"}]
    chunks = chunk_document(secs, **_base())
    assert len(chunks) == 1
    assert chunks[0].section_path == "Conclusion"
    assert chunks[0].text  # non-empty


def test_no_heading_inherits_path():
    secs = [
        {"text": "## Methods\n\nIntro to methods."},
        {"text": "Continuation without a heading."},
    ]
    chunks = chunk_document(secs, **_base())
    # Second section has no heading; should inherit "Methods" path
    assert chunks[1].section_path == "Methods"


def test_dataset_id_and_doc_id_propagated():
    secs = [{"text": "## S\n\nText."}]
    chunks = chunk_document(secs, **_base(doc_id="arxiv_001", dataset_id="orb"))
    assert chunks[0].dataset_id == "orb"
    assert chunks[0].doc_id == "arxiv_001"
