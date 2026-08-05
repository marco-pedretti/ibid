"""Tests for E-03: IR metrics computation."""

from __future__ import annotations

import ir_measures

from src.datasets.golden import GoldenQrel, GoldenQuery
from src.eval.metrics import (
    DEFAULT_MEASURES,
    build_qrels,
    build_run,
    compute_metrics,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_query(qid: str, chunk_ids: list[str], relevances: list[int], answerable: bool = True) -> GoldenQuery:
    return GoldenQuery(
        query_id=qid,
        dataset_id="open_ragbench",
        query_text="Test query?",
        qrels=[GoldenQrel(chunk_id=c, relevance=r) for c, r in zip(chunk_ids, relevances)],
        answerable=answerable,
    )


# ---------------------------------------------------------------------------
# build_qrels
# ---------------------------------------------------------------------------

class TestBuildQrels:
    def test_basic(self):
        q = _make_query("q1", ["c1", "c2"], [2, 1])
        qrels = build_qrels([q])
        assert len(qrels) == 2

    def test_excludes_zero_relevance(self):
        q = _make_query("q1", ["c1", "c2"], [2, 0])
        qrels = build_qrels([q])
        assert len(qrels) == 1
        assert qrels[0].doc_id == "c1"

    def test_excludes_unanswerable_queries(self):
        q = _make_query("q1", ["c1"], [2], answerable=False)
        qrels = build_qrels([q])
        assert qrels == []

    def test_multiple_queries(self):
        qs = [
            _make_query("q1", ["c1"], [2]),
            _make_query("q2", ["c2", "c3"], [1, 2]),
        ]
        qrels = build_qrels(qs)
        assert len(qrels) == 3
        query_ids = {qr.query_id for qr in qrels}
        assert query_ids == {"q1", "q2"}

    def test_qrel_fields(self):
        q = _make_query("q1", ["chunk_abc"], [2])
        qrels = build_qrels([q])
        assert qrels[0].query_id == "q1"
        assert qrels[0].doc_id == "chunk_abc"
        assert qrels[0].relevance == 2

    def test_empty_input(self):
        assert build_qrels([]) == []


# ---------------------------------------------------------------------------
# build_run
# ---------------------------------------------------------------------------

class TestBuildRun:
    def test_basic(self):
        run = build_run("q1", ["c1", "c2", "c3"], [0.9, 0.8, 0.7])
        assert len(run) == 3

    def test_fields(self):
        run = build_run("q1", ["c1"], [0.95])
        assert run[0].query_id == "q1"
        assert run[0].doc_id == "c1"
        assert run[0].score == 0.95

    def test_empty(self):
        assert build_run("q1", [], []) == []

    def test_order_preserved(self):
        run = build_run("q1", ["a", "b", "c"], [0.9, 0.8, 0.7])
        assert [r.doc_id for r in run] == ["a", "b", "c"]
        assert [r.score for r in run] == [0.9, 0.8, 0.7]


# ---------------------------------------------------------------------------
# compute_metrics
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def _perfect_scenario(self):
        """One query, top result is the relevant chunk."""
        q = _make_query("q1", ["c1"], [2])
        qrels = build_qrels([q])
        run = build_run("q1", ["c1", "c2", "c3"], [0.9, 0.8, 0.7])
        return qrels, run

    def test_returns_dict(self):
        qrels, run = self._perfect_scenario()
        metrics = compute_metrics(qrels, run)
        assert isinstance(metrics, dict)

    def test_default_measure_keys_present(self):
        qrels, run = self._perfect_scenario()
        metrics = compute_metrics(qrels, run)
        keys = set(metrics.keys())
        assert any("R@5" in k or "Recall" in k for k in keys)
        assert any("nDCG" in k for k in keys)
        assert any("RR" in k for k in keys)  # ir_measures: MRR@10 -> "RR@10"
        assert any("Success" in k for k in keys)

    def test_all_values_float(self):
        qrels, run = self._perfect_scenario()
        metrics = compute_metrics(qrels, run)
        for v in metrics.values():
            assert isinstance(v, float)

    def test_perfect_retrieval_success1(self):
        qrels, run = self._perfect_scenario()
        metrics = compute_metrics(qrels, run)
        success_key = next(k for k in metrics if "Success" in k)
        assert metrics[success_key] == 1.0

    def test_miss_at_1_success0(self):
        """Relevant chunk is rank 2, not rank 1 -> success@1 = 0."""
        q = _make_query("q1", ["c1"], [2])
        qrels = build_qrels([q])
        run = build_run("q1", ["c2", "c1", "c3"], [0.9, 0.8, 0.7])
        metrics = compute_metrics(qrels, run)
        success_key = next(k for k in metrics if "Success" in k)
        assert metrics[success_key] == 0.0

    def test_recall5_perfect_when_in_top5(self):
        q = _make_query("q1", ["c3"], [2])
        qrels = build_qrels([q])
        run = build_run("q1", ["c1", "c2", "c3", "c4", "c5"], [0.9, 0.8, 0.7, 0.6, 0.5])
        metrics = compute_metrics(qrels, run)
        r5_key = next(k for k in metrics if "R@5" in k or ("Recall" in k and "@5" in k))
        assert metrics[r5_key] == 1.0

    def test_empty_run_returns_zeros(self):
        q = _make_query("q1", ["c1"], [2])
        qrels = build_qrels([q])
        metrics = compute_metrics(qrels, [])
        for v in metrics.values():
            assert v == 0.0

    def test_metrics_between_0_and_1(self):
        q = _make_query("q1", ["c1"], [2])
        qrels = build_qrels([q])
        run = build_run("q1", ["c2", "c3"], [0.9, 0.8])  # miss
        metrics = compute_metrics(qrels, run)
        for v in metrics.values():
            assert 0.0 <= v <= 1.0
