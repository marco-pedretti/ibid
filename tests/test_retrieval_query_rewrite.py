"""Tests for R-03: query rewriting (rewrite() + harness integration).

The LLM generate() call is mocked throughout — no server required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.retrieval.query_rewrite import rewrite, rewrite_batch


# ---------------------------------------------------------------------------
# TestRewrite — pure unit tests
# ---------------------------------------------------------------------------

class TestRewrite:
    def test_returns_rewritten_string(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="rewritten query"):
            result = rewrite("original query")
        assert result == "rewritten query"

    def test_falls_back_to_original_on_error(self):
        with patch("src.retrieval.query_rewrite.generate", side_effect=RuntimeError("LLM down")):
            result = rewrite("original query")
        assert result == "original query"

    def test_passes_query_as_user_message(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="r") as mock_gen:
            rewrite("my question")
        assert mock_gen.call_args.kwargs["user"] == "my question"

    def test_temperature_is_zero(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="r") as mock_gen:
            rewrite("q")
        assert mock_gen.call_args.kwargs["temperature"] == 0.0

    def test_max_tokens_is_short(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="r") as mock_gen:
            rewrite("q")
        assert mock_gen.call_args.kwargs["max_tokens"] <= 256

    def test_custom_model_passed_through(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="r") as mock_gen:
            rewrite("q", base_url="http://x", model="my-model")
        assert mock_gen.call_args.kwargs["model"] == "my-model"

    def test_strips_whitespace_from_llm_output(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="  trimmed  "):
            result = rewrite("q")
        assert result == "trimmed"


class TestRewriteBatch:
    def test_preserves_length(self):
        with patch("src.retrieval.query_rewrite.generate", return_value="r"):
            results = rewrite_batch(["a", "b", "c"])
        assert len(results) == 3

    def test_preserves_order(self):
        answers = ["first", "second", "third"]
        with patch("src.retrieval.query_rewrite.generate", side_effect=answers):
            results = rewrite_batch(["a", "b", "c"])
        assert results == answers

    def test_empty_input(self):
        with patch("src.retrieval.query_rewrite.generate"):
            results = rewrite_batch([])
        assert results == []

    def test_fallback_per_item_on_error(self):
        def _gen_side_effect(**kwargs):
            if kwargs["user"] == "bad":
                raise RuntimeError("fail")
            return "ok"

        with patch("src.retrieval.query_rewrite.generate", side_effect=_gen_side_effect):
            results = rewrite_batch(["good", "bad", "good"])
        assert results == ["ok", "bad", "ok"]


# ---------------------------------------------------------------------------
# TestQueryRewriteHarness — harness integration
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


class TestQueryRewriteHarness:
    def _run(self, tmp_path: Path, query_rewrite: bool, **kwargs):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.eval.harness.encode", return_value=[[0.1] * 1024]), \
             patch("src.eval.harness.search_batch", return_value=[[hit]]):
            return run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                query_rewrite=query_rewrite,
                limit=1,
                **kwargs,
            )

    def test_query_rewrite_false_skips_rewrite_batch(self, tmp_path):
        with patch("src.eval.harness.rewrite_batch") as mock_rw:
            self._run(tmp_path, query_rewrite=False)
        mock_rw.assert_not_called()

    def test_query_rewrite_true_calls_rewrite_batch(self, tmp_path):
        with patch("src.eval.harness.rewrite_batch", return_value=["rewritten"]) as mock_rw:
            self._run(tmp_path, query_rewrite=True)
        mock_rw.assert_called_once()

    def test_query_rewrite_returns_evalrun(self, tmp_path):
        from src.datasets.schema import EvalRun

        with patch("src.eval.harness.rewrite_batch", return_value=["rewritten"]):
            run = self._run(tmp_path, query_rewrite=True)
        assert isinstance(run, EvalRun)

    def test_config_hash_differs_with_query_rewrite(self, tmp_path):
        with patch("src.eval.harness.rewrite_batch", return_value=["rewritten"]):
            run_rw = self._run(tmp_path, query_rewrite=True, pipeline_mode="generic_rewritten")
        run_plain = self._run(tmp_path, query_rewrite=False)
        assert run_rw.config_hash != run_plain.config_hash

    def test_rewrite_batch_receives_original_texts(self, tmp_path):
        with patch("src.eval.harness.rewrite_batch", return_value=["rewritten"]) as mock_rw:
            self._run(tmp_path, query_rewrite=True)
        call_args = mock_rw.call_args
        assert "What is X?" in call_args.args[0]

    def test_pipeline_mode_stored(self, tmp_path):
        with patch("src.eval.harness.rewrite_batch", return_value=["rewritten"]):
            run = self._run(tmp_path, query_rewrite=True, pipeline_mode="generic_rewritten")
        assert run.pipeline_mode == "generic_rewritten"
