"""Tests for the evaluation methodology invariants (manutenzione 2026-08-07).

These pin three properties that were violated by every run produced before this
date, and whose violation was invisible in the result files:

  1. retrieval goes at least as deep as the deepest measure asks for
  2. every run reports the same metric keys, so any two are comparable
  3. every run records how many queries it actually evaluated

Each is cheap to break again by a plausible-looking edit, and none of them
would show up as a crash — only as numbers that are quietly wrong.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import src.config as cfg
from src.datasets.golden import GoldenQrel, GoldenQuery
from src.eval.harness import _config_hash, run_retrieval_eval
from src.eval.metrics import DEFAULT_MEASURES, METRIC_DEPTH, _required_depth


def _golden(tmp_path: Path, dataset_id: str = "open_ragbench") -> Path:
    q = GoldenQuery(
        query_id="q1",
        dataset_id=dataset_id,
        query_text="What is X?",
        qrels=[GoldenQrel(chunk_id=f"{dataset_id}:doc1:0", relevance=2)],
    )
    p = tmp_path / "golden.jsonl"
    p.write_text(q.model_dump_json() + "\n", encoding="utf-8")
    return p


def _hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    h = MagicMock()
    h.payload = {"chunk_id": chunk_id, "text": "t"}
    h.score = score
    return h


def _run(tmp_path: Path, n_hits: int = 30, **kwargs):
    """Run the harness against a mocked Qdrant, returning (EvalRun, search mock)."""
    hits = [_hit(f"open_ragbench:doc{i}:0", 0.9 - i / 100) for i in range(n_hits)]
    with patch("src.eval.harness.get_client"), \
         patch("src.eval.retrieval_backends.encode", return_value=[[0.1] * 1024]), \
         patch("src.eval.retrieval_backends.encode_sparse_query", return_value=[MagicMock()]), \
         patch("src.eval.retrieval_backends.search_batch", return_value=[hits]) as sb, \
         patch("src.eval.harness.cross_encode", side_effect=lambda q, p, m, top_n: [
             _hit(x["chunk_id"]) for x in p[:top_n]
         ]):
        run = run_retrieval_eval("open_ragbench", _golden(tmp_path), **kwargs)
    return run, sb


# ---------------------------------------------------------------------------
# 1. Retrieval depth vs measure depth
# ---------------------------------------------------------------------------

class TestMetricDepth:
    def test_derived_from_the_measure_list(self):
        """Hardcoding 10 would silently truncate again if nDCG@20 were added."""
        assert METRIC_DEPTH == _required_depth(DEFAULT_MEASURES)

    def test_current_measures_need_ten(self):
        assert METRIC_DEPTH == 10

    def test_depth_helper_reads_the_deepest_cutoff(self):
        from ir_measures import Recall, nDCG
        assert _required_depth([Recall @ 5, nDCG @ 20]) == 20

    def test_depth_helper_handles_measures_without_cutoff(self):
        assert _required_depth([]) == 1

    def test_small_top_k_still_fetches_metric_depth(self, tmp_path):
        """The actual defect: top_k=5 used to fetch 5, making R@10 unmeasurable."""
        _, sb = _run(tmp_path, top_k=5)
        assert sb.call_args.kwargs["top_k"] >= METRIC_DEPTH

    def test_large_top_k_is_respected(self, tmp_path):
        _, sb = _run(tmp_path, top_k=50)
        assert sb.call_args.kwargs["top_k"] == 50

    def test_rerank_fetches_at_least_the_rerank_pool(self, tmp_path):
        _, sb = _run(tmp_path, top_k=5, rerank=True)
        assert sb.call_args.kwargs["top_k"] >= cfg.RERANK_FETCH_K

    def test_rerank_still_reaches_metric_depth(self, tmp_path):
        _, sb = _run(tmp_path, top_k=5, rerank=True)
        assert sb.call_args.kwargs["top_k"] >= METRIC_DEPTH

    def test_r10_can_exceed_r5(self, tmp_path):
        """With a relevant chunk at rank 8, R@10 must see it and R@5 must not.

        This is the assertion that would have caught the original bug.
        """
        hits = [_hit(f"open_ragbench:other{i}:0", 0.9 - i / 100) for i in range(7)]
        hits.append(_hit("open_ragbench:doc1:0", 0.1))  # rank 8, the relevant one
        with patch("src.eval.harness.get_client"), \
             patch("src.eval.retrieval_backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.retrieval_backends.search_batch", return_value=[hits]):
            run = run_retrieval_eval("open_ragbench", _golden(tmp_path), top_k=5)
        assert run.metrics["R@5"] == 0.0
        assert run.metrics["R@10"] == 1.0


# ---------------------------------------------------------------------------
# 2. Every run reports the same metric keys
# ---------------------------------------------------------------------------

class TestMetricConsistency:
    EXPECTED = {"R@5", "R@10", "nDCG@10", "RR@10", "Success@1", "doc_R@5", "doc_R@10"}

    def test_default_run_has_every_metric(self, tmp_path):
        run, _ = _run(tmp_path)
        assert set(run.metrics) == self.EXPECTED

    @pytest.mark.parametrize("kwargs", [
        {"retrieval_mode": "dense"},
        {"retrieval_mode": "sparse"},
        {"retrieval_mode": "hybrid"},
        {"rerank": True},
        {"doc_aggregate": True},
        {"doc_aggregate": False},
        {"filter_content_type": "text"},
        {"top_k": 20},
    ])
    def test_metric_keys_identical_across_configs(self, tmp_path, kwargs):
        """Any two runs must be comparable without checking which flags were on."""
        run, _ = _run(tmp_path, **kwargs)
        assert set(run.metrics) == self.EXPECTED

    def test_doc_metrics_no_longer_depend_on_the_flag(self, tmp_path):
        on, _ = _run(tmp_path, doc_aggregate=True)
        off, _ = _run(tmp_path, doc_aggregate=False)
        assert set(on.metrics) == set(off.metrics)


# ---------------------------------------------------------------------------
# 3. Sample size is recorded
# ---------------------------------------------------------------------------

class TestSampleSizeRecorded:
    def test_n_queries_present(self, tmp_path):
        run, _ = _run(tmp_path)
        assert run.config["n_queries"] == 1

    def test_eval_depth_present(self, tmp_path):
        run, _ = _run(tmp_path, top_k=5)
        assert run.config["eval_depth"] == METRIC_DEPTH

    def test_eval_depth_follows_large_top_k(self, tmp_path):
        run, _ = _run(tmp_path, top_k=50)
        assert run.config["eval_depth"] == 50


# ---------------------------------------------------------------------------
# config_hash: pre-fix and post-fix runs must not collide
# ---------------------------------------------------------------------------

class TestConfigHashSeparatesTheFix:
    def test_eval_depth_changes_the_hash(self):
        """An archived run and a new one with the same flags are NOT comparable."""
        old = _config_hash(5, "generic", "dense")
        new = _config_hash(5, "generic", "dense", eval_depth=10)
        assert old != new

    def test_archived_hashes_are_reproducible(self):
        """Omitting eval_depth still reproduces the pre-fix hash, so the archive
        stays interpretable."""
        assert _config_hash(5, "generic", "dense") == _config_hash(
            5, "generic", "dense", eval_depth=None
        )

    def test_different_depths_differ(self):
        assert _config_hash(5, "generic", "dense", eval_depth=10) != _config_hash(
            5, "generic", "dense", eval_depth=20
        )

    def test_n_queries_is_not_in_the_hash(self, tmp_path):
        """Sample size is not a configuration; the dashboard flags it separately."""
        a, _ = _run(tmp_path)
        b, _ = _run(tmp_path, limit=1)
        assert a.config_hash == b.config_hash


class TestConfigHashSeparatesTheIdfFix:
    """R-08. Turning on `modifier=IDF` changed every sparse score, so a run
    from before it must not share a name with one from after."""

    # Literals, not recomputed: these are the hashes actually written into
    # eval/results before R-08.  If this test fails, six archived runs have
    # silently stopped matching their own filenames.
    PRE_R08_SPARSE = "adb48814"
    PRE_R08_HYBRID = "3d3ed9e7"
    PRE_R08_HYBRID_RERANK = "fc616cbe"

    @pytest.mark.parametrize("mode", ["sparse", "hybrid"])
    def test_sparse_modes_got_a_new_identity(self, mode):
        pre = {"sparse": self.PRE_R08_SPARSE, "hybrid": self.PRE_R08_HYBRID}[mode]
        assert _config_hash(5, "generic", mode, eval_depth=10) != pre

    def test_hybrid_rerank_got_a_new_identity(self):
        assert _config_hash(
            5, "generic", "hybrid", rerank=True, eval_depth=10
        ) != self.PRE_R08_HYBRID_RERANK

    @pytest.mark.parametrize("expected,depth", [("bbaaca85", None), ("5c3c7fa2", 10)])
    def test_dense_identity_is_untouched(self, expected, depth):
        """The other half of the rule, and the harder one to keep.

        R-08 changed nothing a dense run reads, so dense runs must keep the
        names they already have — C-06 and the whole of Fase 4 are compared
        against them.  A hash change here would orphan every one of those
        measurements without a single test failing anywhere else.
        """
        assert _config_hash(5, "generic", "dense", eval_depth=depth) == expected

    def test_dense_and_sparse_are_still_distinct(self):
        assert _config_hash(5, "generic", "dense", eval_depth=10) != _config_hash(
            5, "generic", "sparse", eval_depth=10
        )
