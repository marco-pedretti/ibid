"""Tests for R-02: cross-encoder reranker (rerank() + harness integration).

The fastembed TextCrossEncoder is mocked throughout — no model download required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.retrieval.reranker import RankedResult, rerank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload(chunk_id: str, text: str = "dummy text") -> dict:
    return {"chunk_id": chunk_id, "text": text}


def _mock_reranker(scores: list[float]) -> MagicMock:
    """Return a mock TextCrossEncoder whose rerank() yields the given scores."""
    mock = MagicMock()
    mock.rerank.return_value = iter(scores)
    return mock


# ---------------------------------------------------------------------------
# TestRerank — pure unit tests, no I/O
# ---------------------------------------------------------------------------

class TestRerank:
    def test_empty_candidates_returns_empty(self):
        with patch("src.retrieval.reranker._get_reranker"):
            result = rerank("query", [], "any-model")
        assert result == []

    def test_returns_ranked_result_instances(self):
        candidates = [_payload("doc:0"), _payload("doc:1")]
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.9, 0.3])):
            results = rerank("query", candidates, "any-model")
        assert all(isinstance(r, RankedResult) for r in results)

    def test_sorted_descending_by_score(self):
        candidates = [_payload("a"), _payload("b"), _payload("c")]
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.3, 0.9, 0.6])):
            results = rerank("query", candidates, "any-model")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_highest_score_is_first(self):
        candidates = [_payload("low"), _payload("high")]
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.1, 0.9])):
            results = rerank("query", candidates, "any-model")
        assert results[0].payload["chunk_id"] == "high"

    def test_top_n_respected(self):
        candidates = [_payload(f"doc:{i}") for i in range(5)]
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.5, 0.4, 0.3, 0.2, 0.1])):
            results = rerank("query", candidates, "any-model", top_n=3)
        assert len(results) == 3

    def test_no_top_n_returns_all(self):
        candidates = [_payload(f"doc:{i}") for i in range(4)]
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.4, 0.3, 0.2, 0.1])):
            results = rerank("query", candidates, "any-model")
        assert len(results) == 4

    def test_score_preserved_from_model(self):
        candidates = [_payload("doc:0")]
        expected_score = 0.87654
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([expected_score])):
            results = rerank("query", candidates, "any-model")
        assert results[0].score == pytest.approx(expected_score)

    def test_payload_preserved(self):
        p = {"chunk_id": "x:1", "text": "hello world", "doc_id": "x", "page": 0}
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.5])):
            results = rerank("query", [p], "any-model")
        assert results[0].payload == p

    def test_model_called_with_query_and_texts(self):
        candidates = [_payload("a", "text A"), _payload("b", "text B")]
        mock_enc = _mock_reranker([0.9, 0.1])
        with patch("src.retrieval.reranker._get_reranker", return_value=mock_enc):
            rerank("my query", candidates, "any-model")
        mock_enc.rerank.assert_called_once_with(query="my query", documents=["text A", "text B"])

    def test_single_candidate(self):
        with patch("src.retrieval.reranker._get_reranker",
                   return_value=_mock_reranker([0.77])):
            results = rerank("q", [_payload("only")], "any-model")
        assert len(results) == 1
        assert results[0].score == pytest.approx(0.77)


# ---------------------------------------------------------------------------
# TestRerankerHarness — harness integration with all deps mocked
# ---------------------------------------------------------------------------

def _write_golden(tmp_path: Path, text: str = "chunk text") -> Path:
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


def _fake_hit(chunk_id: str, score: float = 0.9, text: str = "chunk text") -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id, "text": text}
    hit.score = score
    return hit


class TestRerankerHarness:
    def _run(self, tmp_path, rerank: bool, **kwargs):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]):
            return run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                rerank=rerank,
                limit=1,
                **kwargs,
            )

    def test_rerank_false_skips_cross_encode(self, tmp_path):
        with patch("src.eval.harness.cross_encode") as mock_ce:
            self._run(tmp_path, rerank=False)
        mock_ce.assert_not_called()

    def test_rerank_true_calls_cross_encode(self, tmp_path):
        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.95

        with patch("src.eval.harness.cross_encode", return_value=[mock_result]) as mock_ce:
            self._run(tmp_path, rerank=True)
        mock_ce.assert_called_once()

    def test_rerank_returns_evalrun(self, tmp_path):
        from src.datasets.schema import EvalRun

        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.95

        with patch("src.eval.harness.cross_encode", return_value=[mock_result]):
            run = self._run(tmp_path, rerank=True)
        assert isinstance(run, EvalRun)

    def test_rerank_pipeline_mode_appended(self, tmp_path):
        # When the CLI sets pipeline_mode="generic_reranked", harness stores it as-is.
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")
        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.9

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]), \
             patch("src.eval.harness.cross_encode", return_value=[mock_result]):
            run = run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                pipeline_mode="generic_reranked",
                rerank=True,
                limit=1,
            )
        assert run.pipeline_mode == "generic_reranked"

    def test_rerank_config_hash_differs_from_no_rerank(self, tmp_path):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")
        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.9

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]), \
             patch("src.eval.harness.cross_encode", return_value=[mock_result]):
            run_reranked = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense",
                pipeline_mode="generic_reranked", rerank=True, limit=1,
            )

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]):
            run_plain = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense",
                pipeline_mode="generic", rerank=False, limit=1,
            )

        assert run_reranked.config_hash != run_plain.config_hash

    def test_rerank_cross_encode_receives_query_text(self, tmp_path):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0", text="relevant passage")
        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.9

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]), \
             patch("src.eval.harness.cross_encode", return_value=[mock_result]) as mock_ce:
            run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense", rerank=True, limit=1,
            )

        call_args = mock_ce.call_args
        assert call_args.args[0] == "What is X?"

    def test_rerank_hybrid_calls_cross_encode(self, tmp_path):
        from qdrant_client.models import SparseVector

        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        sparse_vec = SparseVector(indices=[0], values=[1.0])
        hit = _fake_hit("open_ragbench:doc1:0")
        mock_result = MagicMock()
        mock_result.payload = {"chunk_id": "open_ragbench:doc1:0"}
        mock_result.score = 0.9

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.encode_sparse_query", return_value=[sparse_vec]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]), \
             patch("src.eval.harness.cross_encode", return_value=[mock_result]) as mock_ce:
            run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="hybrid",
                pipeline_mode="hybrid_rrf_reranked",
                rerank=True,
                limit=1,
            )

        mock_ce.assert_called_once()
