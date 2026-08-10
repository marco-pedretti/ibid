"""Tests for R-05: document-level aggregation (doc_id_from_chunk_id, aggregate_to_docs,
harness helpers _build_doc_qrels / _build_doc_run, and harness integration).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import ir_measures
import pytest

from src.retrieval.doc_aggregation import DocResult, aggregate_to_docs, doc_id_from_chunk_id


# ---------------------------------------------------------------------------
# doc_id_from_chunk_id
# ---------------------------------------------------------------------------

class TestDocIdFromChunkId:
    def test_standard_three_part(self):
        assert doc_id_from_chunk_id("open_ragbench:paper123:0") == "paper123"

    def test_ledger_format(self):
        assert doc_id_from_chunk_id("ledger:annual_report_2023:0042") == "annual_report_2023"

    def test_seq_with_multiple_colons_preserved(self):
        # doc_id is always the middle segment; seq may have colons
        cid = "ds:my_doc:seq:extra"
        assert doc_id_from_chunk_id(cid) == "my_doc"

    def test_no_colon_returns_chunk_id(self):
        assert doc_id_from_chunk_id("nodoc") == "nodoc"

    def test_two_parts_returns_second(self):
        assert doc_id_from_chunk_id("ds:doc") == "doc"


# ---------------------------------------------------------------------------
# aggregate_to_docs — max strategy (default)
# ---------------------------------------------------------------------------

class TestAggregateToDocsMax:
    def test_single_chunk_single_doc(self):
        results = aggregate_to_docs([("open_ragbench:doc1:0", 0.9)])
        assert len(results) == 1
        assert results[0].doc_id == "doc1"
        assert results[0].score == pytest.approx(0.9)
        assert results[0].top_chunk_id == "open_ragbench:doc1:0"
        assert results[0].chunk_count == 1

    def test_two_chunks_same_doc_keeps_max(self):
        chunks = [("open_ragbench:doc1:0", 0.9), ("open_ragbench:doc1:1", 0.7)]
        results = aggregate_to_docs(chunks)
        assert len(results) == 1
        assert results[0].score == pytest.approx(0.9)
        assert results[0].chunk_count == 2

    def test_two_chunks_same_doc_top_chunk_is_best(self):
        chunks = [("open_ragbench:doc1:0", 0.5), ("open_ragbench:doc1:1", 0.9)]
        results = aggregate_to_docs(chunks)
        assert results[0].top_chunk_id == "open_ragbench:doc1:1"

    def test_two_chunks_different_docs_sorted_by_score(self):
        chunks = [("ds:doc_a:0", 0.6), ("ds:doc_b:0", 0.9)]
        results = aggregate_to_docs(chunks)
        assert results[0].doc_id == "doc_b"
        assert results[1].doc_id == "doc_a"

    def test_chunk_count_per_doc(self):
        chunks = [
            ("ds:doc1:0", 0.9),
            ("ds:doc1:1", 0.8),
            ("ds:doc1:2", 0.7),
            ("ds:doc2:0", 0.6),
        ]
        results = aggregate_to_docs(chunks)
        by_id = {r.doc_id: r for r in results}
        assert by_id["doc1"].chunk_count == 3
        assert by_id["doc2"].chunk_count == 1

    def test_empty_input(self):
        assert aggregate_to_docs([]) == []

    def test_returns_list_of_doc_result(self):
        results = aggregate_to_docs([("ds:doc:0", 0.5)])
        assert all(isinstance(r, DocResult) for r in results)

    def test_sorted_descending(self):
        chunks = [("ds:a:0", 0.3), ("ds:b:0", 0.9), ("ds:c:0", 0.6)]
        scores = [r.score for r in aggregate_to_docs(chunks)]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# aggregate_to_docs — sum strategy
# ---------------------------------------------------------------------------

class TestAggregateToDocsSum:
    def test_sum_of_two_chunks(self):
        chunks = [("ds:doc1:0", 0.6), ("ds:doc1:1", 0.4)]
        results = aggregate_to_docs(chunks, strategy="sum")
        assert results[0].score == pytest.approx(1.0)

    def test_sum_beats_max_when_many_chunks(self):
        # doc_a: two 0.4 chunks → sum=0.8; doc_b: one 0.7 chunk
        chunks = [("ds:doc_a:0", 0.4), ("ds:doc_a:1", 0.4), ("ds:doc_b:0", 0.7)]
        results_sum = aggregate_to_docs(chunks, strategy="sum")
        assert results_sum[0].doc_id == "doc_a"

    def test_sum_sorted_descending(self):
        chunks = [("ds:a:0", 0.2), ("ds:b:0", 0.5), ("ds:b:1", 0.3)]
        scores = [r.score for r in aggregate_to_docs(chunks, strategy="sum")]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Harness helpers: _build_doc_qrels and _build_doc_run
# ---------------------------------------------------------------------------

class TestBuildDocQrels:
    def test_derives_doc_id_from_chunk_qrel(self):
        from src.eval.harness import _build_doc_qrels
        from src.datasets.golden import GoldenQuery, GoldenQrel

        q = GoldenQuery(
            query_id="q1",
            dataset_id="open_ragbench",
            query_text="What is X?",
            qrels=[GoldenQrel(chunk_id="open_ragbench:doc42:0", relevance=2)],
        )
        doc_qrels = _build_doc_qrels([q])
        assert len(doc_qrels) == 1
        assert doc_qrels[0].doc_id == "doc42"
        assert doc_qrels[0].relevance == 2

    def test_max_relevance_across_chunks_same_doc(self):
        from src.eval.harness import _build_doc_qrels
        from src.datasets.golden import GoldenQuery, GoldenQrel

        q = GoldenQuery(
            query_id="q1",
            dataset_id="ds",
            query_text="q",
            qrels=[
                GoldenQrel(chunk_id="ds:doc1:0", relevance=1),
                GoldenQrel(chunk_id="ds:doc1:1", relevance=2),
            ],
        )
        doc_qrels = _build_doc_qrels([q])
        assert len(doc_qrels) == 1
        assert doc_qrels[0].relevance == 2

    def test_multiple_queries(self):
        from src.eval.harness import _build_doc_qrels
        from src.datasets.golden import GoldenQuery, GoldenQrel

        queries = [
            GoldenQuery(query_id="q1", dataset_id="ds", query_text="a",
                        qrels=[GoldenQrel(chunk_id="ds:docA:0", relevance=2)]),
            GoldenQuery(query_id="q2", dataset_id="ds", query_text="b",
                        qrels=[GoldenQrel(chunk_id="ds:docB:0", relevance=2)]),
        ]
        doc_qrels = _build_doc_qrels(queries)
        query_ids = {qr.query_id for qr in doc_qrels}
        assert query_ids == {"q1", "q2"}

    def test_zero_relevance_excluded(self):
        from src.eval.harness import _build_doc_qrels
        from src.datasets.golden import GoldenQuery, GoldenQrel

        q = GoldenQuery(
            query_id="q1", dataset_id="ds", query_text="q",
            qrels=[GoldenQrel(chunk_id="ds:doc1:0", relevance=0)],
        )
        assert _build_doc_qrels([q]) == []


class TestBuildDocRun:
    def test_aggregates_chunks_from_same_doc(self):
        from src.eval.harness import _build_doc_run

        chunk_run = [
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:doc1:0", score=0.9),
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:doc1:1", score=0.7),
        ]
        doc_run = _build_doc_run(chunk_run)
        assert len(doc_run) == 1
        assert doc_run[0].doc_id == "doc1"

    def test_keeps_max_score(self):
        from src.eval.harness import _build_doc_run

        chunk_run = [
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:doc1:0", score=0.5),
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:doc1:1", score=0.9),
        ]
        doc_run = _build_doc_run(chunk_run)
        assert doc_run[0].score == pytest.approx(0.9)

    def test_preserves_separate_docs(self):
        from src.eval.harness import _build_doc_run

        chunk_run = [
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:docA:0", score=0.8),
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:docB:0", score=0.6),
        ]
        doc_run = _build_doc_run(chunk_run)
        assert len(doc_run) == 2

    def test_sorted_by_score_within_query(self):
        from src.eval.harness import _build_doc_run

        chunk_run = [
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:docA:0", score=0.3),
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:docB:0", score=0.9),
        ]
        doc_run = _build_doc_run(chunk_run)
        assert doc_run[0].doc_id == "docB"
        assert doc_run[1].doc_id == "docA"

    def test_multiple_queries_independent(self):
        from src.eval.harness import _build_doc_run

        chunk_run = [
            ir_measures.ScoredDoc(query_id="q1", doc_id="ds:doc1:0", score=0.9),
            ir_measures.ScoredDoc(query_id="q2", doc_id="ds:doc2:0", score=0.8),
        ]
        doc_run = _build_doc_run(chunk_run)
        query_ids = {sd.query_id for sd in doc_run}
        assert query_ids == {"q1", "q2"}

    def test_empty_input(self):
        from src.eval.harness import _build_doc_run
        assert _build_doc_run([]) == []


# ---------------------------------------------------------------------------
# Harness integration
# ---------------------------------------------------------------------------

def _write_golden(tmp_path: Path) -> Path:
    from src.datasets.golden import GoldenQrel, GoldenQuery

    q = GoldenQuery(
        query_id="q1",
        dataset_id="open_ragbench",
        query_text="What is X?",
        qrels=[GoldenQrel(chunk_id="open_ragbench:doc1:0", relevance=2)],
    )
    p = tmp_path / "golden.jsonl"
    p.write_text(q.model_dump_json() + "\n", encoding="utf-8")
    return p


def _fake_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id, "text": "chunk text"}
    hit.score = score
    return hit


class TestDocAggregateHarness:
    def _run(self, tmp_path: Path, doc_aggregate: bool, **kwargs):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.retrieval_backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.retrieval_backends.search_batch", return_value=[[hit]]):
            return run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                doc_aggregate=doc_aggregate,
                limit=1,
                **kwargs,
            )

    def test_doc_metrics_present_even_without_the_flag(self, tmp_path):
        """Since 2026-08-07 document metrics are unconditional.

        They are pure post-processing of the same run — no extra retrieval, no
        extra embedding. Gating them behind a flag left most runs without
        doc_R@5, the metric the routing claim (§0.2) rests on, so runs with and
        without the flag could not be compared.
        """
        run = self._run(tmp_path, doc_aggregate=False)
        assert "doc_R@5" in run.metrics
        assert "doc_R@10" in run.metrics

    def test_doc_aggregate_true_adds_doc_r5(self, tmp_path):
        run = self._run(tmp_path, doc_aggregate=True)
        assert "doc_R@5" in run.metrics

    def test_doc_aggregate_true_adds_doc_r10(self, tmp_path):
        run = self._run(tmp_path, doc_aggregate=True)
        assert "doc_R@10" in run.metrics

    def test_doc_metrics_are_floats(self, tmp_path):
        run = self._run(tmp_path, doc_aggregate=True)
        assert isinstance(run.metrics["doc_R@5"], float)
        assert isinstance(run.metrics["doc_R@10"], float)

    def test_config_hash_differs_with_doc_aggregate(self, tmp_path):
        run_plain = self._run(tmp_path, doc_aggregate=False)
        run_agg = self._run(tmp_path, doc_aggregate=True)
        assert run_plain.config_hash != run_agg.config_hash

    def test_relevant_doc_found_gives_recall_one(self, tmp_path):
        # The single hit chunk_id "open_ragbench:doc1:0" → doc_id "doc1",
        # which is the relevant doc in the golden query.
        run = self._run(tmp_path, doc_aggregate=True)
        assert run.metrics["doc_R@5"] == pytest.approx(1.0)

    def test_chunk_metrics_still_present(self, tmp_path):
        run = self._run(tmp_path, doc_aggregate=True)
        assert "nDCG@10" in run.metrics
        assert "R@5" in run.metrics
