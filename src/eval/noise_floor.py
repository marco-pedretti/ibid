"""Noise floor measurement for E-07.

Runs the same evaluation N times and computes per-metric dispersion statistics.
No improvement smaller than the noise floor dispersion should ever be declared.

Design: compute_noise_floor() is pure statistics — it receives a list of EvalRun
objects already produced by the caller. The script handles actually running evals.
"""

from __future__ import annotations

import statistics
import subprocess
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from src.datasets.schema import EvalRun


class MetricStats(BaseModel):
    mean: float
    std: float       # population std (pstdev) — treats N runs as the full population
    min_val: float
    max_val: float


class NoiseFloorResult(BaseModel):
    timestamp: datetime
    git_commit: str
    n_runs: int
    dataset_id: str
    pipeline_mode: str
    retrieval_mode: str  # "dense" | "sparse" | "baseline_a" | "baseline_b"
    metric_stats: dict[str, MetricStats]


def compute_noise_floor(runs: list[EvalRun]) -> dict[str, MetricStats]:
    """Compute per-metric dispersion across N EvalRun objects.

    Args:
        runs: list of EvalRun produced by the same configuration.
              Must be non-empty; all runs should share the same metric keys.

    Returns:
        Dict mapping metric name to MetricStats (mean, std, min, max).

    Raises:
        ValueError: if runs is empty.
    """
    if not runs:
        raise ValueError("at least one run is required to compute noise floor")

    all_metrics: set[str] = set()
    for run in runs:
        all_metrics.update(run.metrics.keys())

    stats: dict[str, MetricStats] = {}
    for metric in sorted(all_metrics):
        values = [run.metrics.get(metric, 0.0) for run in runs]
        mean = statistics.mean(values)
        std = statistics.pstdev(values)
        stats[metric] = MetricStats(
            mean=mean,
            std=std,
            min_val=min(values),
            max_val=max(values),
        )
    return stats


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def build_noise_floor_result(
    runs: list[EvalRun],
    retrieval_mode: str,
) -> NoiseFloorResult:
    """Wrap compute_noise_floor() into a saveable NoiseFloorResult."""
    if not runs:
        raise ValueError("at least one run is required")
    first = runs[0]
    return NoiseFloorResult(
        timestamp=datetime.now(timezone.utc),
        git_commit=_git_commit(),
        n_runs=len(runs),
        dataset_id=first.dataset_id,
        pipeline_mode=first.pipeline_mode,
        retrieval_mode=retrieval_mode,
        metric_stats=compute_noise_floor(runs),
    )
