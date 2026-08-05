"""Tests for D-01: dashboard helper functions (eval_store + golden_store)."""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.datasets.schema import EvalRun
from src.datasets.golden import GoldenQuery, GoldenQrel
from dashboard.eval_store import compare_table, load_eval_runs, run_label
from dashboard.golden_store import (
    example_queries,
    filter_queries,
    load_golden_queries,
    recall_at_k,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(
    dataset_id: str = "open_ragbench",
    pipeline_mode: str = "generic",
    metrics: dict | None = None,
    git_commit: str = "abc1234",
    timestamp: datetime | None = None,
) -> EvalRun:
    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=timestamp or datetime.now(timezone.utc),
        git_commit=git_commit,
        config_hash="deadbeef",
        dataset_id=dataset_id,
        model="multilingual-e5-large",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode=pipeline_mode,
        metrics=metrics or {"nDCG@10": 0.68, "R@5": 0.80},
    )


def _write_run(tmp_path: Path, run: EvalRun) -> Path:
    p = tmp_path / f"{run.run_id}.json"
    p.write_text(
        json.dumps(run.model_dump(mode="json"), ensure_ascii=False), encoding="utf-8"
    )
    return p


# ---------------------------------------------------------------------------
# load_eval_runs
# ---------------------------------------------------------------------------

