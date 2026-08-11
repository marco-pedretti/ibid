"""C-04 — the abstention gate: when it fires, and when it refuses to have an opinion.

The gate's job is a guarantee, not a metric: on E-02 the model already abstains
35/35 on both datasets, so a threshold cannot raise that rate and can only lower
it by refusing answerable questions. These tests therefore care most about the
ways it could fire when it should not — a wrong-scale threshold, a missing
calibration silently treated as zero, an empty candidate list.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as cfg
from src.retrieval.abstention import AbstentionDecision, decide, threshold_for

COLL = "open_ragbench"
THR = cfg.ABSTENTION_THRESHOLDS[COLL]


class TestDecide:
    def test_abstains_below_the_threshold(self):
        d = decide([THR - 0.05, 0.7, 0.7], COLL, "dense")
        assert d.abstain and d.active

    def test_answers_above_the_threshold(self):
        d = decide([THR + 0.05, 0.7, 0.7], COLL, "dense")
        assert not d.abstain and d.active

    def test_threshold_is_exclusive_at_the_boundary(self):
        # Equal to the threshold is not below it: the budget is a percentile of
        # answerable scores, so the boundary case belongs to the answered side.
        assert not decide([THR], COLL, "dense").abstain

    def test_only_the_top_score_decides(self):
        """Top-1, not the mean: a mean over five chunks dilutes one good hit
        with four fillers, which is the case the gate most needs to pass."""
        d = decide([THR + 0.05, 0.1, 0.1, 0.1, 0.1], COLL, "dense")
        assert not d.abstain

    def test_margin_reports_the_distance(self):
        d = decide([THR + 0.02], COLL, "dense")
        assert d.margin == pytest.approx(0.02)


class TestUncalibrated:
    def test_unknown_collection_does_not_gate(self):
        d = decide([0.1], "una_collezione_mai_calibrata", "dense")
        assert not d.abstain and not d.active and d.threshold is None

    def test_other_retrieval_mode_does_not_gate(self):
        """Dense cosine sits around 0.8 and RRF fusion around 0.02. Applying one
        threshold to the other abstains on everything or on nothing, so an
        uncalibrated mode has no opinion instead of a wrong one."""
        d = decide([0.02], COLL, "hybrid")
        assert not d.abstain and not d.active

    def test_inactive_is_distinguishable_from_confident(self):
        """A result that cannot tell "the gate did not run" from "the scores
        were high enough" cannot be compared with one where the gate ran."""
        off = decide([0.1], COLL, "hybrid")
        on = decide([THR + 0.1], COLL, "dense")
        assert off.abstain == on.abstain
        assert off.active != on.active


class TestThresholdLookup:
    def test_returns_the_configured_value(self):
        assert threshold_for(COLL, "dense") == THR

    def test_none_for_an_uncalibrated_mode(self):
        assert threshold_for(COLL, "sparse") is None

    def test_none_for_an_uncalibrated_collection(self):
        assert threshold_for("mistero", "dense") is None

    def test_every_configured_collection_has_a_plausible_dense_score(self):
        """A cosine threshold outside [0,1] means the config was pasted from a
        calibration in another retrieval mode."""
        for name, value in cfg.ABSTENTION_THRESHOLDS.items():
            assert 0.0 < value < 1.0, name


class TestEdges:
    def test_no_candidates_abstains_when_calibrated(self):
        assert decide([], COLL, "dense").abstain

    def test_no_candidates_does_not_abstain_when_uncalibrated(self):
        assert not decide([], COLL, "hybrid").abstain


class TestPolicy:
    def test_budget_is_small_on_purpose(self):
        """The gate cannot improve the E-02 rate — the model is already at
        35/35 — so it exists as a guarantee for models that will not, and a
        guarantee should cost as little as possible."""
        assert cfg.ABSTENTION_BUDGET <= 0.02

    def test_thresholds_sit_below_the_answerable_median(self):
        # Measured medians: 0.8605 open_ragbench, 0.8652 ledger.
        for value in cfg.ABSTENTION_THRESHOLDS.values():
            assert value < 0.86

    def test_a_changed_budget_does_not_silently_move_the_thresholds(self):
        """They are derived by scripts/calibrate_abstention.py, not computed at
        import time: changing the budget alone must not shift the gate under a
        run that is already comparing results."""
        with patch.object(cfg, "ABSTENTION_BUDGET", 0.25):
            assert threshold_for(COLL, "dense") == THR


class TestDecisionShape:
    def test_carries_score_and_threshold(self):
        d = AbstentionDecision(abstain=True, active=True, score=0.5, threshold=0.7)
        assert d.margin == pytest.approx(-0.2)

    def test_margin_is_none_without_a_threshold(self):
        assert AbstentionDecision(False, False, 0.5, None).margin is None


class TestNoLeakageBetweenSplits:
    """The calibration set, its holdout and the evaluation set must not overlap.

    Three scripts derive their slices from the same shuffle with the same seed:
    `calibrate_abstention.py` takes [0:150] and [150:300], `eval_abstention.py`
    takes [300:...]. The arrangement is only correct as long as all three agree
    on the seed and the reserved size, and nothing in the code enforces that
    agreement — a changed seed would silently measure the false-abstention rate
    on the queries that set the threshold, which is not a measurement.
    """

    def _slices(self, dataset: str):
        import json
        import random

        rows = [json.loads(x) for x in
                (Path(__file__).parent.parent / "eval" / "golden" / f"{dataset}.jsonl")
                .read_text(encoding="utf-8").splitlines() if x.strip()]
        answerable = [r for r in rows if r.get("answerable") is not False]
        random.Random(1).shuffle(answerable)
        ids = [r["query_id"] for r in answerable]
        return set(ids[:150]), set(ids[150:300]), set(ids[300:360])

    @pytest.mark.parametrize("dataset", ["open_ragbench", "ledger"])
    def test_splits_are_disjoint(self, dataset):
        cal, holdout, evaluation = self._slices(dataset)
        assert not (cal & holdout)
        assert not (cal & evaluation)
        assert not (holdout & evaluation)

    def test_eval_starts_after_everything_calibration_uses(self):
        from scripts.eval_abstention import CALIBRATION_RESERVED

        assert CALIBRATION_RESERVED >= 300
