"""Tests for the noise-floor-aware comparator (dashboard-rework, point 2).

The behaviour under test is a ROADMAP §14 guard: the dashboard must not present
a delta as an improvement unless it clears the E-07 run-to-run dispersion, and
must say "not measured" rather than imply significance when no noise floor
exists for that dataset.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


from dashboard.eval_store import (
    config_diff,
    config_matrix,
    is_significant,
    load_eval_runs,
    load_noise_floors,
    match_noise_floor,
    noise_std,
    run_label,
    significance_label,
)
from src.datasets.schema import EvalRun
from src.eval.noise_floor import MetricStats, NoiseFloorResult


def _run(dataset="open_ragbench", pipeline_mode="generic", config=None, metrics=None,
         ts=None) -> EvalRun:
    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=ts or datetime.now(timezone.utc),
        git_commit="abc1234def",
        config_hash="deadbeef",
        dataset_id=dataset,
        model="retrieval_only",
        quantization="none",
        context_window=0,
        temperature=0.0,
        reasoning_enabled=False,
        pipeline_mode=pipeline_mode,
        config=config if config is not None else {"retrieval_mode": "dense", "top_k": 5},
        metrics=metrics or {"R@5": 0.8, "nDCG@10": 0.68},
    )


def _floor(dataset="open_ragbench", retrieval_mode="dense", std=0.01, ts=None,
           pipeline_mode="generic") -> NoiseFloorResult:
    return NoiseFloorResult(
        timestamp=ts or datetime.now(timezone.utc),
        git_commit="abc1234def",
        n_runs=5,
        dataset_id=dataset,
        pipeline_mode=pipeline_mode,
        retrieval_mode=retrieval_mode,
        metric_stats={
            "R@5": MetricStats(mean=0.8, std=std, min_val=0.79, max_val=0.81),
            "nDCG@10": MetricStats(mean=0.68, std=std, min_val=0.67, max_val=0.69),
        },
    )


# ---------------------------------------------------------------------------
# load_noise_floors — the files load_eval_runs deliberately skips
# ---------------------------------------------------------------------------

class TestLoadNoiseFloors:
    def test_loads_metric_stats_files(self, tmp_path: Path):
        (tmp_path / "nf.json").write_text(_floor().model_dump_json(), encoding="utf-8")
        assert len(load_noise_floors(tmp_path)) == 1

    def test_ignores_evalrun_files(self, tmp_path: Path):
        (tmp_path / "run.json").write_text(_run().model_dump_json(), encoding="utf-8")
        assert load_noise_floors(tmp_path) == []

    def test_evalrun_loader_still_ignores_noise_files(self, tmp_path: Path):
        (tmp_path / "nf.json").write_text(_floor().model_dump_json(), encoding="utf-8")
        assert load_eval_runs(tmp_path) == []

    def test_both_loaders_coexist_in_one_dir(self, tmp_path: Path):
        (tmp_path / "nf.json").write_text(_floor().model_dump_json(), encoding="utf-8")
        (tmp_path / "run.json").write_text(_run().model_dump_json(), encoding="utf-8")
        assert len(load_noise_floors(tmp_path)) == 1
        assert len(load_eval_runs(tmp_path)) == 1

    def test_malformed_file_skipped(self, tmp_path: Path):
        (tmp_path / "bad.json").write_text('{"metric_stats": "nope"}', encoding="utf-8")
        assert load_noise_floors(tmp_path) == []

    def test_sorted_newest_first(self, tmp_path: Path):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        (tmp_path / "a.json").write_text(_floor(ts=old).model_dump_json(), encoding="utf-8")
        (tmp_path / "b.json").write_text(_floor().model_dump_json(), encoding="utf-8")
        floors = load_noise_floors(tmp_path)
        assert floors[0].timestamp > floors[1].timestamp


# ---------------------------------------------------------------------------
# match_noise_floor — never across datasets
# ---------------------------------------------------------------------------

class TestMatchNoiseFloor:
    def test_no_floors_returns_none(self):
        assert match_noise_floor(_run(), []) is None

    def test_never_matches_across_datasets(self):
        """§13: dispersion measured on ledger says nothing about open_ragbench."""
        assert match_noise_floor(_run(dataset="open_ragbench"), [_floor(dataset="ledger")]) is None

    def test_prefers_same_retrieval_mode(self):
        sparse = _floor(retrieval_mode="sparse")
        dense = _floor(retrieval_mode="dense")
        run = _run(config={"retrieval_mode": "sparse"})
        assert match_noise_floor(run, [dense, sparse]) is sparse

    def test_falls_back_to_same_dataset(self):
        only = _floor(retrieval_mode="sparse")
        run = _run(config={"retrieval_mode": "hybrid"})
        assert match_noise_floor(run, [only]) is only

    def test_newest_wins_among_equals(self):
        old = _floor(ts=datetime.now(timezone.utc) - timedelta(days=1))
        new = _floor()
        assert match_noise_floor(_run(), [new, old]) is new

    def test_run_without_config_still_matches_dataset(self):
        floor = _floor()
        assert match_noise_floor(_run(config={}), [floor]) is floor


# ---------------------------------------------------------------------------
# noise_std / is_significant — "unknown" is not "not significant"
# ---------------------------------------------------------------------------

class TestSignificance:
    def test_std_none_when_no_floor(self):
        assert noise_std(None, "R@5") is None

    def test_std_none_for_unmeasured_metric(self):
        assert noise_std(_floor(), "doc_R@5") is None

    def test_std_read_from_floor(self):
        assert noise_std(_floor(std=0.02), "R@5") == 0.02

    def test_unmeasured_noise_is_unknown_not_false(self):
        assert is_significant(0.5, None) is None

    def test_delta_below_std_is_not_significant(self):
        assert is_significant(0.005, 0.01) is False

    def test_delta_above_std_is_significant(self):
        assert is_significant(0.05, 0.01) is True

    def test_negative_delta_uses_magnitude(self):
        assert is_significant(-0.05, 0.01) is True
        assert is_significant(-0.005, 0.01) is False

    def test_delta_exactly_at_std_is_not_significant(self):
        """Strictly greater — a delta equal to the noise is noise."""
        assert is_significant(0.01, 0.01) is False

    def test_label_says_unmeasured(self):
        assert "non misurato" in significance_label(0.5, None)

    def test_label_says_below_noise(self):
        assert "sotto rumore" in significance_label(0.005, 0.01)

    def test_label_says_significant(self):
        assert significance_label(0.05, 0.01).startswith("significativo")


# ---------------------------------------------------------------------------
# config_diff — ROADMAP §14 single-change attribution
# ---------------------------------------------------------------------------

class TestConfigDiff:
    def test_identical_runs(self):
        assert config_diff(_run(), _run()) == []

    def test_single_flag(self):
        a = _run(config={"retrieval_mode": "dense", "doc_aggregate": False})
        b = _run(config={"retrieval_mode": "dense", "doc_aggregate": True})
        assert config_diff(a, b) == ["doc_aggregate"]

    def test_routing_axis_counted_once_despite_collection(self):
        """generic->routed necessarily changes collection: one decision, not two."""
        a = _run(pipeline_mode="generic", config={"collection": "ledger"})
        b = _run(pipeline_mode="routed", config={"collection": "ledger_routed"})
        assert config_diff(a, b) == ["pipeline_mode"]

    def test_rerank_counted_once_despite_model_name(self):
        a = _run(config={"rerank": False, "reranker_model": None})
        b = _run(config={"rerank": True, "reranker_model": "BAAI/bge-reranker-v2-m3"})
        assert config_diff(a, b) == ["rerank"]

    def test_query_rewrite_counted_once(self):
        a = _run(config={"query_rewrite": False, "query_rewrite_model": None})
        b = _run(config={"query_rewrite": True, "query_rewrite_model": "gemma"})
        assert config_diff(a, b) == ["query_rewrite"]

    def test_two_real_changes_reported_as_two(self):
        a = _run(config={"retrieval_mode": "dense", "doc_aggregate": False})
        b = _run(config={"retrieval_mode": "hybrid", "doc_aggregate": True})
        assert len(config_diff(a, b)) == 2

    def test_r07_pair_is_a_single_change(self):
        """The actual R-07 comparison must read as one decision."""
        base = {"retrieval_mode": "dense", "top_k": 5, "rerank": False,
                "doc_aggregate": True}
        a = _run(pipeline_mode="generic", config={**base, "collection": "ledger"})
        b = _run(pipeline_mode="routed", config={**base, "collection": "ledger_routed"})
        assert config_diff(a, b) == ["pipeline_mode"]


# ---------------------------------------------------------------------------
# config_matrix — only the axes actually under comparison
# ---------------------------------------------------------------------------

class TestConfigMatrix:
    def test_identical_configs_show_only_pipeline_mode(self):
        m = config_matrix([_run(), _run()])
        assert list(m) == ["pipeline_mode"]

    def test_differing_key_appears(self):
        a = _run(config={"retrieval_mode": "dense"})
        b = _run(config={"retrieval_mode": "hybrid"})
        assert "retrieval_mode" in config_matrix([a, b])

    def test_shared_key_hidden(self):
        a = _run(config={"retrieval_mode": "dense", "top_k": 5})
        b = _run(config={"retrieval_mode": "hybrid", "top_k": 5})
        assert "top_k" not in config_matrix([a, b])

    def test_private_and_legacy_keys_hidden(self):
        a = _run(config={"_migrated": True, "legacy_pipeline_mode": "generic_docagg"})
        b = _run(config={"_migrated": False, "legacy_pipeline_mode": "routed_docagg"})
        m = config_matrix([a, b])
        assert "_migrated" not in m and "legacy_pipeline_mode" not in m

    def test_row_length_matches_run_count(self):
        m = config_matrix([_run(), _run(), _run()])
        assert all(len(v) == 3 for v in m.values())

    def test_none_vs_value_counts_as_differing(self):
        a = _run(config={"filter_content_type": None})
        b = _run(config={"filter_content_type": "text"})
        assert "filter_content_type" in config_matrix([a, b])


# ---------------------------------------------------------------------------
# run_label — two configs must not collapse to the same string
# ---------------------------------------------------------------------------

class TestRunLabel:
    def test_includes_config_slug(self):
        run = _run(config={"retrieval_mode": "hybrid", "rerank": True})
        assert "hybrid-rerank" in run_label(run)

    def test_distinguishes_runs_that_used_to_collide(self):
        """Both were labelled "generic" before EvalRun.config existed."""
        a = _run(config={"retrieval_mode": "dense", "doc_aggregate": False})
        b = _run(config={"retrieval_mode": "dense", "doc_aggregate": True})
        assert run_label(a) != run_label(b)

    def test_dataset_omitted_when_requested(self):
        assert "open_ragbench" not in run_label(_run(), include_dataset=False)

    def test_dataset_present_by_default(self):
        assert "open_ragbench" in run_label(_run())


# ---------------------------------------------------------------------------
# Comparison-table helpers (leggibilità: niente valori troncati)
# ---------------------------------------------------------------------------

class TestShortRunLabel:
    def test_is_indexed(self):
        from dashboard.eval_store import short_run_label
        assert short_run_label(_run(), 3).startswith("#3 ")

    def test_carries_pipeline_and_slug(self):
        from dashboard.eval_store import short_run_label
        run = _run(pipeline_mode="routed",
                   config={"retrieval_mode": "dense", "doc_aggregate": True})
        assert short_run_label(run, 1) == "#1 routed·dense-docagg"

    def test_shorter_than_full_label(self):
        """Full labels were long enough that Streamlit clipped the headers."""
        from dashboard.eval_store import run_label, short_run_label
        run = _run()
        assert len(short_run_label(run, 1)) < len(run_label(run))

    def test_distinct_for_distinct_configs(self):
        from dashboard.eval_store import short_run_label
        a = _run(config={"retrieval_mode": "dense"})
        b = _run(config={"retrieval_mode": "hybrid"})
        assert short_run_label(a, 1) != short_run_label(b, 2)


class TestActiveFlags:
    def test_none_active(self):
        from dashboard.eval_store import active_flags
        assert active_flags({"rerank": False}) == "—"

    def test_lists_active(self):
        from dashboard.eval_store import active_flags
        assert active_flags({"rerank": True, "doc_aggregate": True}) == "rerank, doc_aggregate"

    def test_filter_carries_value(self):
        from dashboard.eval_store import active_flags
        assert active_flags({"filter_content_type": "table"}) == "filter=table"

    def test_empty_config(self):
        from dashboard.eval_store import active_flags
        assert active_flags({}) == "—"


class TestRunRows:
    def test_one_row_per_run(self):
        from dashboard.eval_store import run_rows
        assert len(run_rows([_run(), _run(), _run()])) == 3

    def test_collection_not_truncated(self):
        """The clipped value that motivated the table: 'ledg…' told you nothing."""
        from dashboard.eval_store import run_rows
        run = _run(config={"collection": "ledger_routed"})
        assert run_rows([run])[0]["collection"] == "ledger_routed"

    def test_rows_are_numbered_to_match_short_label(self):
        from dashboard.eval_store import run_rows, short_run_label
        runs = [_run(), _run()]
        rows = run_rows(runs)
        assert rows[1]["#"] == "#2"
        assert short_run_label(runs[1], 2).startswith("#2")

    def test_missing_config_degrades_to_dash(self):
        from dashboard.eval_store import run_rows
        assert run_rows([_run(config={})])[0]["retrieval"] == "—"

    def test_commit_is_shortened(self):
        from dashboard.eval_store import run_rows
        assert len(run_rows([_run()])[0]["commit"]) == 7
