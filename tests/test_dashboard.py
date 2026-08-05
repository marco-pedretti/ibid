"""Tests for D-01: dashboard helper functions in dashboard/eval_store.py."""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.datasets.schema import EvalRun
from dashboard.eval_store import compare_table, load_eval_runs, run_label


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