class TestLoadEvalRuns:
    def test_empty_dir_returns_empty_list(self, tmp_path):
        assert load_eval_runs(tmp_path) == []

    def test_loads_single_run(self, tmp_path):
        run = _make_run()
        _write_run(tmp_path, run)
        loaded = load_eval_runs(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].run_id == run.run_id

    def test_loads_multiple_runs(self, tmp_path):
        for _ in range(3):
            _write_run(tmp_path, _make_run())
        loaded = load_eval_runs(tmp_path)
        assert len(loaded) == 3

    def test_sorted_newest_first(self, tmp_path):
        base = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        ordered = []
        for i in range(3):
            r = _make_run(timestamp=base + timedelta(hours=i))
            _write_run(tmp_path, r)
            ordered.append(r)
        loaded = load_eval_runs(tmp_path)
        assert loaded[0].timestamp == ordered[-1].timestamp  # newest first
        assert loaded[-1].timestamp == ordered[0].timestamp  # oldest last

    def test_skips_noise_floor_files(self, tmp_path):
        noise = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": "abc",
            "n_runs": 5,
            "dataset_id": "open_ragbench",
            "pipeline_mode": "generic",
            "retrieval_mode": "dense",
            "metric_stats": {},
        }
        (tmp_path / "noise.json").write_text(json.dumps(noise), encoding="utf-8")
        assert load_eval_runs(tmp_path) == []

    def test_skips_invalid_json(self, tmp_path):
        (tmp_path / "broken.json").write_text("not valid json {{{", encoding="utf-8")
        assert load_eval_runs(tmp_path) == []

    def test_skips_non_json_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("ignore me", encoding="utf-8")
        _write_run(tmp_path, _make_run())
        loaded = load_eval_runs(tmp_path)
        assert len(loaded) == 1

    def test_returns_eval_run_instances(self, tmp_path):
        _write_run(tmp_path, _make_run())
        loaded = load_eval_runs(tmp_path)
        assert isinstance(loaded[0], EvalRun)

    def test_preserves_metrics(self, tmp_path):
        run = _make_run(metrics={"nDCG@10": 0.72, "R@5": 0.85})
        _write_run(tmp_path, run)
        loaded = load_eval_runs(tmp_path)
        assert loaded[0].metrics["nDCG@10"] == pytest.approx(0.72)
        assert loaded[0].metrics["R@5"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# run_label
# ---------------------------------------------------------------------------

class TestRunLabel:
    def test_contains_dataset_id(self):
        run = _make_run(dataset_id="ledger")
        assert "ledger" in run_label(run)

    def test_contains_pipeline_mode(self):
        run = _make_run(pipeline_mode="baseline_c")
        assert "baseline_c" in run_label(run)

    def test_contains_short_commit(self):
        run = _make_run(git_commit="abc1234deadbeef")
        label = run_label(run)
        assert "abc1234" in label

    def test_label_is_string(self):
        assert isinstance(run_label(_make_run()), str)

    def test_different_runs_different_labels(self):
        r1 = _make_run(dataset_id="open_ragbench")
        r2 = _make_run(dataset_id="ledger")
        assert run_label(r1) != run_label(r2)


# ---------------------------------------------------------------------------
# compare_table
# ---------------------------------------------------------------------------

class TestCompareTable:
    def test_all_metrics_present(self):
        runs = [
            _make_run(metrics={"nDCG@10": 0.68, "R@5": 0.80}),
            _make_run(metrics={"nDCG@10": 0.72, "R@5": 0.85}),
        ]
        table = compare_table(runs)
        assert "nDCG@10" in table
        assert "R@5" in table

    def test_correct_values_per_run(self):
        runs = [
            _make_run(metrics={"nDCG@10": 0.68}),
            _make_run(metrics={"nDCG@10": 0.72}),
        ]
        table = compare_table(runs)
        assert table["nDCG@10"][0] == pytest.approx(0.68)
        assert table["nDCG@10"][1] == pytest.approx(0.72)

    def test_missing_metric_is_nan(self):
        runs = [
            _make_run(metrics={"nDCG@10": 0.68, "R@5": 0.80}),
            _make_run(metrics={"nDCG@10": 0.72}),
        ]
        table = compare_table(runs)
        assert math.isnan(table["R@5"][1])

    def test_single_run(self):
        run = _make_run(metrics={"nDCG@10": 0.68})
        table = compare_table([run])
        assert table["nDCG@10"] == [pytest.approx(0.68)]

    def test_metrics_in_sorted_order(self):
        run = _make_run(metrics={"z_metric": 0.1, "a_metric": 0.9, "m_metric": 0.5})
        table = compare_table([run])
        assert list(table.keys()) == sorted(table.keys())

    def test_union_of_metrics_across_runs(self):
        runs = [
            _make_run(metrics={"nDCG@10": 0.68}),
            _make_run(metrics={"R@5": 0.80}),
        ]
        table = compare_table(runs)
        assert set(table.keys()) == {"nDCG@10", "R@5"}

    def test_three_runs(self):
        runs = [_make_run(metrics={"nDCG@10": v}) for v in [0.60, 0.65, 0.70]]
        table = compare_table(runs)
        assert len(table["nDCG@10"]) == 3
        assert table["nDCG@10"] == pytest.approx([0.60, 0.65, 0.70])

    def test_generation_metrics(self):
        runs = [
            _make_run(metrics={"abstention_rate": 0.2, "correct_rate": 0.6, "wrong_rate": 0.2}),
            _make_run(metrics={"abstention_rate": 0.3, "correct_rate": 0.5, "wrong_rate": 0.2}),
        ]
        table = compare_table(runs)
        assert set(table.keys()) == {"abstention_rate", "correct_rate", "wrong_rate"}


# =============================================================================
# golden_store helpers
# =============================================================================

def _make_golden_query(
    query_text: str = "What is the RMSE?",
    answerable: bool = True,
    n_qrels: int = 1,
    dataset_id: str = "open_ragbench",
    reference_answer: str | None = "0.42",
) -> GoldenQuery:
    qrels = [GoldenQrel(chunk_id=f"open_ragbench:doc{i}:0", relevance=2) for i in range(n_qrels)]
    return GoldenQuery(
        query_id=str(uuid.uuid4()),
        dataset_id=dataset_id,
        query_text=query_text,
        qrels=qrels if answerable else [],
        answerable=answerable,
        reference_answer=reference_answer,
    )


def _write_golden(tmp_path: Path, queries: list[GoldenQuery]) -> Path:
    p = tmp_path / "test.jsonl"
    lines = [q.model_dump_json() for q in queries]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


class TestLoadGoldenQueries:
    def test_nonexistent_path_returns_empty(self, tmp_path):
        assert load_golden_queries(tmp_path / "nope.jsonl") == []

    def test_loads_single_query(self, tmp_path):
        q = _make_golden_query()
        p = _write_golden(tmp_path, [q])
        loaded = load_golden_queries(p)
        assert len(loaded) == 1
        assert loaded[0].query_id == q.query_id

    def test_loads_multiple_queries(self, tmp_path):
        qs = [_make_golden_query(f"Query {i}") for i in range(5)]
        p = _write_golden(tmp_path, qs)
        loaded = load_golden_queries(p)
        assert len(loaded) == 5

    def test_preserves_query_text(self, tmp_path):
        q = _make_golden_query("What is the standard deviation?")
        p = _write_golden(tmp_path, [q])
        loaded = load_golden_queries(p)
        assert loaded[0].query_text == "What is the standard deviation?"

    def test_preserves_answerable_flag(self, tmp_path):
        qs = [_make_golden_query(answerable=True), _make_golden_query(answerable=False)]
        p = _write_golden(tmp_path, qs)
        loaded = load_golden_queries(p)
        flags = {q.answerable for q in loaded}
        assert flags == {True, False}

    def test_skips_malformed_lines(self, tmp_path):
        q = _make_golden_query()
        p = tmp_path / "test.jsonl"
        p.write_text(q.model_dump_json() + "\nnot valid json\n", encoding="utf-8")
        loaded = load_golden_queries(p)
        assert len(loaded) == 1

    def test_skips_blank_lines(self, tmp_path):
        q = _make_golden_query()
        p = tmp_path / "test.jsonl"
        p.write_text("\n" + q.model_dump_json() + "\n\n", encoding="utf-8")
        loaded = load_golden_queries(p)
        assert len(loaded) == 1


class TestFilterQueries:
    def test_no_filter_returns_all(self):
        qs = [_make_golden_query() for _ in range(4)]
        assert filter_queries(qs) == qs

    def test_filter_answerable_true(self):
        qs = [_make_golden_query(answerable=True), _make_golden_query(answerable=False)]
        result = filter_queries(qs, answerable=True)
        assert all(q.answerable for q in result)
        assert len(result) == 1

    def test_filter_answerable_false(self):
        qs = [_make_golden_query(answerable=True), _make_golden_query(answerable=False)]
        result = filter_queries(qs, answerable=False)
        assert all(not q.answerable for q in result)
        assert len(result) == 1

    def test_filter_by_search_text(self):
        qs = [
            _make_golden_query("What is RMSE?"),
            _make_golden_query("What is the revenue?"),
        ]
        result = filter_queries(qs, search="rmse")
        assert len(result) == 1
        assert "RMSE" in result[0].query_text

    def test_filter_search_case_insensitive(self):
        qs = [_make_golden_query("What is RMSE?")]
        assert len(filter_queries(qs, search="rmse")) == 1
        assert len(filter_queries(qs, search="RMSE")) == 1
        assert len(filter_queries(qs, search="Rmse")) == 1

    def test_filter_combined(self):
        qs = [
            _make_golden_query("What is RMSE?", answerable=True),
            _make_golden_query("What is RMSE?", answerable=False),
            _make_golden_query("What is revenue?", answerable=True),
        ]
        result = filter_queries(qs, answerable=True, search="rmse")
        assert len(result) == 1
        assert result[0].answerable

    def test_filter_no_match_returns_empty(self):
        qs = [_make_golden_query("What is RMSE?")]
        assert filter_queries(qs, search="nonexistent_xyz") == []


class TestExampleQueries:
    def test_returns_query_texts(self):
        qs = [_make_golden_query(f"Query {i}") for i in range(3)]
        result = example_queries(qs, n=3)
        assert len(result) == 3
        assert all(isinstance(s, str) for s in result)

    def test_respects_n_limit(self):
        qs = [_make_golden_query(f"Q{i}") for i in range(10)]
        result = example_queries(qs, n=4)
        assert len(result) == 4

    def test_excludes_unanswerable(self):
        qs = [
            _make_golden_query("Good query", answerable=True),
            _make_golden_query("Bad query", answerable=False),
        ]
        result = example_queries(qs, n=10)
        assert all("Good" in s for s in result)

    def test_excludes_queries_without_qrels(self):
        qs = [
            _make_golden_query("Has qrels", n_qrels=1),
            _make_golden_query("No qrels", n_qrels=0),
        ]
        result = example_queries(qs, n=10)
        assert all("Has qrels" in s for s in result)

    def test_empty_input_returns_empty(self):
        assert example_queries([], n=5) == []


class TestRecallAtK:
    def _make_query_with_qrels(self, chunk_ids: list[str]) -> GoldenQuery:
        return GoldenQuery(
            query_id="q1",
            dataset_id="test",
            query_text="test",
            qrels=[GoldenQrel(chunk_id=cid, relevance=2) for cid in chunk_ids],
            answerable=True,
        )

    def test_perfect_recall(self):
        q = self._make_query_with_qrels(["a:doc:0"])
        assert recall_at_k(q, ["a:doc:0"], k=1) == pytest.approx(1.0)

    def test_zero_recall(self):
        q = self._make_query_with_qrels(["a:doc:0"])
        assert recall_at_k(q, ["b:doc:1", "c:doc:2"], k=2) == pytest.approx(0.0)

    def test_partial_recall(self):
        q = self._make_query_with_qrels(["a:doc:0", "b:doc:1"])
        assert recall_at_k(q, ["a:doc:0", "c:doc:2"], k=2) == pytest.approx(0.5)

    def test_k_cutoff_respected(self):
        # Golden chunk is at position 3, k=2 → not found
        q = self._make_query_with_qrels(["a:doc:0"])
        assert recall_at_k(q, ["x", "y", "a:doc:0"], k=2) == pytest.approx(0.0)

    def test_empty_qrels_returns_zero(self):
        q = GoldenQuery(
            query_id="q1", dataset_id="test", query_text="t", qrels=[], answerable=False
        )
        assert recall_at_k(q, ["a:doc:0"], k=5) == pytest.approx(0.0)
