"""Tests for src/eval/paired.py — McNemar's exact test.

The numbers here are checked against values that can be derived by hand, so a
future edit to the tail computation fails loudly instead of shifting a p-value
that nobody re-derives.
"""

from __future__ import annotations

import pytest

from src.eval.paired import compare_paired, mcnemar_exact


class TestMcNemarExact:
    def test_no_discordant_pairs_is_p_one(self):
        assert mcnemar_exact(0, 0) == 1.0

    def test_symmetric_split_is_p_one(self):
        """5 vs 5 is exactly what the null predicts."""
        assert mcnemar_exact(5, 5) == 1.0

    def test_is_symmetric_in_its_arguments(self):
        assert mcnemar_exact(12, 1) == mcnemar_exact(1, 12)

    def test_single_discordant_pair_cannot_be_significant(self):
        """One flip is a coin toss: p = 1.0, never evidence."""
        assert mcnemar_exact(1, 0) == 1.0

    def test_r07_open_ragbench_case(self):
        """6 vs 1: two-sided tail = 2*(C(7,0)+C(7,1))/2^7 = 2*8/128 = 0.125."""
        assert mcnemar_exact(1, 6) == pytest.approx(0.125)

    def test_r07_ledger_case(self):
        """12 vs 1: 2*(C(13,0)+C(13,1))/2^13 = 2*14/8192."""
        assert mcnemar_exact(12, 1) == pytest.approx(2 * 14 / 8192)

    def test_ledger_case_is_significant(self):
        assert mcnemar_exact(12, 1) < 0.05

    def test_open_ragbench_case_is_not_significant(self):
        assert mcnemar_exact(1, 6) > 0.05

    def test_all_one_way_is_strongly_significant(self):
        assert mcnemar_exact(10, 0) == pytest.approx(2 / 1024)

    def test_p_never_exceeds_one(self):
        for a in range(6):
            for b in range(6):
                assert mcnemar_exact(a, b) <= 1.0

    def test_more_evidence_lowers_p(self):
        assert mcnemar_exact(20, 0) < mcnemar_exact(10, 0)


class TestComparePaired:
    def test_identical_systems(self):
        r = compare_paired([True, False, True], [True, False, True])
        assert r.discordant == 0
        assert r.delta == 0.0
        assert "identici" in r.verdict()

    def test_b_strictly_better(self):
        r = compare_paired([False] * 10, [True] * 10)
        assert r.only_b == 10 and r.only_a == 0
        assert r.delta == 1.0
        assert "vince B" in r.verdict()

    def test_a_strictly_better(self):
        r = compare_paired([True] * 10, [False] * 10)
        assert "vince A" in r.verdict()

    def test_concordant_queries_carry_no_information(self):
        """Adding queries both systems get right must not change the p-value."""
        few = compare_paired([True, False], [False, True])
        many = compare_paired([True, False] + [True] * 50, [False, True] + [True] * 50)
        assert few.p_value == many.p_value

    def test_rates_reflect_all_queries_not_just_discordant(self):
        r = compare_paired([True, True, False], [True, False, False])
        assert r.rate_a == pytest.approx(2 / 3)
        assert r.rate_b == pytest.approx(1 / 3)

    def test_small_delta_can_be_insignificant(self):
        hits_a = [True] * 100
        hits_b = [True] * 100
        hits_a[0] = False  # one flip each way
        hits_b[1] = False
        r = compare_paired(hits_a, hits_b)
        assert r.p_value > 0.05

    def test_empty_input(self):
        r = compare_paired([], [])
        assert r.n == 0 and r.p_value == 1.0

    def test_mismatched_lengths_rejected(self):
        """Unpaired queries make the whole comparison meaningless — fail loudly."""
        with pytest.raises(ValueError, match="non appaiate"):
            compare_paired([True, False], [True])

    def test_delta_sign_follows_b_minus_a(self):
        r = compare_paired([True, True], [False, False])
        assert r.delta < 0

    def test_verdict_reports_discordant_count_when_inconclusive(self):
        r = compare_paired([True, False], [False, True])
        assert "discordanti" in r.verdict()
