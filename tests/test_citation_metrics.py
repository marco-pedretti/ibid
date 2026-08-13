"""C-03 — citation_precision and the numbers that keep it honest.

The verifier is injected, so these tests are about the accounting: what counts
as a pair, what belongs in which denominator, and the specific ways the headline
number can be true and misleading at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.eval.citation_metrics import (
    CitationReport,
    PairVerdict,
    build_metrics,
    summarize,
    verify_answer,
)
from src.generation.entailment import Verdict

CHUNKS = [
    {"chunk_id": "ds:doc:1", "text": "Il valore massimo misurato è 400ms."},
    {"chunk_id": "ds:doc:2", "text": "Il sistema usa una cache locale."},
    {"chunk_id": "ds:doc:3", "text": "Le misure sono state ripetute dieci volte."},
]


def verifier_for(scores: dict[str, float], default: float = 0.0, threshold: float = 0.5):
    """Verifier that scores by chunk text prefix."""
    def _v(chunk_text: str, claim: str) -> Verdict:
        s = next((v for k, v in scores.items() if k in chunk_text), default)
        return Verdict(supported=s >= threshold, score=s, n_premises=1)
    return _v


ALL_YES = lambda *_: Verdict(True, 0.99, 1)      # noqa: E731
ALL_NO = lambda *_: Verdict(False, 0.01, 1)      # noqa: E731


class TestVerifyAnswer:
    def test_one_verdict_per_cited_chunk(self):
        answer = "Il valore massimo registrato durante il test è 400ms [1][2]."
        _, v = verify_answer(answer, CHUNKS, ALL_YES)
        assert [x.marker for x in v] == [1, 2]

    def test_marker_maps_to_the_chunk_at_that_position(self):
        answer = "Il valore massimo registrato durante il test è 400ms [2]."
        _, v = verify_answer(answer, CHUNKS, ALL_YES)
        assert v[0].chunk_id == "ds:doc:2"

    def test_claim_text_reaches_the_verifier_without_markers(self):
        seen = {}

        def spy(chunk_text, claim):
            seen["claim"] = claim
            return Verdict(True, 0.9, 1)

        verify_answer("Il valore massimo registrato è 400ms [1].", CHUNKS, spy)
        assert "[1]" not in seen["claim"]

    def test_out_of_range_marker_produces_no_pair(self):
        answer = "Una affermazione sufficientemente lunga da contare [9]."
        _, v = verify_answer(answer, CHUNKS, ALL_YES)
        assert v == []

    def test_uncited_claim_produces_no_pair_but_is_returned(self):
        answer = "Una affermazione sufficientemente lunga ma senza alcuna fonte."
        claims, v = verify_answer(answer, CHUNKS, ALL_YES)
        assert v == [] and len(claims) == 1

    def test_scores_are_kept_not_only_the_boolean(self):
        _, v = verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1].",
            CHUNKS, verifier_for({"400ms": 0.49}))
        assert v[0].score == pytest.approx(0.49) and not v[0].supported


class TestPrecision:
    def test_all_supported(self):
        r = summarize([verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1][2].", CHUNKS, ALL_YES)])
        assert r.citation_precision == 1.0

    def test_none_supported(self):
        r = summarize([verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1][2].", CHUNKS, ALL_NO)])
        assert r.citation_precision == 0.0

    def test_padding_a_correct_citation_lowers_precision(self):
        """The reason the unit is the pair and not the union of a sentence's
        citations: a model that adds two irrelevant chunks to a correct one is
        doing the thing C-03 exists to catch."""
        answer = "Il valore massimo registrato durante il test è 400ms [1][2][3]."
        r = summarize([verify_answer(answer, CHUNKS, verifier_for({"400ms": 0.9}))])
        assert r.citation_precision == pytest.approx(1 / 3)

    def test_no_pairs_is_zero_not_a_crash(self):
        r = summarize([verify_answer("Nessuna citazione in questa lunga frase.", CHUNKS, ALL_YES)])
        assert r.citation_precision == 0.0


class TestRecallAndUncited:
    def test_recall_counts_claims_not_pairs(self):
        """One claim with two citations, one of them entailing: the claim is
        supported once, not twice."""
        answer = "Il valore massimo registrato durante il test è 400ms [1][2]."
        r = summarize([verify_answer(answer, CHUNKS, verifier_for({"400ms": 0.9}))])
        assert r.citation_recall == 1.0
        assert r.citation_precision == 0.5

    def test_uncited_claim_lowers_recall(self):
        answer = ("Il valore massimo registrato durante il test è 400ms [1]. "
                  "Una seconda affermazione lunga ma priva di fonte.")
        r = summarize([verify_answer(answer, CHUNKS, ALL_YES)])
        assert r.citation_recall == 0.5
        assert r.uncited_claim_rate == 0.5

    def test_citing_less_raises_precision_but_uncited_rate_exposes_it(self):
        """Precision alone is gamed by citing less. This is the pairing that
        makes the headline number readable."""
        answer = ("Il valore massimo registrato durante il test è 400ms [1]. "
                  "Una seconda affermazione lunga ma priva di fonte. "
                  "Una terza affermazione lunga e altrettanto priva di fonte.")
        r = summarize([verify_answer(answer, CHUNKS, verifier_for({"400ms": 0.9}))])
        assert r.citation_precision == 1.0
        assert r.uncited_claim_rate == pytest.approx(2 / 3)

    def test_fragments_are_out_of_the_denominator(self):
        answer = "Sì. Il valore massimo registrato durante il test è 400ms [1]."
        r = summarize([verify_answer(answer, CHUNKS, ALL_YES)])
        assert r.n_claims == 2 and r.n_verifiable == 1


class TestWindowedRate:
    def test_zero_when_every_premise_fits(self):
        r = summarize([verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1].", CHUNKS, ALL_YES)])
        assert r.windowed_rate == 0.0

    def test_reported_when_a_premise_had_to_be_split(self):
        split = lambda *_: Verdict(True, 0.9, 4)  # noqa: E731
        r = summarize([verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1].", CHUNKS, split)])
        assert r.windowed_rate == 1.0


class TestAggregation:
    def test_across_answers(self):
        a = verify_answer("Il valore massimo registrato durante il test è 400ms [1].",
                          CHUNKS, ALL_YES)
        b = verify_answer("Il sistema adotta una cache locale per le misure [2].",
                          CHUNKS, ALL_NO)
        r = summarize([a, b])
        assert r.n_answers == 2 and r.n_pairs == 2
        assert r.citation_precision == 0.5

    def test_empty_input(self):
        r = summarize([])
        assert r.citation_precision == 0.0 and r.citation_recall == 0.0


class TestBuildMetrics:
    def test_carries_the_criterion_and_its_context(self):
        r = summarize([verify_answer(
            "Il valore massimo registrato durante il test è 400ms [1].", CHUNKS, ALL_YES)])
        m = build_metrics(r)
        for key in ("citation_precision", "citation_recall", "uncited_claim_rate",
                    "windowed_premise_rate", "citations_per_answer", "claims_per_answer"):
            assert key in m

    def test_per_answer_rates_use_the_answer_count(self):
        r = CitationReport(n_answers=4, n_claims=8, n_verifiable=8, n_uncited=0,
                           n_pairs=12, n_supported=6, n_claims_supported=6, n_windowed=0)
        m = build_metrics(r)
        assert m["claims_per_answer"] == 2.0
        assert m["citations_per_answer"] == 3.0


class TestNumericMetric:
    """C-09: la metrica numerica affianca `citation_precision`, non la sostituisce.

    Due strumenti con definizioni diverse — un'inferenza linguistica contro una
    ricerca in griglia — e denominatori diversi. Sotto un nome solo i due dataset
    smetterebbero di essere confrontabili.
    """

    def _report(self, numeric_outcomes: list[str]) -> CitationReport:
        verdicts = [
            PairVerdict(claim=f"c{i}", chunk_id="x", marker=1, supported=True,
                        score=0.9, n_premises=1, numeric=o)
            for i, o in enumerate(numeric_outcomes)
        ]
        return CitationReport(
            n_answers=1, n_claims=len(verdicts), n_verifiable=len(verdicts),
            n_uncited=0, n_pairs=len(verdicts), n_supported=len(verdicts),
            n_claims_supported=len(verdicts), n_windowed=0,
            n_numeric_judged=sum(1 for v in verdicts if v.numeric in ("supported", "unsupported")),
            n_numeric_supported=sum(1 for v in verdicts if v.numeric == "supported"),
            verdicts=verdicts,
        )

    def test_not_applicable_leaves_both_numerator_and_denominator(self):
        """Non e' un fallimento: e' lavoro che resta all'NLI. Contarlo come
        rifiuto sarebbe il difetto che C-09 corregge."""
        r = self._report(["supported", "unsupported", "not_applicable"])
        assert r.n_numeric_judged == 2
        assert r.numeric_citation_precision == pytest.approx(0.5)

    def test_coverage_reports_the_denominator(self):
        r = self._report(["supported", "not_applicable", "not_applicable", "not_applicable"])
        assert r.numeric_coverage == pytest.approx(0.25)

    def test_precision_is_zero_when_nothing_is_judged(self):
        r = self._report(["not_applicable", "not_applicable"])
        assert r.numeric_citation_precision == 0.0
        assert r.numeric_coverage == 0.0

    def test_nli_precision_is_untouched(self):
        """Il campo `supported` resta il verdetto dell'NLI: i numeri gia'
        riportati prima di C-09 devono restare confrontabili (§15)."""
        r = self._report(["unsupported"] * 3)
        assert r.citation_precision == 1.0        # tutti supported per l'NLI
        assert r.numeric_citation_precision == 0.0

    def test_both_keys_always_present(self):
        m = build_metrics(self._report(["not_applicable"]))
        assert "numeric_citation_precision" in m and "numeric_coverage" in m

    def test_verdict_records_the_numeric_outcome(self):
        """Serve per rileggere i disaccordi senza ricalcolare: e' cosi' che i
        67 casi numerico-si'/NLI-no sono stati letti."""
        chunks = [{"chunk_id": "c1", "text": "<table><tr><td>Ricavi</td><td>1234.5</td></tr></table>"}]
        _, verdicts = verify_answer(
            "The reported Ricavi for the period were 1234.5 million [1].", chunks,
            verifier=lambda text, claim: Verdict(supported=False, score=0.1, n_premises=1),
        )
        assert verdicts[0].numeric == "supported"
        assert verdicts[0].supported is False     # l'NLI dice altro, e resta registrato
