"""Pure data helpers for the Streamlit dashboard.

Separated from app.py so they can be unit-tested without importing Streamlit.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from src.datasets.schema import EvalRun
from src.eval.noise_floor import NoiseFloorResult
from src.eval.run_config import config_slug, differing_keys


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


def load_noise_floors(results_dir: Path) -> list[NoiseFloorResult]:
    """Load all E-07 noise-floor JSONs from results_dir, newest-first.

    These are the files `load_eval_runs` skips: they carry `metric_stats`
    (mean/std/min/max per metric) instead of a single `metrics` dict.  Without
    them the dashboard cannot tell a real improvement from run-to-run jitter,
    which ROADMAP §14 requires before any delta is called an improvement.
    """
    floors: list[NoiseFloorResult] = []
    for f in results_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "metric_stats" not in data:
                continue
            floors.append(NoiseFloorResult.model_validate(data))
        except Exception:
            continue
    floors.sort(key=lambda r: r.timestamp, reverse=True)
    return floors


def match_noise_floor(
    run: EvalRun, floors: list[NoiseFloorResult]
) -> NoiseFloorResult | None:
    """Find the most relevant noise floor for a run.

    Matching is deliberately loose: dataset_id must agree (never compare
    dispersion across genres), retrieval_mode is preferred, and among the
    candidates the newest wins.  Returns None when nothing matches — the caller
    must then say "not measured" rather than imply significance.
    """
    same_dataset = [f for f in floors if f.dataset_id == run.dataset_id]
    if not same_dataset:
        return None
    mode = run.config.get("retrieval_mode")
    if mode:
        exact = [f for f in same_dataset if f.retrieval_mode == mode]
        if exact:
            return exact[0]
    return same_dataset[0]


def noise_std(floor: NoiseFloorResult | None, metric: str) -> float | None:
    """Std of `metric` in `floor`, or None when unmeasured."""
    if floor is None:
        return None
    stats = floor.metric_stats.get(metric)
    return stats.std if stats else None


def is_significant(delta: float, std: float | None) -> bool | None:
    """Is `delta` larger than run-to-run noise?

    Returns None when the noise floor for that metric was never measured — an
    honest "unknown", distinct from False.
    """
    if std is None:
        return None
    return abs(delta) > std


def significance_label(delta: float, std: float | None) -> str:
    """Short verdict string for the delta table."""
    verdict = is_significant(delta, std)
    if verdict is None:
        return "rumore non misurato"
    if not verdict:
        return f"sotto rumore (σ={std:.4f})"
    return f"significativo (σ={std:.4f})"


def run_label(run: EvalRun, include_dataset: bool = True) -> str:
    """Short display label for multiselect and chart legends.

    Includes the config slug: two runs of the same dataset and pipeline_mode are
    otherwise indistinguishable, which is how "generic_docagg" vs "generic"
    used to get confused in the comparator.
    """
    ts = run.timestamp.strftime("%m-%d %H:%M")
    slug = config_slug(run.config)
    head = f"{run.dataset_id} · " if include_dataset else ""
    return f"{head}{run.pipeline_mode} · {slug} · {run.git_commit[:7]}  [{ts}]"


def short_run_label(run: EvalRun, index: int) -> str:
    """Compact label for chart legends and table headers: "#1 routed·dense-docagg".

    The full identity (commit, timestamp, config hash) is shown once in the run
    table instead of being repeated in every column header, where it was long
    enough to force Streamlit to truncate mid-word.
    """
    return f"#{index} {run.pipeline_mode}·{config_slug(run.config)}"


def active_flags(config: dict[str, Any]) -> str:
    """Human list of the retrieval flags that are on, or "—" when none are."""
    active = [k for k in ("rerank", "query_rewrite", "doc_aggregate") if config.get(k)]
    if config.get("filter_content_type"):
        active.append(f"filter={config['filter_content_type']}")
    return ", ".join(active) if active else "—"


def run_rows(runs: list[EvalRun]) -> list[dict[str, Any]]:
    """One row per run for the comparison table.

    Rows rather than columns: with five runs side by side every value
    ("retrieval_only", a commit sha, "ledger_routed") was being clipped to
    "retri…", and a clipped collection name is exactly the thing you are trying
    to read in a routing ablation.
    """
    rows = []
    for i, run in enumerate(runs, 1):
        rows.append({
            "#": f"#{i}",
            "pipeline_mode": run.pipeline_mode,
            "retrieval": run.config.get("retrieval_mode", "—"),
            "collection": run.config.get("collection", "—"),
            "top_k": run.config.get("top_k", "—"),
            "flag attivi": active_flags(run.config),
            "commit": run.git_commit[:7],
            "config_hash": run.config_hash,
            "quando": run.timestamp.strftime("%d %b %H:%M"),
        })
    return rows


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


def config_diff(a: EvalRun, b: EvalRun) -> list[str]:
    """What changed between two runs, including the routing axis.

    ROADMAP §14 forbids measuring two changes at once.  The comparator uses this
    to warn when a delta cannot be attributed to a single decision.
    """
    diff = differing_keys(a.config, b.config)
    if a.pipeline_mode != b.pipeline_mode:
        diff = ["pipeline_mode", *diff]
    # A routed run necessarily queries a different collection — that is the same
    # decision, not a second one.
    if "pipeline_mode" in diff and "collection" in diff:
        diff.remove("collection")
    # Same for rerank/query_rewrite and the model name they imply.
    for flag, implied in (("rerank", "reranker_model"),
                          ("query_rewrite", "query_rewrite_model")):
        if flag in diff and implied in diff:
            diff.remove(implied)
    return diff


def config_matrix(runs: list[EvalRun]) -> dict[str, list[Any]]:
    """Flag matrix across runs: {config_key: [value_run0, ...]}.

    Only keys that differ somewhere are returned, so the table shows the axes
    actually under comparison instead of ten identical rows.
    """
    keys: set[str] = set()
    for r in runs:
        keys.update(k for k in r.config if not k.startswith("_") and k != "legacy_pipeline_mode")

    matrix: dict[str, list[Any]] = {"pipeline_mode": [r.pipeline_mode for r in runs]}
    for key in sorted(keys):
        values = [r.config.get(key) for r in runs]
        if len(set(map(repr, values))) > 1:
            matrix[key] = values
    return matrix
