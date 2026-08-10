"""T-06 — unit tests for citation marker parser.

Covers the malformed forms the model is known to produce, plus boundary cases.

Written before any generation existed, so "known to produce" meant "expected to
produce".  C-02 measured which of these actually occur and reversed one of the
decisions taken here — see `TestOverflowingConstructs` below and
`test_citations_real.py` for the corpus that forced it.  The `n_chunks` argument
threaded through `normalize` arrived with that change; the value 10 is simply
large enough that these cases keep testing what they were written to test.
"""

from src.generation.citations import extract_cited, filter_valid, normalize, parse


class TestNormalize:
    def test_valid_unchanged(self):
        assert normalize("Il valore è 400ms [2][3].", 10) == "Il valore è 400ms [2][3]."

    def test_dash_between_markers(self):
        assert normalize("testo [1]-[2] fine", 10) == "testo [1][2] fine"

    def test_comma_two(self):
        assert normalize("testo [1,2] fine", 10) == "testo [1][2] fine"

    def test_comma_space_two(self):
        assert normalize("testo [1, 2] fine", 10) == "testo [1][2] fine"

    def test_comma_three(self):
        assert normalize("testo [1,2,3] fine", 10) == "testo [1][2][3] fine"

    def test_italian_and(self):
        assert normalize("testo [1 e 2] fine", 10) == "testo [1][2] fine"

    def test_english_and(self):
        assert normalize("testo [1 and 2] fine", 10) == "testo [1][2] fine"

    def test_english_and_case_insensitive(self):
        assert normalize("testo [1 AND 2] fine", 10) == "testo [1][2] fine"

    def test_range_two(self):
        assert normalize("testo [1-2] fine", 10) == "testo [1][2] fine"

    def test_range_three(self):
        assert normalize("testo [1-3] fine", 10) == "testo [1][2][3] fine"

    def test_range_en_dash(self):
        assert normalize("testo [1–3] fine", 10) == "testo [1][2][3] fine"

    def test_range_inverted_unchanged(self):
        # [3-1] is not a valid range — leave as-is rather than silently drop
        result = normalize("testo [3-1] fine", 10)
        assert "[3-1]" in result or result == "testo [3-1] fine"

    def test_multiple_malformed_forms(self):
        text = "A [1,2]. B [3]-[4]. C [5 e 6]."
        result = normalize(text, 10)
        assert result == "A [1][2]. B [3][4]. C [5][6]."


class TestFilterValid:
    def test_keeps_all_valid(self):
        assert filter_valid("Il valore è 400ms [1][2].", 5) == "Il valore è 400ms [1][2]."

    def test_drops_over_limit(self):
        assert filter_valid("Il valore è [1][6].", 5) == "Il valore è [1]."

    def test_drops_zero(self):
        assert filter_valid("[0] testo", 5) == " testo"

    def test_all_invalid(self):
        assert filter_valid("[7][8][9]", 5) == ""

    def test_exactly_n_kept(self):
        assert filter_valid("[5]", 5) == "[5]"

    def test_n_plus_one_dropped(self):
        assert filter_valid("[6]", 5) == ""

    def test_single_chunk(self):
        assert filter_valid("risposta [1].", 1) == "risposta [1]."
        assert filter_valid("risposta [2].", 1) == "risposta ."


class TestParse:
    def test_valid_passthrough(self):
        raw = "Il valore massimo è 400ms [2][3]."
        assert parse(raw, 5) == raw

    def test_normalizes_then_filters(self):
        # [1,2] with n_chunks=3 → both in context → normalize to [1][2]
        assert parse("testo [1,2] fine", 3) == "testo [1][2] fine"

    def test_real_output_comma_form(self):
        raw = "I modelli sono stati confrontati [1,2]."
        assert parse(raw, 2) == "I modelli sono stati confrontati [1][2]."

    def test_all_markers_invalid_text_preserved(self):
        raw = "La risposta è 42 [9][10]."
        result = parse(raw, 5)
        assert result == "La risposta è 42 ."

    def test_no_markers(self):
        raw = "Non ho informazioni sufficienti."
        assert parse(raw, 5) == raw


class TestExtractCited:
    def test_empty_string(self):
        assert extract_cited("nessuna citazione") == []

    def test_single(self):
        assert extract_cited("testo [3].") == [3]

    def test_sorted_unique(self):
        assert extract_cited("[3][1][2][1]") == [1, 2, 3]

    def test_no_duplicates(self):
        result = extract_cited("[1][1][1]")
        assert result == [1]


class TestOverflowingConstructs:
    """A multi-number construct is expanded only if every number fits the context.

    This reverses a T-06 decision.  The two tests that used to live in
    `TestParse` asserted that `[2-5]` against 3 chunks becomes `[2][3]` and that
    `[1 e 4]` against 3 chunks becomes `[1]` — expand first, discard the overflow
    after.  C-02 measured what such constructs really are: in 897 real answers,
    all 16 occurrences named the source document's own references, and not one
    fit its context.  Expanding them produced citations the model never made,
    indistinguishable from real ones by the time the discard step saw them.
    """

    def test_range_overflowing_the_context_is_left_alone(self):
        assert parse("Il confronto è descritto [2-5].", 3) == "Il confronto è descritto [2-5]."

    def test_conjunction_overflowing_the_context_is_left_alone(self):
        raw = "Il modello supera la baseline [1 e 4]."
        assert parse(raw, 3) == raw

    def test_comma_list_overflowing_the_context_is_left_alone(self):
        raw = "These methods [16,17,18,19] use RANSAC."
        assert parse(raw, 5) == raw

    def test_dash_joined_overflowing_the_context_is_left_alone(self):
        raw = "Previous works [1]-[21] focus on visual information."
        assert parse(raw, 5) == raw

    def test_a_construct_that_fits_is_still_expanded(self):
        # The rule costs nothing when the construct is a genuine malformed
        # citation of ours; this corpus just never contained one.
        assert parse("testo [2-4] fine", 5) == "testo [2][3][4] fine"

    def test_zero_is_not_a_chunk_index_so_math_survives(self):
        # §3.2 numbers chunks from 1. `[0,1]` is an interval, and the old rule
        # turned it into `[0][1]` and then into `[1]` — a fabricated citation
        # inside a formula. Same reasoning as `citation_format._is_citation_attempt`.
        raw = r"$\Psi_{r} \subseteq[0,1]^{p}$ [1]"
        assert parse(raw, 5) == raw

    def test_the_valid_half_of_an_overflowing_pair_is_not_left_dangling(self):
        # Stripping only [21] would leave "works [1]- focus", which reads as a
        # citation of chunk 1 that the model never made.
        assert "[1]-" not in parse("works [1]-[21] focus", 5).replace("[1]-[21]", "")
