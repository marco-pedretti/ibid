"""Tests for R-04: metadata filtering (build_content_type_filter, infer_content_type,
search_batch filter threading, harness integration).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.retrieval.metadata_filter import build_content_type_filter, infer_content_type


# ---------------------------------------------------------------------------
# build_content_type_filter
# ---------------------------------------------------------------------------

class TestBuildContentTypeFilter:
    def test_none_for_all(self):
        assert build_content_type_filter("all") is None

    def test_none_for_empty_string(self):
        assert build_content_type_filter("") is None

    def test_returns_filter_for_text(self):
        f = build_content_type_filter("text")
        assert isinstance(f, Filter)

    def test_returns_filter_for_table(self):
        f = build_content_type_filter("table")
        assert isinstance(f, Filter)

    def test_returns_filter_for_mixed(self):
        f = build_content_type_filter("mixed")
        assert isinstance(f, Filter)

    def test_filter_targets_content_type_field(self):
        f = build_content_type_filter("text")
        cond = f.must[0]
        assert isinstance(cond, FieldCondition)
        assert cond.key == "content_type"

    def test_filter_matches_correct_value(self):
        f = build_content_type_filter("table")
        cond = f.must[0]
        assert isinstance(cond.match, MatchValue)
        assert cond.match.value == "table"

    def test_text_filter_value(self):
        f = build_content_type_filter("text")
        assert f.must[0].match.value == "text"


# ---------------------------------------------------------------------------
# infer_content_type
# ---------------------------------------------------------------------------

class TestInferContentType:
    def test_no_keywords_returns_none(self):
        assert infer_content_type("What is the SD of RMSE for Ridge Regression?") is None

    def test_table_keyword_returns_table(self):
        assert infer_content_type("What does the table show?") == "table"

    def test_figure_keyword_returns_table(self):
        assert infer_content_type("Describe the figure in section 3.") == "table"

    def test_graph_keyword_returns_table(self):
        assert infer_content_type("What is shown in the graph?") == "table"

    def test_chart_keyword_returns_table(self):
        assert infer_content_type("Summarize the chart.") == "table"

    def test_italian_table_keyword(self):
        assert infer_content_type("Cosa mostra la tabella?") == "table"

    def test_italian_figure_keyword(self):
        assert infer_content_type("Descrivi la figura 2.") == "table"

    def test_case_insensitive(self):
        assert infer_content_type("Look at the TABLE on page 4.") == "table"

    def test_empty_query_returns_none(self):
        assert infer_content_type("") is None

    def test_generic_query_returns_none(self):
        assert infer_content_type("What is the main finding of the paper?") is None


# ---------------------------------------------------------------------------
# search_batch filter threading
# ---------------------------------------------------------------------------

class TestSearchBatchFilters:
    def _make_client(self):
        client = MagicMock()
        response = MagicMock()
        response.points = []
        client.query_batch_points.return_value = [response]
        return client

    def test_no_filters_passes_none_per_request(self):
        from src.index.store import search_batch
        client = self._make_client()

        search_batch(client, "col", [[0.1] * 4], top_k=5, using="dense", filters=None)

        reqs = client.query_batch_points.call_args.kwargs["requests"]
        assert reqs[0].filter is None

    def test_uniform_filter_applied_to_all(self):
        from src.index.store import search_batch
        client = self._make_client()
        f = build_content_type_filter("text")

        search_batch(client, "col", [[0.1] * 4, [0.2] * 4], top_k=5, using="dense", filters=[f, f])

        reqs = client.query_batch_points.call_args.kwargs["requests"]
        assert reqs[0].filter == f
        assert reqs[1].filter == f

    def test_per_query_filters_applied_individually(self):
        from src.index.store import search_batch
        client = self._make_client()
        client.query_batch_points.return_value = [MagicMock(points=[]), MagicMock(points=[])]
        f_text = build_content_type_filter("text")
        f_table = build_content_type_filter("table")

        search_batch(client, "col", [[0.1] * 4, [0.2] * 4], top_k=5, using="dense",
                     filters=[f_text, f_table])

        reqs = client.query_batch_points.call_args.kwargs["requests"]
        assert reqs[0].filter == f_text
        assert reqs[1].filter == f_table

    def test_none_entry_in_filters_passes_none(self):
        from src.index.store import search_batch
        client = self._make_client()
        client.query_batch_points.return_value = [MagicMock(points=[]), MagicMock(points=[])]
        f = build_content_type_filter("text")

        search_batch(client, "col", [[0.1] * 4, [0.2] * 4], top_k=5, filters=[f, None])

        reqs = client.query_batch_points.call_args.kwargs["requests"]
        assert reqs[0].filter == f
        assert reqs[1].filter is None


# ---------------------------------------------------------------------------
# Harness integration
# ---------------------------------------------------------------------------

def _write_golden(tmp_path: Path) -> Path:
    from src.datasets.golden import GoldenQrel, GoldenQuery

    q = GoldenQuery(
        query_id="q1",
        dataset_id="open_ragbench",
        query_text="What is the main finding?",
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


class TestFilterContentTypeHarness:
    def _run(self, tmp_path: Path, filter_content_type: str | None = None, **kwargs):
        from src.eval.harness import run_retrieval_eval

        path = _write_golden(tmp_path)
        hit = _fake_hit("open_ragbench:doc1:0")

        with patch("src.eval.harness.get_client"), \
             patch("src.retrieval.backends.encode", return_value=[[0.1] * 1024]), \
             patch("src.retrieval.backends.search_batch", return_value=[[hit]]) as mock_sb:
            run = run_retrieval_eval(
                "open_ragbench", path,
                retrieval_mode="dense",
                filter_content_type=filter_content_type,
                limit=1,
                **kwargs,
            )
        return run, mock_sb

    def test_no_filter_passes_none_filters(self, tmp_path):
        _, mock_sb = self._run(tmp_path, filter_content_type=None)
        call_kwargs = mock_sb.call_args.kwargs
        assert call_kwargs.get("filters") is None

    def test_text_filter_builds_filter_list(self, tmp_path):
        _, mock_sb = self._run(tmp_path, filter_content_type="text")
        filters = mock_sb.call_args.kwargs.get("filters")
        assert filters is not None
        assert len(filters) == 1
        assert isinstance(filters[0], Filter)

    def test_table_filter_builds_correct_value(self, tmp_path):
        _, mock_sb = self._run(tmp_path, filter_content_type="table")
        filters = mock_sb.call_args.kwargs.get("filters")
        assert filters[0].must[0].match.value == "table"

    def test_auto_filter_returns_none_for_no_keywords(self, tmp_path):
        # golden query is "What is the main finding?" — no table keywords
        _, mock_sb = self._run(tmp_path, filter_content_type="auto")
        filters = mock_sb.call_args.kwargs.get("filters")
        assert filters is not None
        assert filters[0] is None  # no keyword match → no filter

    def test_config_hash_differs_with_filter(self, tmp_path):
        run_plain, _ = self._run(tmp_path, filter_content_type=None)
        run_filtered, _ = self._run(tmp_path, filter_content_type="text")
        assert run_plain.config_hash != run_filtered.config_hash

    def test_config_hash_differs_text_vs_table(self, tmp_path):
        run_text, _ = self._run(tmp_path, filter_content_type="text")
        run_table, _ = self._run(tmp_path, filter_content_type="table")
        assert run_text.config_hash != run_table.config_hash

    def test_pipeline_mode_stored(self, tmp_path):
        run, _ = self._run(tmp_path, filter_content_type="text",
                           pipeline_mode="generic_filtered_text")
        assert run.pipeline_mode == "generic_filtered_text"

    def test_evalrun_returned(self, tmp_path):
        from src.datasets.schema import EvalRun
        run, _ = self._run(tmp_path, filter_content_type="text")
        assert isinstance(run, EvalRun)
