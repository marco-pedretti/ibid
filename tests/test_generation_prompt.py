"""T-05 / C-01: unit tests for the prompt builder and the citation format.

The C-01 assertions come from measured failures, not from taste: each one names
a defect that appeared in the first 200-query run and that the prompt now tries
to prevent.  If a future edit drops one of these instructions, the test says
which measurement it came from.
"""

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
    assert "[2, 3]" in SYSTEM


def test_system_prompt_forbids_spaced_markers():
    # 7 answers of 192 used "[1] [3]" in the second C-01 run.
    assert "[2] [3]" in SYSTEM


def test_system_prompt_forbids_dash_and_range():
    assert "[2]-[3]" in SYSTEM
    assert "[2-3]" in SYSTEM


def test_system_prompt_warns_against_the_documents_own_references():
    # The dominant failure: 14 answers cited bibliography numbers out of the
    # paper ([12], [69], [121]) and 5 cited its structural labels.
    lowered = SYSTEM.lower()
    assert "bibliograph" in lowered
    assert "corollary" in lowered


def test_system_prompt_keeps_the_exact_abstention_phrase():
    # is_abstention() matches on this string; rewording it silently reclassifies
    # every refusal as a format failure.
    assert "'Insufficient information.'" in SYSTEM


class TestUserMessage:
    def test_states_the_valid_range(self):
        msg = build_user_message("Q?", [_chunk(i, f"T{i}") for i in range(5)])
        assert "[1] to [5]" in msg

    def test_single_chunk_range_is_not_a_range(self):
        msg = build_user_message("Q?", [_chunk(0, "T")])
        assert "[1] to [1]" not in msg
        assert "are [1]" in msg

    def test_numbers_every_chunk(self):
        msg = build_user_message("Q?", [_chunk(i, f"Text {i}.") for i in range(3)])
        assert "CHUNK [1]" in msg and "CHUNK [2]" in msg and "CHUNK [3]" in msg
        assert "CHUNK [4]" not in msg

    def test_delimiter_separates_the_number_from_the_text(self):
        # A bare "[1] " prefix sat flush against text that can itself open with
        # "[12]", which is how the numbering became ambiguous.
        msg = build_user_message("Q?", [_chunk(0, "[12] refers to Smith et al.")])
        assert "--- CHUNK [1] ---\n[12] refers to Smith et al." in msg

    def test_includes_query(self):
        msg = build_user_message("What is entropy?", [_chunk(0, "Some text.")])
        assert "What is entropy?" in msg

    def test_includes_chunk_text(self):
        msg = build_user_message("Q?", [_chunk(0, "The sky is blue.")])
        assert "The sky is blue." in msg

    def test_empty_chunks(self):
        msg = build_user_message("Q?", [])
        assert "Q?" in msg


class TestOutputLanguage:
    """C-05. The instruction was carried here by an early refactor and was never
    verified; `scripts/probe_language.py` verified it on 20 translated queries.
    """

    def test_the_language_instruction_is_present(self):
        assert "same language as the question" in SYSTEM

    def test_the_abstention_string_is_a_fixed_token(self):
        """It stays English on purpose. `citation_format.is_abstention` matches
        it exactly, and a phrase that varied per language would make the
        abstention rate depend on the language a query was written in.
        Localising it belongs to the UI, not the prompt."""
        from src.generation.baseline_prompts import ABSTENTION_PHRASES

        assert "reply exactly: 'Insufficient information.'" in SYSTEM
        assert "insufficient information" in ABSTENTION_PHRASES

    def test_the_prompt_does_not_name_a_language_to_answer_in(self):
        """Hardcoding "answer in English" would be a different contract, and one
        that both corpora being English today would hide until it shipped."""
        assert "in English" not in SYSTEM
