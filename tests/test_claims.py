"""C-03 — splitting an answer into the units that get verified.

The failures these exist to prevent are all ways of quietly changing the
denominator: dropping uncited sentences (which would let a model raise its own
precision by citing less), losing a marker at a sentence boundary, or sending
bracketed indices into an NLI model as part of the hypothesis.
"""

from __future__ import annotations

from src.generation.claims import (
    MIN_CLAIM_CHARS,
    Claim,
    citation_pairs,
    split_claims,
    strip_markers,
)


class TestStripMarkers:
    def test_removes_markers_and_their_leading_space(self):
        assert strip_markers("Il valore massimo è 400ms [2][3].") == "Il valore massimo è 400ms."

    def test_marker_mid_sentence(self):
        assert strip_markers("Il dato [1] è confermato.") == "Il dato è confermato."

    def test_no_markers_is_unchanged(self):
        assert strip_markers("Nessuna citazione qui.") == "Nessuna citazione qui."

    def test_does_not_touch_other_brackets(self):
        # A mathematical interval is not a citation — same rule as the parser.
        assert strip_markers(r"$x \in [0,1]$ vale [1].") == r"$x \in [0,1]$ vale."


class TestSplitClaims:
    def test_one_sentence_one_claim(self):
        c = split_claims("Il valore massimo è 400ms [2][3].")
        assert len(c) == 1
        assert c[0].markers == [2, 3]
        assert "[2]" not in c[0].text

    def test_markers_stay_with_their_own_sentence(self):
        """§3.2 puts markers before the terminator, so the split must not hand
        them to the next sentence."""
        c = split_claims("Primo fatto [1]. Secondo fatto [2].")
        assert [x.markers for x in c] == [[1], [2]]

    def test_uncited_sentence_is_kept(self):
        c = split_claims("Un fatto citato [1]. Un fatto senza fonte alcuna.")
        assert len(c) == 2
        assert c[1].markers == []
        assert not c[1].is_cited

    def test_raw_keeps_the_markers(self):
        c = split_claims("Il valore massimo è 400ms [2][3].")
        assert "[2][3]" in c[0].raw

    def test_duplicate_markers_counted_once(self):
        c = split_claims("Il dato [1] e ancora il dato [1] sono confermati.")
        assert c[0].markers == [1]

    def test_markers_sorted(self):
        assert split_claims("Fatto [3][1].")[0].markers == [1, 3]

    def test_out_of_range_markers_dropped_when_n_chunks_given(self):
        c = split_claims("Fatto [1][9].", n_chunks=5)
        assert c[0].markers == [1]

    def test_no_n_chunks_keeps_everything(self):
        assert split_claims("Fatto [9].")[0].markers == [9]

    def test_empty_answer(self):
        assert split_claims("") == []

    def test_whitespace_only(self):
        assert split_claims("   \n  ") == []

    def test_question_and_exclamation_split(self):
        assert len(split_claims("Davvero? Sì! Certo.")) == 3

    def test_abbreviations_are_not_a_special_case(self):
        """Documenting a known limit rather than pretending it away: `Fig. 3`
        splits.  The fragment is short, so `is_verifiable` excludes it from the
        metric instead of it becoming a spurious uncited claim."""
        c = split_claims("Vedi Fig. 3 per il dettaglio completo del confronto [1].")
        assert not c[0].is_verifiable


class TestVerifiable:
    def test_fragment_is_not_verifiable(self):
        assert not Claim(text="Sì.", raw="Sì.", markers=[1]).is_verifiable

    def test_full_sentence_is_verifiable(self):
        text = "x" * MIN_CLAIM_CHARS
        assert Claim(text=text, raw=text, markers=[1]).is_verifiable


class TestCitationPairs:
    def test_one_pair_per_cited_chunk(self):
        claims = split_claims(
            "Il valore massimo registrato nel test è 400ms [2][3]."
        )
        assert citation_pairs(claims) == [(claims[0], 2), (claims[0], 3)]

    def test_uncited_claim_contributes_nothing(self):
        claims = split_claims("Una affermazione lunga abbastanza ma senza fonte.")
        assert citation_pairs(claims) == []

    def test_fragments_excluded(self):
        claims = split_claims("Sì [1].")
        assert citation_pairs(claims) == []

    def test_pairs_across_sentences(self):
        claims = split_claims(
            "La prima affermazione documentata [1]. La seconda affermazione documentata [2]."
        )
        assert [m for _, m in citation_pairs(claims)] == [1, 2]
