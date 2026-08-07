"""Tests for R-07: routing ablation infrastructure.

Covers:
  - harness.run_retrieval_eval() routes search_batch to the specified collection
  - _config_hash differs when collection differs from dataset_id
  - _config_hash is unchanged when collection equals dataset_id
  - pipeline_mode is stored correctly in EvalRun
  - --collection and --pipeline-mode flags wire through run_dataset
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.eval.harness import _config_hash, run_retrieval_eval


# ---------------------------------------------------------------------------
# _config_hash
# ---------------------------------------------------------------------------

class TestConfigHashCollection:
    def test_same_as_dataset_id_no_change(self):
        h1 = _config_hash(5, "generic", "dense")
        h2 = _config_hash(5, "generic", "dense", collection="open_ragbench",
                          dataset_id="open_ragbench")
        assert h1 == h2

    def test_different_collection_changes_hash(self):
        h1 = _config_hash(5, "generic", "dense", collection="open_ragbench",
                          dataset_id="open_ragbench")
        h2 = _config_hash(5, "generic", "dense", collection="open_ragbench_routed",
                          dataset_id="open_ragbench")
        assert h1 != h2

    def test_none_collection_equals_no_collection(self):
        h1 = _config_hash(5, "routed", "dense")
        h2 = _config_hash(5, "routed", "dense", collection=None, dataset_id="open_ragbench")
        assert h1 == h2

    def test_routed_pipeline_mode_changes_hash(self):
        h_generic = _config_hash(5, "generic", "dense")
        h_routed = _config_hash(5, "routed", "dense")
        assert h_generic != h_routed


# ---------------------------------------------------------------------------
# Harness uses specified collection in search_batch calls
# ---------------------------------------------------------------------------

def _golden_file(tmp_path: Path, dataset_id: str = "open_ragbench") -> Path:
    from src.datasets.golden import GoldenQrel, GoldenQuery
    q = GoldenQuery(
        query_id="q1",
        dataset_id=dataset_id,
        query_text="What is X?",
        qrels=[GoldenQrel(chunk_id=f"{dataset_id}:doc1:0", relevance=2)],
    )
    p = tmp_path / "golden.jsonl"
    p.write_text(q.model_dump_json() + "\n", encoding="utf-8")
    return p


def _fake_hit(chunk_id: str, score: float = 0.9) -> MagicMock:
    hit = MagicMock()
    hit.payload = {"chunk_id": chunk_id, "text": "text"}
    hit.score = score
    return hit


class TestHarnessCollection:
    def _run(self, tmp_path: Path, collection: str | None = None, **kwargs):
        path = _golden_file(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch", return_value=[[hit]]) as mock_sb:
            result = run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                collection=collection,
                limit=1,
                **kwargs,
            )
            return result, mock_sb

    def test_default_collection_is_dataset_id(self, tmp_path):
        _, mock_sb = self._run(tmp_path)
        args = mock_sb.call_args
        # second positional arg is the collection name
        assert args[0][1] == "open_ragbench"

    def test_custom_collection_passed_to_search_batch(self, tmp_path):
        _, mock_sb = self._run(tmp_path, collection="open_ragbench_routed")
        assert mock_sb.call_args[0][1] == "open_ragbench_routed"

    def test_none_collection_uses_dataset_id(self, tmp_path):
        _, mock_sb = self._run(tmp_path, collection=None)
        assert mock_sb.call_args[0][1] == "open_ragbench"

    def test_evalrun_pipeline_mode_stored(self, tmp_path):
        path = _golden_file(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")
        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch", return_value=[[hit]]):
            run = run_retrieval_eval(
                "open_ragbench", path,
                pipeline_mode="routed",
                retrieval_mode="dense",
                collection="open_ragbench_routed",
                limit=1,
            )
        assert run.pipeline_mode == "routed"

    def test_config_hash_differs_between_collections(self, tmp_path):
        path = _golden_file(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")
        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch", return_value=[[hit]]):
            run_orig = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense",
                collection="open_ragbench", limit=1,
            )
            run_routed = run_retrieval_eval(
                "open_ragbench", path, retrieval_mode="dense",
                collection="open_ragbench_routed", limit=1,
            )
        assert run_orig.config_hash != run_routed.config_hash

    def test_doc_aggregate_works_with_custom_collection(self, tmp_path):
        run, _ = self._run(tmp_path, collection="open_ragbench_routed",
                           doc_aggregate=True)
        assert "doc_R@5" in run.metrics

    def test_returns_evalrun(self, tmp_path):
        from src.datasets.schema import EvalRun
        run, _ = self._run(tmp_path)
        assert isinstance(run, EvalRun)


# ---------------------------------------------------------------------------
# run_dataset wires collection and pipeline_mode_override
# ---------------------------------------------------------------------------

class TestRunDatasetFlags:
    def _call_run_dataset(self, tmp_path: Path, **kwargs):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.eval import run_dataset

        with patch("scripts.eval.run_retrieval_eval") as mock_eval, \
             patch("scripts.eval.GOLDEN_DIR", tmp_path), \
             patch("scripts.eval.RESULTS_DIR", tmp_path):
            # create a fake golden file so it exists
            (tmp_path / "open_ragbench.jsonl").write_text("")
            # run_retrieval_eval needs to return an EvalRun-like object
            from src.datasets.schema import EvalRun
            import uuid
            from datetime import datetime, timezone
            fake_run = EvalRun(
                run_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                git_commit="abc",
                config_hash="00000000",
                dataset_id="open_ragbench",
                model="retrieval_only",
                quantization="none",
                context_window=0,
                temperature=0.0,
                reasoning_enabled=False,
                pipeline_mode=kwargs.get("pipeline_mode_override", "generic") or "generic",
                metrics={"R@5": 0.5},
            )
            mock_eval.return_value = fake_run
            run_dataset("open_ragbench", 5, 10, "dense", **kwargs)
            return mock_eval

    def test_collection_forwarded(self, tmp_path):
        mock = self._call_run_dataset(tmp_path, collection="open_ragbench_routed")
        _, kwargs = mock.call_args
        assert kwargs["collection"] == "open_ragbench_routed"

    def test_none_collection_forwarded(self, tmp_path):
        mock = self._call_run_dataset(tmp_path)
        _, kwargs = mock.call_args
        assert kwargs["collection"] is None

    def test_pipeline_mode_override_sets_pipeline_mode(self, tmp_path):
        mock = self._call_run_dataset(tmp_path, pipeline_mode_override="routed")
        _, kwargs = mock.call_args
        assert kwargs["pipeline_mode"] == "routed"

    def test_default_pipeline_mode_is_generic(self, tmp_path):
        mock = self._call_run_dataset(tmp_path)
        _, kwargs = mock.call_args
        assert kwargs["pipeline_mode"] == "generic"
