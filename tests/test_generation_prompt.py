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


class TestContiguityReminder:
    """The rule is repeated next to the question, not only in the system prompt.

    Measured on 188 answers: `[1] [2]` was the last remaining defect (8 cases)
    while the comma form the corpus actually uses — 13.1% of open_ragbench
    chunks contain `[1,2]` — appeared in 1.  The prohibition works when it is
    read; the contiguity one had to compete with 8,000 tokens of context.
    """

    def test_reminder_sits_after_the_context(self):
        msg = build_user_message("Q?", [_chunk(0, "T")])
        assert msg.index("Reminder:") > msg.index("Context:")

    def test_reminder_sits_before_the_question(self):
        msg = build_user_message("Q?", [_chunk(0, "T")])
        assert msg.index("Reminder:") < msg.index("Question:")

    def test_reminder_shows_both_forms(self):
        msg = build_user_message("Q?", [_chunk(0, "T")])
        assert "[1][2]" in msg and "never [1] [2]" in msg
