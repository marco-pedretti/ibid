"""Tests for src/generation/citation_format.py (C-01).

The acceptance criterion of C-01 is a number ("format §3.2 respected in ≥95% of
generations"), so what the checker counts *is* the criterion.  These tests pin
down the three decisions that number depends on:

  1. compliance is judged on raw output, not on parser output;
  2. abstentions leave the denominator instead of scoring either way;
  3. every violation kind is reported on every run, zeros included.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.citation_format import (
    COMPLIANCE_TARGET,
    VIOLATION_KINDS,
    FormatReport,
    check_format,
    find_violations,
    is_abstention,
    summarize,
    wilson_lower,
)


class TestCompliantForms:
    def test_canonical_example_from_roadmap(self):
        r = check_format("Il valore massimo è 400ms [2][3].", 5)
        assert r.compliant
        assert r.markers == [2, 3]

    def test_single_marker(self):
        assert check_format("The model outperforms the baseline [1].", 3).compliant

    def test_three_contiguous_markers(self):
        r = check_format("Tutti concordano [1][2][3].", 3)
        assert r.compliant and r.markers == [1, 2, 3]

    def test_several_sentences_each_cited(self):
        text = "A vale 1 [1]. B vale 2 [2][3]. C non è definito [3]."
        assert check_format(text, 3).compliant

    def test_marker_at_the_context_boundary(self):
        assert check_format("Vero [5].", 5).compliant

    def test_numbers_in_prose_are_not_markers(self):
        # "400ms", "2009", "0.85" must not be read as citations.
        r = check_format("Nel 2009 il valore era 400ms, ora 0.85 [1].", 2)
        assert r.compliant and r.markers == [1]


class TestViolations:
    def _kinds(self, text, n=5):
        return {v.kind for v in find_violations(text, n)}

    def test_comma_list(self):
        assert "comma_list" in self._kinds("Vero [2, 3].")

    def test_comma_list_without_space(self):
        assert "comma_list" in self._kinds("Vero [2,3].")

    def test_comma_list_of_three(self):
        assert "comma_list" in self._kinds("Vero [1,2,3].")

    def test_range(self):
        assert "range" in self._kinds("Vero [1-3].")

    def test_range_en_dash(self):
        assert "range" in self._kinds("Vero [1–3].")

    def test_conjunction_italian(self):
        assert "conjunction" in self._kinds("Vero [2 e 3].")

    def test_conjunction_english(self):
        assert "conjunction" in self._kinds("True [2 and 3].")

    def test_dash_joined(self):
        assert "dash_joined" in self._kinds("Vero [2]-[3].")

    def test_spaced_markers(self):
        # §3.2 says "contiguous"; a space between markers is not contiguous.
        assert "spaced_markers" in self._kinds("Vero [2] [3].")

    def test_named_marker_bracket(self):
        assert "named_marker" in self._kinds("Vero [Chunk 2].")

    def test_named_marker_parenthesis(self):
        assert "named_marker" in self._kinds("Vero (Source 2).")

    def test_named_marker_is_case_insensitive(self):
        assert "named_marker" in self._kinds("Vero [doc 2].")

    def test_out_of_range_above(self):
        assert "out_of_range" in self._kinds("Vero [9].", n=5)

    def test_out_of_range_one_below_the_floor(self):
        # [0] itself is excluded on purpose — see TestMathIsNotACitation.
        assert "out_of_range" in self._kinds("Vero [6].", n=5)

    def test_no_citation(self):
        assert "no_citation" in self._kinds("Il valore massimo è 400ms.")

    def test_one_violation_per_occurrence(self):
        vs = find_violations("Vero [1,2]. Anche [3,4].", 5)
        assert sum(1 for v in vs if v.kind == "comma_list") == 2

    def test_snippet_records_what_was_seen(self):
        vs = find_violations("Vero [2, 3].", 5)
        assert any(v.snippet == "[2, 3]" for v in vs)

    def test_several_kinds_at_once(self):
        kinds = self._kinds("A [1,2] e B [3]-[4].")
        assert {"comma_list", "dash_joined"} <= kinds

    def test_valid_markers_alongside_a_violation_still_fail(self):
        r = check_format("A [1]. B [2,3].", 5)
        assert not r.compliant

    def test_paragraph_without_markers_is_not_excused(self):
        # A long answer that never cites is a format failure, not an abstention.
        text = "Il documento discute vari aspetti del problema. " * 10
        assert not check_format(text, 5).compliant


class TestAbstention:
    def test_prompt_phrase_is_an_abstention(self):
        assert is_abstention("Insufficient information.")

    def test_italian_phrase(self):
        assert is_abstention("Non ho informazioni sufficienti.")

    def test_answer_with_markers_is_never_an_abstention(self):
        # "insufficient information" inside a cited answer is prose.
        assert not is_abstention("The paper gives insufficient information [2].")

    def test_long_prose_containing_a_phrase_is_not_an_abstention(self):
        text = ("Il documento non ho informazioni sufficienti su questo punto, "
                "ma discute in dettaglio molti altri aspetti del problema. " * 4)
        assert not is_abstention(text)

    def test_abstention_report_is_neither_compliant_nor_violating(self):
        r = check_format("Insufficient information.", 5)
        assert r.abstained
        assert not r.compliant
        assert r.violations == []

    def test_plain_uncited_answer_is_not_an_abstention(self):
        r = check_format("Il valore è 400ms.", 5)
        assert not r.abstained
        assert "no_citation" in r.kinds


class TestSummarize:
    @staticmethod
    def _reports(n_ok, n_bad, n_abstained):
        out = [check_format("Vero [1].", 5) for _ in range(n_ok)]
        out += [check_format("Vero [1,2].", 5) for _ in range(n_bad)]
        out += [check_format("Insufficient information.", 5) for _ in range(n_abstained)]
        return out

    def test_rate_is_over_scored_answers_only(self):
        s = summarize(self._reports(n_ok=9, n_bad=1, n_abstained=10))
        assert s.n_total == 20
        assert s.n_scored == 10
        assert s.n_abstained == 10
        assert s.rate == 0.9

    def test_abstentions_do_not_raise_the_rate(self):
        # The trap this guards: counting abstentions as compliant would let a
        # model that abstains on everything report perfect format compliance.
        a = summarize(self._reports(n_ok=9, n_bad=1, n_abstained=0)).rate
        b = summarize(self._reports(n_ok=9, n_bad=1, n_abstained=90)).rate
        assert a == b == 0.9

    def test_all_kinds_present_even_at_zero(self):
        s = summarize(self._reports(n_ok=5, n_bad=0, n_abstained=0))
        assert set(s.kind_rates) == set(VIOLATION_KINDS)
        assert all(v == 0.0 for v in s.kind_rates.values())

    def test_kind_rate_counts_answers_not_occurrences(self):
        # One answer with two comma lists is one non-compliant answer.
        reports = [check_format("A [1,2]. B [3,4].", 5)]
        s = summarize(reports)
        assert s.kind_rates["comma_list"] == 1.0

    def test_markers_per_answer(self):
        reports = [check_format("Vero [1][2].", 5), check_format("Vero [1].", 5)]
        assert summarize(reports).markers_per_answer == 1.5

    def test_empty_input_does_not_divide_by_zero(self):
        s = summarize([])
        assert s.rate == 0.0 and s.n_scored == 0 and s.markers_per_answer == 0.0

    def test_all_abstained_gives_zero_rate_not_one(self):
        s = summarize(self._reports(n_ok=0, n_bad=0, n_abstained=5))
        assert s.n_scored == 0 and s.rate == 0.0


class TestMeasuredBeforeRepair:
    """C-01 measures the prompt; C-02 measures the parser.  Keep them apart."""

    def test_normalized_output_would_score_differently(self):
        from src.generation.citations import normalize

        raw = "Il valore massimo è 400ms [2, 3]."
        assert not check_format(raw, 5).compliant
        # The parser can repair it — which is C-02's result, not C-01's.
        assert check_format(normalize(raw), 5).compliant

    def test_report_has_no_repair_path(self):
        # A FormatReport carries the verdict and the evidence, never a fixed
        # string: nothing downstream can mistake it for repaired output.
        assert not hasattr(FormatReport(compliant=True, abstained=False), "repaired")


class TestWilsonLower:
    """The interval is what turns a sample rate into a claim about the model."""

    def test_perfect_small_sample_does_not_reach_the_target(self):
        # 10/10 is 100%, but ten answers cannot support ">= 95%".
        assert wilson_lower(10, 10) < COMPLIANCE_TARGET

    def test_perfect_large_sample_does(self):
        assert wilson_lower(200, 200) >= COMPLIANCE_TARGET

    def test_bound_is_below_the_point_estimate(self):
        assert wilson_lower(95, 100) < 0.95

    def test_bound_never_negative(self):
        assert wilson_lower(0, 5) == 0.0

    def test_empty_sample(self):
        assert wilson_lower(0, 0) == 0.0

    def test_tightens_as_n_grows(self):
        assert wilson_lower(98, 100) < wilson_lower(980, 1000)

    def test_summary_exposes_the_bound(self):
        reports = [check_format("Vero [1].", 5) for _ in range(50)]
        s = summarize(reports)
        assert s.rate == 1.0 and 0.0 < s.rate_lower95 < 1.0

    def test_meets_target_uses_the_observed_rate(self):
        """ROADMAP §8 asks for the rate, not for a bound on it.

        Precedent in the repo: I-02 was accepted at 45/50 = 90.0% against a
        ≥90% criterion, on 50 documents, with no interval.
        """
        s = summarize([check_format("Vero [1].", 5) for _ in range(20)])
        assert s.rate == 1.0
        assert s.rate_lower95 < COMPLIANCE_TARGET   # the bound would fail it
        assert s.meets_target                       # the criterion does not

    def test_below_target_fails(self):
        reports = ([check_format("Vero [1].", 5) for _ in range(9)]
                   + [check_format("Vero [1,2].", 5)])
        assert summarize(reports).rate == 0.9
        assert not summarize(reports).meets_target


class TestMathIsNotACitation:
    """§3.2 numbers chunks from 1, so a construct containing 0 is something else.

    Found in the C-01 run: an interval `[0,1]` in a LaTeX expression scored as a
    malformed comma list while the same sentence cited `[1]` correctly.
    """

    def test_interval_zero_one_is_not_a_comma_list(self):
        text = r"functions within each box $\Psi_{r} \subseteq[0,1]^{p}$ [1]."
        assert check_format(text, 5).compliant

    def test_bare_zero_marker_is_not_out_of_range(self):
        assert "out_of_range" not in check_format("Il dominio è [0] per costruzione [1].", 5).kinds

    def test_zero_range_is_not_a_range_violation(self):
        assert check_format(r"su $[0-1]$ vale la stima [1].", 5).compliant

    def test_a_real_malformed_list_is_still_caught(self):
        # The rule must not excuse [16,17,18,19]: no zero, and the numbers point
        # at chunks that do not exist.
        r = check_format("Vero [16,17,18,19].", 5)
        assert not r.compliant
        assert "comma_list" in r.kinds

    def test_valid_comma_list_still_violates(self):
        assert "comma_list" in check_format("Vero [1,2].", 5).kinds
