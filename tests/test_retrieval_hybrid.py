"""Tests for R-01: hybrid RRF retrieval (rrf_fuse + hybrid_search + harness integration).

rrf_fuse is pure Python — no Qdrant required.
hybrid_search and harness integration use mocks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.retrieval.hybrid import HybridResult, hybrid_search, rrf_fuse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id, "text": f"content of {chunk_id}"}
    hit.score = score
    return hit


def _fake_sparse_vec():
    from qdrant_client.models import SparseVector
    return SparseVector(indices=[0, 1], values=[0.8, 0.2])


# ---------------------------------------------------------------------------
# TestRrfFuse — pure unit tests, no I/O
# ---------------------------------------------------------------------------

class TestRrfFuse:
    def test_single_list_order_preserved(self):
        ids = ["a", "b", "c"]
        result = rrf_fuse([ids], k=60, top_n=3)
        assert [r[0] for r in result] == ["a", "b", "c"]

    def test_mutual_item_scores_higher(self):
        # "a" appears at rank 1 in both lists; "b" only in first, "c" only in second
        result = rrf_fuse([["a", "b"], ["a", "c"]], k=60)
        scores = {cid: s for cid, s in result}
        assert scores["a"] > scores["b"]
        assert scores["a"] > scores["c"]

    def test_top_n_respected(self):
        ids = ["a", "b", "c", "d", "e"]
        result = rrf_fuse([ids], top_n=3)
        assert len(result) == 3

    def test_empty_lists_returns_empty(self):
        assert rrf_fuse([[], []]) == []

    def test_scores_are_positive(self):
        result = rrf_fuse([["a", "b", "c"]], k=60)
        assert all(score > 0 for _, score in result)

    def test_higher_rank_higher_score(self):
        result = rrf_fuse([["a", "b"]], k=60)
        scores = {cid: s for cid, s in result}
        assert scores["a"] > scores["b"]

    def test_k_parameter_affects_scores(self):
        r1 = rrf_fuse([["a"]], k=1)
        r2 = rrf_fuse([["a"]], k=60)
        assert r1[0][1] != r2[0][1]

    def test_disjoint_lists_contain_union(self):
        result = rrf_fuse([["a", "b"], ["c", "d"]])
        ids = {cid for cid, _ in result}
        assert ids == {"a", "b", "c", "d"}

    def test_no_top_n_returns_all(self):
        ids = ["a", "b", "c", "d"]
        result = rrf_fuse([ids])
        assert len(result) == 4

    def test_two_lists_same_item_double_score(self):
        # With k=0 would be 1/rank. With same k, item in both lists should
        # have exactly double the score of an item in only one list at same rank.
        result = rrf_fuse([["a"], ["a"]], k=60)
        result_single = rrf_fuse([["a"]], k=60)
        assert result[0][1] == pytest.approx(result_single[0][1] * 2)


# ---------------------------------------------------------------------------
# TestHybridSearch — mocked Qdrant
# ---------------------------------------------------------------------------

class TestHybridSearch:
    def test_returns_top_k_results(self):
        client = MagicMock()
        dense_hits = [_fake_hit(f"doc:{i}", score=1.0 - i * 0.1) for i in range(5)]
        sparse_hits = [_fake_hit(f"doc:{i}", score=1.0 - i * 0.1) for i in range(5)]

        with patch("src.retrieval.hybrid.search", side_effect=[dense_hits, sparse_hits]):
            results = hybrid_search(client, "col", [0.1] * 4, _fake_sparse_vec(), top_k=3)

        assert len(results) == 3

    def test_rrf_promotes_shared_chunk(self):
        # "shared" appears at rank 1 in both lists — should be top result
        dense_hits = [_fake_hit("shared", 0.9), _fake_hit("dense_only", 0.8)]
        sparse_hits = [_fake_hit("shared", 0.7), _fake_hit("sparse_only", 0.6)]

        with patch("src.retrieval.hybrid.search", side_effect=[dense_hits, sparse_hits]):
            results = hybrid_search(
                MagicMock(), "col", [0.1] * 4, _fake_sparse_vec(), top_k=3
            )

        assert results[0].payload["chunk_id"] == "shared"

    def test_payload_preserved(self):
        hit = _fake_hit("doc:1", score=0.9)
        hit.payload["text"] = "hello world"

        with patch("src.retrieval.hybrid.search", side_effect=[[hit], [hit]]):
            results = hybrid_search(
                MagicMock(), "col", [0.1] * 4, _fake_sparse_vec(), top_k=1
            )

        assert results[0].payload["text"] == "hello world"

    def test_returns_hybrid_result_instances(self):
        hit = _fake_hit("doc:1")
        with patch("src.retrieval.hybrid.search", side_effect=[[hit], []]):
            results = hybrid_search(
                MagicMock(), "col", [0.1] * 4, _fake_sparse_vec(), top_k=1
            )
        assert all(isinstance(r, HybridResult) for r in results)

    def test_fetch_k_clamped_to_top_k(self):
        # fetch_k=2 but top_k=5 → must fetch at least 5 from each index
        hit = _fake_hit("doc:0")
        with patch("src.retrieval.hybrid.search", return_value=[hit]) as mock_search:
            hybrid_search(
                MagicMock(), "col", [0.1] * 4, _fake_sparse_vec(),
                top_k=5, fetch_k=2,
            )
        # Both calls should request at least top_k=5 candidates
        for c in mock_search.call_args_list:
            assert c.kwargs.get("top_k", c.args[3] if len(c.args) > 3 else 5) >= 5


# ---------------------------------------------------------------------------
# TestHybridHarness — harness integration with mocked dependencies
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


def _make_batch_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id}
    hit.score = score
    return hit


class TestHybridHarness:
    def _run_hybrid(self, tmp_path):
        from src.eval.harness import run_retrieval_eval
        from qdrant_client.models import SparseVector

        path = _write_golden(tmp_path)
        dense_vec = [0.1] * 1024
        sparse_vec = SparseVector(indices=[0], values=[1.0])
        # search_batch returns list[list[hit]]: one inner list per query
        batch_hit = _make_batch_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[dense_vec]), \
             patch("src.retrieval.backends.encode_sparse_query", return_value=[sparse_vec]), \
             patch("src.retrieval.backends.search_batch", return_value=[[batch_hit]]) as mock_batch:
            run = run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="hybrid",
                pipeline_mode="hybrid_rrf",
                limit=1,
            )
        return run, mock_batch

    def test_hybrid_returns_evalrun(self, tmp_path):
        from src.datasets.schema import EvalRun
        run, _ = self._run_hybrid(tmp_path)
        assert isinstance(run, EvalRun)

    def test_hybrid_calls_both_encode_functions(self, tmp_path):
        from src.eval.harness import run_retrieval_eval
        from qdrant_client.models import SparseVector

        path = _write_golden(tmp_path)
        dense_vec = [0.1] * 1024
        sparse_vec = SparseVector(indices=[0], values=[1.0])
        batch_hit = _make_batch_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[dense_vec]) as mock_enc, \
             patch("src.retrieval.backends.encode_sparse_query", return_value=[sparse_vec]) as mock_sparse, \
             patch("src.retrieval.backends.search_batch", return_value=[[batch_hit]]):
            run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="hybrid",
                limit=1,
            )

        mock_enc.assert_called_once()
        mock_sparse.assert_called_once()

    def test_hybrid_calls_search_batch_twice(self, tmp_path):
        # One search_batch call for dense, one for sparse
        from src.eval.harness import run_retrieval_eval
        from qdrant_client.models import SparseVector

        path = _write_golden(tmp_path)
        sparse_vec = SparseVector(indices=[0], values=[1.0])
        batch_hit = _make_batch_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.encode_sparse_query", return_value=[sparse_vec]), \
             patch("src.retrieval.backends.search_batch", return_value=[[batch_hit]]) as mock_batch:
            run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="hybrid",
                limit=1,
            )

        assert mock_batch.call_count == 2
        usings = [c.kwargs.get("using") for c in mock_batch.call_args_list]
        assert set(usings) == {"dense", "sparse"}

    def test_hybrid_pipeline_mode(self, tmp_path):
        run, _ = self._run_hybrid(tmp_path)
        assert run.pipeline_mode == "hybrid_rrf"

    def test_hybrid_config_hash_differs_from_dense(self, tmp_path):
        from src.eval.harness import run_retrieval_eval
        from qdrant_client.models import SparseVector

        path = _write_golden(tmp_path)
        sparse_vec = SparseVector(indices=[0], values=[1.0])
        batch_hit = _make_batch_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.encode_sparse_query", return_value=[sparse_vec]), \
             patch("src.retrieval.backends.search_batch", return_value=[[batch_hit]]):
            run_hybrid = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="hybrid",
                pipeline_mode="hybrid_rrf", limit=1,
            )

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[]]):
            run_dense = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense",
                pipeline_mode="generic", limit=1,
            )

        assert run_hybrid.config_hash != run_dense.config_hash
