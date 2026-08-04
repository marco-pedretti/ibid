"""T-05: unit tests for prompt builder and citation format."""

from src.datasets.schema import Chunk
from src.generation.prompt import SYSTEM, build_user_message


def _chunk(i: int, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"open_ragbench:doc:{i}",
        dataset_id="open_ragbench",
        doc_id="doc",
        doc_genre="academic_pdf",
        pipeline="continuous_text",
        section_path="",
        page=0,
        bbox=None,
        content_type="text",
        text=text,
        source_uri="https://arxiv.org/abs/1234.5678",
    )


def test_system_prompt_has_citation_example():
    # ROADMAP §3.2: format must be shown via example, not just described
    assert "[2][3]" in SYSTEM
    assert "[n]" in SYSTEM


def test_system_prompt_forbids_comma_form():
    assert "[1,2]" in SYSTEM  # must be mentioned as forbidden


def test_build_numbers_chunks():
    chunks = [_chunk(i, f"Text {i}.") for i in range(3)]
    msg = build_user_message("Q?", chunks)
    assert "[1] Text 0." in msg
    assert "[2] Text 1." in msg
    assert "[3] Text 2." in msg
    assert "[4]" not in msg


def test_build_includes_query():
    msg = build_user_message("What is entropy?", [_chunk(0, "Some text.")])
    assert "What is entropy?" in msg


def test_build_includes_chunk_text():
    msg = build_user_message("Q?", [_chunk(0, "The sky is blue.")])
    assert "The sky is blue." in msg


def test_build_empty_chunks():
    msg = build_user_message("Q?", [])
    assert "Domanda: Q?" in msg
