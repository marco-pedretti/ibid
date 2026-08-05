"""Pure data helpers for the Streamlit dashboard.

Separated from app.py so they can be unit-tested without importing Streamlit.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from src.datasets.schema import EvalRun


def load_eval_runs(results_dir: Path) -> list[EvalRun]:
    """Load all EvalRun JSON files from results_dir, sorted newest-first.

    Noise-floor files (no 'metrics' key) and malformed files are silently skipped.
    """
    runs: list[EvalRun] = []
    for f in results_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "metrics" not in data:
                continue
            runs.append(EvalRun.model_validate(data))
        except Exception:
            continue
    runs.sort(key=lambda r: r.timestamp, reverse=True)
    return runs


def run_label(run: EvalRun) -> str:
    """Short display label for multiselect and chart legends."""
    ts = run.timestamp.strftime("%m-%d %H:%M")
    return f"{run.dataset_id} · {run.pipeline_mode} · {run.git_commit[:7]}  [{ts}]"


def compare_table(runs: list[EvalRun]) -> dict[str, list[float]]:
    """Build comparison dict: {metric: [value_run0, value_run1, ...]}.

    Missing metrics for a run are represented as float('nan').
    Metrics are returned in sorted order.
    """
    all_metrics: set[str] = set()
    for run in runs:
        all_metrics.update(run.metrics.keys())

    table: dict[str, list[Any]] = {}
    for metric in sorted(all_metrics):
        table[metric] = [run.metrics.get(metric, math.nan) for run in runs]
    return table
