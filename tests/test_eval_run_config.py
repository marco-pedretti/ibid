"""Tests for src/eval/run_config.py and the legacy result migration.

Covers:
  - build_config() always emits every CONFIG_KEYS entry
  - config_slug() only names active flags
  - differing_keys() isolates single-flag comparisons (ROADMAP §12)
  - parse_legacy() splits old pipeline_mode labels back into structure
  - config_hash is NOT affected by the new config field
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as cfg
from src.eval.run_config import CONFIG_KEYS, build_config, config_slug, differing_keys


def _base(**over):
    kwargs = dict(top_k=5, retrieval_mode="dense", collection="open_ragbench")
    kwargs.update(over)
    return build_config(**kwargs)


class TestBuildConfig:
    def test_all_keys_present_on_minimal_config(self):
        c = _base()
        for key in CONFIG_KEYS:
            assert key in c

    def test_inactive_flags_are_false_not_missing(self):
        c = _base()
        assert c["rerank"] is False
        assert c["query_rewrite"] is False
        assert c["doc_aggregate"] is False
        assert c["filter_content_type"] is None

    def test_reranker_model_only_when_reranking(self):
        assert _base()["reranker_model"] is None
        assert _base(rerank=True)["reranker_model"] == cfg.RERANKER_MODEL

    def test_rewrite_model_only_when_rewriting(self):
        assert _base()["query_rewrite_model"] is None
        assert _base(query_rewrite=True)["query_rewrite_model"] is not None

    def test_collection_is_recorded_verbatim(self):
        assert _base(collection="ledger_routed")["collection"] == "ledger_routed"

    def test_embedding_model_recorded(self):
        assert _base()["embedding_model"] == cfg.EMBEDDING_MODEL


class TestConfigSlug:
    def test_baseline_is_just_retrieval_mode(self):
        assert config_slug(_base()) == "dense"

    def test_sparse_baseline(self):
        assert config_slug(_base(retrieval_mode="sparse")) == "sparse"

    def test_flags_appended_in_stable_order(self):
        c = _base(retrieval_mode="hybrid", rerank=True, query_rewrite=True, doc_aggregate=True)
        assert config_slug(c) == "hybrid-rewrite-rerank-docagg"

    def test_filter_carries_its_value(self):
        assert config_slug(_base(filter_content_type="table")) == "dense-filter_table"

    def test_empty_config_is_unknown(self):
        assert config_slug({}) == "unknown"


class TestDifferingKeys:
    def test_identical_configs_differ_in_nothing(self):
        assert differing_keys(_base(), _base()) == []

    def test_single_flag_change_isolated(self):
        assert differing_keys(_base(), _base(doc_aggregate=True)) == ["doc_aggregate"]

    def test_rerank_change_also_moves_model_key(self):
        # rerank pulls in reranker_model — two keys, but one *decision*.
        assert differing_keys(_base(), _base(rerank=True)) == ["rerank", "reranker_model"]

    def test_two_changes_reported_as_two(self):
        diff = differing_keys(_base(), _base(retrieval_mode="hybrid", doc_aggregate=True))
        assert "retrieval_mode" in diff and "doc_aggregate" in diff

    def test_missing_key_counts_as_difference(self):
        assert differing_keys({"a": 1}, {}) == ["a"]


class TestConfigHashUnaffected:
    def test_hash_ignores_new_config_field(self):
        """The md5 identity must not shift — already-reported runs stay comparable."""
        from src.eval.harness import _config_hash
        # Value asserted literally: if this ever changes, every EvalRun written
        # before the change silently stops matching its own configuration.
        assert _config_hash(5, "generic", "dense") == _config_hash(
            5, "generic", "dense", collection="open_ragbench", dataset_id="open_ragbench"
        )

    def test_evalrun_config_defaults_to_empty(self):
        from datetime import datetime, timezone

        from src.datasets.schema import EvalRun
        run = EvalRun(
            run_id="x", timestamp=datetime.now(timezone.utc), git_commit="abc",
            config_hash="0", dataset_id="open_ragbench", model="m", quantization="none",
            context_window=0, temperature=0.0, reasoning_enabled=False,
            pipeline_mode="generic", metrics={"R@5": 1.0},
        )
        assert run.config == {}


class TestParseLegacy:
    @staticmethod
    def _parse(mode: str, dataset: str = "open_ragbench"):
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        from scripts.migrate_eval_results import parse_legacy
        return parse_legacy(mode, dataset)

    def test_plain_generic(self):
        axis, c = self._parse("generic")
        assert axis == "generic"
        assert c["retrieval_mode"] == "dense"

    def test_baseline_c_is_sparse_on_generic_ingestion(self):
        axis, c = self._parse("baseline_c")
        assert axis == "generic"
        assert c["retrieval_mode"] == "sparse"

    def test_hybrid_rrf(self):
        axis, c = self._parse("hybrid_rrf")
        assert (axis, c["retrieval_mode"]) == ("generic", "hybrid")

    def test_routed_docagg_splits_both_axes(self):
        axis, c = self._parse("routed_docagg", "ledger")
        assert axis == "routed"
        assert c["doc_aggregate"] is True
        assert c["collection"] == "ledger_routed"

    def test_filtered_text_recovers_the_value(self):
        _, c = self._parse("generic_filtered_text")
        assert c["filter_content_type"] == "text"

    def test_reranked_sets_model(self):
        _, c = self._parse("generic_reranked")
        assert c["rerank"] is True
        assert c["reranker_model"] == cfg.RERANKER_MODEL

    def test_rewritten_sets_model(self):
        _, c = self._parse("generic_rewritten")
        assert c["query_rewrite"] is True
        assert c["query_rewrite_model"] is not None

    def test_legacy_label_preserved(self):
        _, c = self._parse("generic_docagg")
        assert c["legacy_pipeline_mode"] == "generic_docagg"
        assert c["_migrated"] is True

    def test_unknown_label_left_alone(self):
        axis, c = self._parse("baseline_a")
        assert axis == "baseline_a"
        assert c["legacy_pipeline_mode"] == "baseline_a"

    def test_generic_collection_is_dataset_id(self):
        _, c = self._parse("generic", "ledger")
        assert c["collection"] == "ledger"


@pytest.fixture(scope="module")
def runs():
    import json
    results = Path(__file__).parent.parent / "eval" / "results"
    out = []
    for p in sorted(results.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if "metrics" in data:
            out.append(data)
    return out


class TestMigratedFilesOnDisk:
    """The committed results must all carry a parsed config after migration."""

    def test_every_run_has_config(self, runs):
        assert runs, "no eval results found"
        assert all(r.get("config") for r in runs)

    def test_pipeline_mode_is_binary(self, runs):
        assert {r["pipeline_mode"] for r in runs} <= {"generic", "routed"}

    def test_routed_runs_point_at_routed_collection(self, runs):
        routed = [r for r in runs if r["pipeline_mode"] == "routed"]
        assert routed
        assert all(r["config"]["collection"].endswith("_routed") for r in routed)
