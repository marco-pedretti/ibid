"""Tests for dashboard/failure_store.py — batch retrieval ranked worst-first.

The behaviour that matters here is the chunk-vs-document distinction: a routed
collection produces chunk_ids the qrels never mention, so chunk recall is
structurally 0.  Reading that as "retrieval is broken" is exactly the mistake
this module exists to prevent.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dashboard.failure_store import (
    QueryOutcome,
    chunk_id_mismatch,
    evaluate_queries,
    failure_summary,
    score_outcome,
    sort_by_failure,
)
from dashboard.retrieval_probe import ProbeConfig
from src.datasets.golden import GoldenQrel, GoldenQuery


def _query(qid: str = "q1", chunk_ids: tuple[str, ...] = ("ds:doc1:0",),
           dataset: str = "open_ragbench") -> GoldenQuery:
    return GoldenQuery(
        query_id=qid,
        dataset_id=dataset,
        query_text=f"question {qid}",
        qrels=[GoldenQrel(chunk_id=c, relevance=2) for c in chunk_ids],
    )


def _outcome(retrieved: list[str], golden: tuple[str, ...] = ("ds:doc1:0",),
             qid: str = "q1") -> QueryOutcome:
    return score_outcome(
        QueryOutcome(
            query=_query(qid, golden),
            retrieved_ids=retrieved,
            scores=[0.9] * len(retrieved),
            payloads=[{"chunk_id": c} for c in retrieved],
        )
    )


def _point(chunk_id: str, score: float = 0.9) -> MagicMock:
    p = MagicMock()
    p.payload = {"chunk_id": chunk_id, "text": "t"}
    p.score = score
    return p


# ---------------------------------------------------------------------------
# score_outcome — two granularities that can disagree
# ---------------------------------------------------------------------------

class TestScoreOutcome:
    def test_exact_hit_is_full_recall(self):
        o = _outcome(["ds:doc1:0"])
        assert o.recall == 1.0 and o.doc_recall == 1.0

    def test_miss_is_zero(self):
        o = _outcome(["ds:doc9:0"])
        assert o.recall == 0.0 and o.doc_recall == 0.0

    def test_wrong_chunk_right_document(self):
        """Chunk recall 0, doc recall 1 — a file-list success, a context failure."""
        o = _outcome(["ds:doc1:7"])
        assert o.recall == 0.0
        assert o.doc_recall == 1.0

    def test_routed_id_scheme_still_matches_document(self):
        o = _outcome(["ds:doc1:0042"], golden=("ds:doc1:3",))
        assert o.recall == 0.0
        assert o.doc_recall == 1.0

    def test_partial_recall_with_multiple_qrels(self):
        o = _outcome(["ds:doc1:0"], golden=("ds:doc1:0", "ds:doc2:0"))
        assert o.recall == 0.5

    def test_no_qrels_is_zero_not_crash(self):
        o = score_outcome(QueryOutcome(query=_query(chunk_ids=()), retrieved_ids=["x"]))
        assert o.recall == 0.0

    def test_empty_retrieval(self):
        assert _outcome([]).recall == 0.0

    def test_is_failure_follows_doc_recall(self):
        assert _outcome(["ds:doc9:0"]).is_failure is True
        assert _outcome(["ds:doc1:7"]).is_failure is False

    def test_top_score_of_empty_is_zero(self):
        assert _outcome([]).top_score == 0.0

    def test_golden_docs_derived_from_chunk_ids(self):
        assert _outcome([], golden=("ds:doc1:0", "ds:doc2:5")).golden_docs == {"doc1", "doc2"}


# ---------------------------------------------------------------------------
# sort_by_failure
# ---------------------------------------------------------------------------

class TestSortByFailure:
    def test_worst_first(self):
        good = _outcome(["ds:doc1:0"], qid="good")
        bad = _outcome(["ds:doc9:0"], qid="bad")
        assert sort_by_failure([good, bad])[0].query.query_id == "bad"

    def test_doc_recall_dominates_chunk_recall(self):
        partial_doc = _outcome(["ds:doc1:7"], qid="doc_ok")     # doc 1.0, chunk 0.0
        total_miss = _outcome(["ds:doc9:0"], qid="miss")        # doc 0.0, chunk 0.0
        assert sort_by_failure([partial_doc, total_miss])[0].query.query_id == "miss"

    def test_chunk_recall_breaks_ties(self):
        a = _outcome(["ds:doc1:7"], qid="a")                     # doc 1, chunk 0
        b = _outcome(["ds:doc1:0"], qid="b")                     # doc 1, chunk 1
        assert sort_by_failure([a, b])[0].query.query_id == "a"

    def test_empty_list(self):
        assert sort_by_failure([]) == []

    def test_does_not_mutate_input(self):
        items = [_outcome(["ds:doc1:0"], qid="a"), _outcome(["ds:doc9:0"], qid="b")]
        sort_by_failure(items)
        assert [o.query.query_id for o in items] == ["a", "b"]


# ---------------------------------------------------------------------------
# failure_summary
# ---------------------------------------------------------------------------

class TestFailureSummary:
    def test_empty_is_all_zero(self):
        s = failure_summary([])
        assert s["n"] == 0 and s["failure_rate"] == 0.0

    def test_counts_failures(self):
        s = failure_summary([_outcome(["ds:doc1:0"]), _outcome(["ds:doc9:0"])])
        assert s["n"] == 2 and s["n_failures"] == 1
        assert s["failure_rate"] == 0.5

    def test_mean_recalls(self):
        s = failure_summary([_outcome(["ds:doc1:0"]), _outcome(["ds:doc9:0"])])
        assert s["mean_recall"] == 0.5
        assert s["mean_doc_recall"] == 0.5

    def test_all_success(self):
        s = failure_summary([_outcome(["ds:doc1:0"])])
        assert s["failure_rate"] == 0.0

    def test_all_failure(self):
        s = failure_summary([_outcome(["ds:doc9:0"])])
        assert s["failure_rate"] == 1.0


# ---------------------------------------------------------------------------
# chunk_id_mismatch — the R-07 diagnostic
# ---------------------------------------------------------------------------

class TestChunkIdMismatch:
    def test_detects_routed_collection(self):
        outcomes = [_outcome(["ds:doc1:0042"], golden=("ds:doc1:3",), qid=f"q{i}")
                    for i in range(3)]
        assert chunk_id_mismatch(outcomes) is True

    def test_normal_collection_is_not_flagged(self):
        outcomes = [_outcome(["ds:doc1:0"], qid=f"q{i}") for i in range(3)]
        assert chunk_id_mismatch(outcomes) is False

    def test_genuine_total_failure_is_not_flagged(self):
        """Everything wrong at both levels is a real failure, not an id mismatch."""
        outcomes = [_outcome(["ds:doc9:0"], qid=f"q{i}") for i in range(3)]
        assert chunk_id_mismatch(outcomes) is False

    def test_one_chunk_hit_disproves_mismatch(self):
        outcomes = [_outcome(["ds:doc1:0042"], golden=("ds:doc1:3",), qid="a"),
                    _outcome(["ds:doc1:0"], qid="b")]
        assert chunk_id_mismatch(outcomes) is False

    def test_empty_is_false(self):
        assert chunk_id_mismatch([]) is False


# ---------------------------------------------------------------------------
# evaluate_queries — batching and mode routing
# ---------------------------------------------------------------------------

class TestEvaluateQueries:
    def _run(self, config, queries, hits_per_query=None, rerank_out=None):
        hits = hits_per_query if hits_per_query is not None else [
            [_point("ds:doc1:0"), _point("ds:doc2:0")] for _ in queries
        ]
        with patch("dashboard.failure_store.encode", return_value=[[0.1] * 1024] * len(queries)), \
             patch("dashboard.failure_store.encode_sparse",
                   return_value=[MagicMock()] * len(queries)), \
             patch("dashboard.failure_store.search_batch", return_value=hits) as mock_sb, \
             patch("dashboard.failure_store.cross_encode",
                   return_value=rerank_out if rerank_out is not None else []):
            out = evaluate_queries(MagicMock(), queries, config)
        return out, mock_sb

    def test_empty_queries_short_circuits(self):
        assert evaluate_queries(MagicMock(), [], ProbeConfig("ledger")) == []

    def test_one_outcome_per_query(self):
        queries = [_query(f"q{i}") for i in range(3)]
        out, _ = self._run(ProbeConfig("ledger", "dense"), queries)
        assert len(out) == 3

    def test_single_batched_search_not_one_per_query(self):
        """Per-query round trips make the page unusable on DirectML."""
        queries = [_query(f"q{i}") for i in range(20)]
        _, mock_sb = self._run(ProbeConfig("ledger", "dense"), queries)
        assert mock_sb.call_count == 1

    def test_queries_the_named_collection(self):
        _, mock_sb = self._run(ProbeConfig("ledger_routed", "dense"), [_query()])
        assert mock_sb.call_args[0][1] == "ledger_routed"

    def test_sparse_mode_routed(self):
        _, mock_sb = self._run(ProbeConfig("ledger", "sparse"), [_query()])
        assert mock_sb.call_args.kwargs["using"] == "sparse"

    def test_hybrid_hits_both_indexes(self):
        _, mock_sb = self._run(ProbeConfig("ledger", "hybrid"), [_query()])
        usings = [c.kwargs["using"] for c in mock_sb.call_args_list]
        assert set(usings) == {"dense", "sparse"}

    def test_truncates_to_top_k(self):
        hits = [[_point(f"ds:doc1:{i}") for i in range(10)]]
        out, _ = self._run(ProbeConfig("ledger", "dense", top_k=3), [_query()], hits)
        assert len(out[0].retrieved_ids) == 3

    def test_recall_computed(self):
        out, _ = self._run(ProbeConfig("ledger", "dense"), [_query()])
        assert out[0].recall == 1.0

    def test_progress_callback_fires_per_query(self):
        seen = []
        queries = [_query(f"q{i}") for i in range(3)]
        with patch("dashboard.failure_store.encode", return_value=[[0.1] * 1024] * 3), \
             patch("dashboard.failure_store.search_batch",
                   return_value=[[_point("ds:doc1:0")]] * 3):
            evaluate_queries(MagicMock(), queries, ProbeConfig("ledger"),
                             on_progress=lambda i, n: seen.append((i, n)))
        assert seen == [(1, 3), (2, 3), (3, 3)]

    def test_rerank_replaces_ranking(self):
        out, _ = self._run(
            ProbeConfig("ledger", "dense", rerank=True, top_k=1), [_query()],
            rerank_out=[_point("ds:doc5:0", 9.0)],
        )
        assert out[0].retrieved_ids == ["ds:doc5:0"]
