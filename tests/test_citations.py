"""T-06 — unit tests for citation marker parser.

Covers the malformed forms the model is known to produce, plus boundary cases.
"""

from src.generation.citations import extract_cited, filter_valid, normalize, parse


class TestNormalize:
    def test_valid_unchanged(self):
        assert normalize("Il valore è 400ms [2][3].") == "Il valore è 400ms [2][3]."

    def test_dash_between_markers(self):
        assert normalize("testo [1]-[2] fine") == "testo [1][2] fine"

    def test_comma_two(self):
        assert normalize("testo [1,2] fine") == "testo [1][2] fine"

    def test_comma_space_two(self):
        assert normalize("testo [1, 2] fine") == "testo [1][2] fine"

    def test_comma_three(self):
        assert normalize("testo [1,2,3] fine") == "testo [1][2][3] fine"

    def test_italian_and(self):
        assert normalize("testo [1 e 2] fine") == "testo [1][2] fine"

    def test_english_and(self):
        assert normalize("testo [1 and 2] fine") == "testo [1][2] fine"

    def test_english_and_case_insensitive(self):
        assert normalize("testo [1 AND 2] fine") == "testo [1][2] fine"

    def test_range_two(self):
        assert normalize("testo [1-2] fine") == "testo [1][2] fine"

    def test_range_three(self):
        assert normalize("testo [1-3] fine") == "testo [1][2][3] fine"

    def test_range_en_dash(self):
        assert normalize("testo [1–3] fine") == "testo [1][2][3] fine"

    def test_range_inverted_unchanged(self):
        # [3-1] is not a valid range — leave as-is rather than silently drop
        result = normalize("testo [3-1] fine")
        assert "[3-1]" in result or result == "testo [3-1] fine"

    def test_multiple_malformed_forms(self):
        text = "A [1,2]. B [3]-[4]. C [5 e 6]."
        result = normalize(text)
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
        # [1,6] with n_chunks=3 → normalize to [1][6] → filter to [1]
        assert parse("testo [1,6] fine", 3) == "testo [1] fine"

    def test_real_output_comma_form(self):
        raw = "I modelli sono stati confrontati [1,2]."
        assert parse(raw, 2) == "I modelli sono stati confrontati [1][2]."

    def test_real_output_range_out_of_context(self):
        # [2-5] with only 3 chunks → [2][3] kept, [4][5] dropped
        result = parse("Il confronto è descritto [2-5].", 3)
        assert "[2]" in result
        assert "[3]" in result
        assert "[4]" not in result
        assert "[5]" not in result

    def test_real_output_italian_and_partial_valid(self):
        # [1 e 4] with n_chunks=3 → normalize to [1][4] → filter to [1]
        raw = "Il modello supera la baseline [1 e 4]."
        result = parse(raw, 3)
        assert "[1]" in result
        assert "[4]" not in result

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
