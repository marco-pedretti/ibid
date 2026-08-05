"""Tests for E-07: noise floor measurement."""

from __future__ import annotations

import math
import statistics
import uuid
from datetime import datetime, timezone

import pytest

from src.datasets.schema import EvalRun
from src.eval.noise_floor import (
    MetricStats,
    NoiseFloorResult,
    build_noise_floor_result,
    compute_noise_floor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _run(metrics: dict[str, float], dataset_id: str = "open_ragbench") -> EvalRun:
    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit="abc1234",
        config_hash="deadbeef",
        dataset_id=dataset_id,
        model="retrieval_only",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode="generic",
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# compute_noise_floor
# ---------------------------------------------------------------------------

class TestComputeNoiseFloor:
    def test_empty_runs_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            compute_noise_floor([])

    def test_single_run_std_zero(self):
        stats = compute_noise_floor([_run({"nDCG@10": 0.68})])
        assert stats["nDCG@10"].std == pytest.approx(0.0)
        assert stats["nDCG@10"].mean == pytest.approx(0.68)
        assert stats["nDCG@10"].min_val == pytest.approx(0.68)
        assert stats["nDCG@10"].max_val == pytest.approx(0.68)

    def test_identical_runs_std_zero(self):
        runs = [_run({"nDCG@10": 0.68, "R@5": 0.80}) for _ in range(5)]
        stats = compute_noise_floor(runs)
        assert stats["nDCG@10"].std == pytest.approx(0.0)
        assert stats["R@5"].std == pytest.approx(0.0)

    def test_correct_mean(self):
        runs = [
            _run({"nDCG@10": 0.60}),
            _run({"nDCG@10": 0.70}),
            _run({"nDCG@10": 0.80}),
        ]
        stats = compute_noise_floor(runs)
        assert stats["nDCG@10"].mean == pytest.approx(0.70)

    def test_correct_std_population(self):
        # pstdev([0.60, 0.70, 0.80]) = stdev of full population
        values = [0.60, 0.70, 0.80]
        expected_std = statistics.pstdev(values)
        runs = [_run({"nDCG@10": v}) for v in values]
        stats = compute_noise_floor(runs)
        assert stats["nDCG@10"].std == pytest.approx(expected_std)

    def test_correct_min_max(self):
        runs = [
            _run({"R@5": 0.75}),
            _run({"R@5": 0.80}),
            _run({"R@5": 0.85}),
        ]
        stats = compute_noise_floor(runs)
        assert stats["R@5"].min_val == pytest.approx(0.75)
        assert stats["R@5"].max_val == pytest.approx(0.85)

    def test_all_metrics_present(self):
        runs = [_run({"nDCG@10": 0.68, "R@5": 0.80, "RR@10": 0.64})]
        stats = compute_noise_floor(runs)
        assert set(stats.keys()) == {"nDCG@10", "R@5", "RR@10"}

    def test_missing_metric_in_some_runs_defaults_to_zero(self):
        # One run has metric, another doesn't — missing defaults to 0.0
        runs = [
            _run({"nDCG@10": 0.68, "extra": 0.5}),
            _run({"nDCG@10": 0.70}),  # "extra" absent
        ]
        stats = compute_noise_floor(runs)
        # extra values: [0.5, 0.0] → mean=0.25
        assert stats["extra"].mean == pytest.approx(0.25)

    def test_returns_metric_stats_instances(self):
        stats = compute_noise_floor([_run({"nDCG@10": 0.68})])
        assert isinstance(stats["nDCG@10"], MetricStats)

    def test_five_runs_realistic(self):
        # Simulate realistic retrieval noise: near-zero std for deterministic retrieval
        values = [0.680, 0.680, 0.680, 0.680, 0.680]
        runs = [_run({"nDCG@10": v}) for v in values]
        stats = compute_noise_floor(runs)
        assert stats["nDCG@10"].std == pytest.approx(0.0, abs=1e-6)
        assert stats["nDCG@10"].mean == pytest.approx(0.680)

    def test_metrics_sorted_in_output(self):
        runs = [_run({"z_metric": 0.1, "a_metric": 0.9})]
        stats = compute_noise_floor(runs)
        keys = list(stats.keys())
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# build_noise_floor_result
# ---------------------------------------------------------------------------

class TestBuildNoiseFloorResult:
    def test_returns_noise_floor_result(self):
        runs = [_run({"nDCG@10": 0.68}) for _ in range(3)]
        result = build_noise_floor_result(runs, retrieval_mode="dense")
        assert isinstance(result, NoiseFloorResult)

    def test_n_runs_correct(self):
        runs = [_run({"R@5": 0.8}) for _ in range(5)]
        result = build_noise_floor_result(runs, retrieval_mode="dense")
        assert result.n_runs == 5

    def test_dataset_id_from_first_run(self):
        runs = [_run({"R@5": 0.8}, dataset_id="ledger")]
        result = build_noise_floor_result(runs, retrieval_mode="dense")
        assert result.dataset_id == "ledger"

    def test_retrieval_mode_stored(self):
        runs = [_run({"R@5": 0.8})]
        result = build_noise_floor_result(runs, retrieval_mode="sparse")
        assert result.retrieval_mode == "sparse"

    def test_empty_runs_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            build_noise_floor_result([], retrieval_mode="dense")

    def test_metric_stats_propagated(self):
        runs = [_run({"nDCG@10": 0.68}), _run({"nDCG@10": 0.72})]
        result = build_noise_floor_result(runs, retrieval_mode="dense")
        assert "nDCG@10" in result.metric_stats
        assert result.metric_stats["nDCG@10"].mean == pytest.approx(0.70)

    def test_serializable_to_json(self):
        runs = [_run({"nDCG@10": 0.68})]
        result = build_noise_floor_result(runs, retrieval_mode="dense")
        data = result.model_dump(mode="json")
        assert isinstance(data["metric_stats"]["nDCG@10"]["mean"], float)
