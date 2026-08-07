"""Tests for the retrieval evaluation harness (E-03/E-06/R-01).

Qdrant client and embedding functions are mocked — no server required.
search_batch is patched instead of search: the harness sends queries in bulk
to avoid Windows socket exhaustion on large datasets.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.datasets.golden import GoldenQrel, GoldenQuery
from src.datasets.schema import EvalRun
from src.eval.harness import run_retrieval_eval


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_golden(tmp_path: Path, queries: list[GoldenQuery]) -> Path:
    p = tmp_path / "golden.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(q.model_dump_json() + "\n")
    return p


def _answerable(qid: str = "q1", chunk_id: str = "open_ragbench:doc1:0") -> GoldenQuery:
    return GoldenQuery(
        query_id=qid,
        dataset_id="open_ragbench",
        query_text="What is X?",
        qrels=[GoldenQrel(chunk_id=chunk_id, relevance=2)],
    )


def _fake_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id}
    hit.score = score
    return hit


# search_batch returns list[list[hit]] — one inner list per query
def _batch_result(chunk_id: str, score: float = 0.9):
    return [[_fake_hit(chunk_id, score)]]


# ---------------------------------------------------------------------------
# Dense retrieval (E-03 path)
# ---------------------------------------------------------------------------

class TestDenseRetrieval:
    def test_returns_evalrun(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        fake_vec = [0.1] * 1024

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[fake_vec]), \
             patch("src.eval.harness.search_batch",
                   return_value=[[ _fake_hit("open_ragbench:doc1:0")]]):
            run = run_retrieval_eval("open_ragbench", path, top_k=5, limit=1)

        assert isinstance(run, EvalRun)

    def test_dense_calls_encode_not_encode_sparse(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        fake_vec = [0.1] * 1024

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[fake_vec]) as mock_enc, \
             patch("src.eval.harness.encode_sparse") as mock_sparse, \
             patch("src.eval.harness.search_batch", return_value=[[]]):
            run_retrieval_eval("open_ragbench", path, retrieval_mode="dense", limit=1)

        mock_enc.assert_called_once()
        mock_sparse.assert_not_called()

    def test_dense_searches_with_dense_using(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        fake_vec = [0.1] * 1024

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[fake_vec]), \
             patch("src.eval.harness.search_batch", return_value=[[]]) as mock_batch:
            run_retrieval_eval("open_ragbench", path, retrieval_mode="dense", limit=1)

        _, kwargs = mock_batch.call_args
        assert kwargs.get("using") == "dense"

    def test_pipeline_mode_generic_for_dense(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch", return_value=[[]]):
            run = run_retrieval_eval("open_ragbench", path, pipeline_mode="generic", limit=1)

        assert run.pipeline_mode == "generic"

    def test_perfect_hit_recall_is_1(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable(chunk_id="open_ragbench:doc1:0")])

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch",
                   return_value=[[_fake_hit("open_ragbench:doc1:0", 0.95)]]):
            run = run_retrieval_eval("open_ragbench", path, limit=1)

        r5_key = next(k for k in run.metrics if "R@5" in k or ("Recall" in k and "@5" in k))
        assert run.metrics[r5_key] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Sparse retrieval — E-06 (lexical-only BM25)
# ---------------------------------------------------------------------------

class TestSparseRetrieval:
    def _fake_sparse_vec(self):
        from qdrant_client.models import SparseVector
        return SparseVector(indices=[0, 1, 2], values=[0.5, 0.3, 0.2])

    def test_sparse_calls_encode_sparse_not_encode(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        sparse_vec = self._fake_sparse_vec()

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode") as mock_dense, \
             patch("src.eval.harness.encode_sparse",
                   return_value=[sparse_vec]) as mock_sparse, \
             patch("src.eval.harness.search_batch", return_value=[[]]):
            run_retrieval_eval("open_ragbench", path, retrieval_mode="sparse", limit=1)

        mock_sparse.assert_called_once()
        mock_dense.assert_not_called()

    def test_sparse_searches_with_sparse_using(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        sparse_vec = self._fake_sparse_vec()

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode_sparse", return_value=[sparse_vec]), \
             patch("src.eval.harness.search_batch", return_value=[[]]) as mock_batch:
            run_retrieval_eval("open_ragbench", path, retrieval_mode="sparse", limit=1)

        _, kwargs = mock_batch.call_args
        assert kwargs.get("using") == "sparse"

    def test_pipeline_mode_baseline_c(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        sparse_vec = self._fake_sparse_vec()

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode_sparse", return_value=[sparse_vec]), \
             patch("src.eval.harness.search_batch", return_value=[[]]):
            run = run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="sparse",
                pipeline_mode="baseline_c",
                limit=1,
            )

        assert run.pipeline_mode == "baseline_c"

    def test_sparse_returns_evalrun(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable()])
        sparse_vec = self._fake_sparse_vec()

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode_sparse", return_value=[sparse_vec]), \
             patch("src.eval.harness.search_batch", return_value=[[]]):
            run = run_retrieval_eval("open_ragbench", path, retrieval_mode="sparse", limit=1)

        assert isinstance(run, EvalRun)
        assert run.model == "retrieval_only"


# ---------------------------------------------------------------------------
# Config hash
# ---------------------------------------------------------------------------

class TestConfigHash:
    def _run(self, tmp_path, **kwargs):
        path = _write_golden(tmp_path, [_answerable()])

        from qdrant_client.models import SparseVector
        sparse_vec = SparseVector(indices=[0], values=[1.0])

        retrieval_mode = kwargs.get("retrieval_mode", "dense")

        if retrieval_mode == "sparse":
            embed_patch = patch("src.eval.harness.encode_sparse", return_value=[sparse_vec])
        elif retrieval_mode == "hybrid":
            embed_patch = patch("src.eval.harness.encode", return_value=[[0.1] * 1024])
        else:
            embed_patch = patch("src.eval.harness.encode", return_value=[[0.1] * 1024])

        if retrieval_mode == "hybrid":
            with patch("src.eval.harness.get_client"), \
                 embed_patch, \
                 patch("src.eval.harness.encode_sparse", return_value=[sparse_vec]), \
                 patch("src.eval.harness.search_batch", return_value=[[]]):
                return run_retrieval_eval("open_ragbench", path, limit=1, **kwargs)
        else:
            with patch("src.eval.harness.get_client"), \
                 embed_patch, \
                 patch("src.eval.harness.search_batch", return_value=[[]]):
                return run_retrieval_eval("open_ragbench", path, limit=1, **kwargs)

    def test_dense_and_sparse_have_different_hash(self, tmp_path):
        run_dense = self._run(tmp_path, retrieval_mode="dense")
        run_sparse = self._run(tmp_path, retrieval_mode="sparse")
        assert run_dense.config_hash != run_sparse.config_hash

    def test_same_config_same_hash(self, tmp_path):
        run1 = self._run(tmp_path, retrieval_mode="dense", top_k=5)
        run2 = self._run(tmp_path, retrieval_mode="dense", top_k=5)
        assert run1.config_hash == run2.config_hash

    def test_different_top_k_different_hash(self, tmp_path):
        run1 = self._run(tmp_path, retrieval_mode="dense", top_k=5)
        run2 = self._run(tmp_path, retrieval_mode="dense", top_k=10)
        assert run1.config_hash != run2.config_hash
