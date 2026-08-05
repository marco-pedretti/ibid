"""I-01: unit tests for document profiler."""

from src.datasets.schema import Chunk
from src.profiling.profiler import (
    DocProfile,
    dataset_summary,
    format_report,
    profile_from_chunks,
)


def _chunk(doc_id: str, content_type: str, text: str = "hello world") -> Chunk:
    return Chunk(
        chunk_id=f"ds:{doc_id}:0",
        dataset_id="ds",
        doc_id=doc_id,
        doc_genre="academic_pdf",
        pipeline="continuous_text",
        section_path="",
        page=0,
        bbox=None,
        content_type=content_type,
        text=text,
        source_uri="https://example.com",
    )


# --- profile_from_chunks ---

def test_empty_input_returns_empty():
    assert profile_from_chunks([]) == []


def test_single_text_doc():
    chunks = [_chunk("doc1", "text", "hello world")]
    profiles = profile_from_chunks(chunks)
    assert len(profiles) == 1
    p = profiles[0]
    assert p.doc_id == "doc1"
    assert p.dataset_id == "ds"
    assert p.n_sections == 1
    assert p.n_chars == len("hello world")
    assert p.has_text_layer is True
    assert p.n_table_sections == 0
    assert p.n_image_sections == 0
    assert p.table_density == 0.0
    assert p.image_density == 0.0


def test_table_density_correct():
    chunks = [
        _chunk("doc1", "text"),
        _chunk("doc1", "table"),
        _chunk("doc1", "table"),
        _chunk("doc1", "text"),
    ]
    p = profile_from_chunks(chunks)[0]
    assert p.n_sections == 4
    assert p.n_table_sections == 2
    assert abs(p.table_density - 0.5) < 1e-9


def test_image_density_correct():
    chunks = [
        _chunk("doc1", "figure_caption"),
        _chunk("doc1", "text"),
        _chunk("doc1", "text"),
    ]
    p = profile_from_chunks(chunks)[0]
    assert p.n_image_sections == 1
    assert abs(p.image_density - 1 / 3) < 1e-9


def test_mixed_counts_as_both_table_and_image():
    chunks = [_chunk("doc1", "mixed")]
    p = profile_from_chunks(chunks)[0]
    assert p.n_table_sections == 1
    assert p.n_image_sections == 1
    assert p.table_density == 1.0
    assert p.image_density == 1.0


def test_has_text_layer_false_when_only_figures():
    chunks = [
        _chunk("doc1", "figure_caption"),
        _chunk("doc1", "figure_caption"),
    ]
    p = profile_from_chunks(chunks)[0]
    assert p.has_text_layer is False


def test_has_text_layer_true_for_mixed():
    chunks = [_chunk("doc1", "mixed")]
    p = profile_from_chunks(chunks)[0]
    assert p.has_text_layer is True


def test_avg_section_len():
    chunks = [
        _chunk("doc1", "text", "ab"),    # 2 chars
        _chunk("doc1", "text", "abcd"),  # 4 chars
    ]
    p = profile_from_chunks(chunks)[0]
    assert p.n_chars == 6
    assert abs(p.avg_section_len - 3.0) < 1e-9


def test_groups_by_doc_id():
    chunks = [
        _chunk("doc1", "text"),
        _chunk("doc2", "table"),
        _chunk("doc1", "table"),
    ]
    profiles = profile_from_chunks(chunks)
    assert len(profiles) == 2
    by_id = {p.doc_id: p for p in profiles}
    assert by_id["doc1"].n_sections == 2
    assert by_id["doc2"].n_sections == 1


def test_profiles_sorted_by_doc_id():
    chunks = [_chunk("doc_b", "text"), _chunk("doc_a", "text")]
    profiles = profile_from_chunks(chunks)
    assert profiles[0].doc_id == "doc_a"
    assert profiles[1].doc_id == "doc_b"


def test_genre_assigned_not_empty():
    # genre is now computed by assign_genre, never left blank
    p = profile_from_chunks([_chunk("doc1", "text")])[0]
    assert p.doc_genre in {"table_heavy", "academic_pdf", "continuous_text"}
    assert p.n_pages == 0


# --- dataset_summary ---

def test_summary_empty():
    assert dataset_summary([]) == {}


def test_summary_basic():
    chunks = [
        _chunk("doc1", "text", "hello"),
        _chunk("doc1", "table", "world"),
        _chunk("doc2", "text", "foo"),
    ]
    profiles = profile_from_chunks(chunks)
    s = dataset_summary(profiles)
    assert s["n_docs"] == 2
    assert s["total_sections"] == 3
    assert s["pct_with_text"] == 100.0
    assert s["mean_table_density"] > 0


def test_summary_pct_with_text():
    # doc1 has text, doc2 has only figures
    chunks = [
        _chunk("doc1", "text"),
        _chunk("doc2", "figure_caption"),
    ]
    profiles = profile_from_chunks(chunks)
    s = dataset_summary(profiles)
    assert s["pct_with_text"] == 50.0


# --- format_report ---

def test_report_nonempty():
    chunks = [_chunk("doc1", "text", "hello world")]
    profiles = profile_from_chunks(chunks)
    report = format_report(profiles)
    assert "ds" in report
    assert "Documents" in report


def test_report_empty():
    assert format_report([]) == "(no documents profiled)"
