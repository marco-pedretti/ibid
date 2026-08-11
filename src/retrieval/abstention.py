"""Abstain before generating, on the retrieval scores alone (C-04).

ROADMAP §14: *l'astensione e il formato citazione sono decisi in codice, mai
lasciati al modello.*  This is that decision for abstention.

**What this is not.**  It is not a fix for a model that answers when it should
not.  Measured on E-02 (35 unanswerable queries per dataset, `gemma4:latest`,
T=0): the model already abstains **35/35 on both datasets**.  A gate cannot
improve a rate that is already 100%, and it can only lower it by refusing
questions the model would have answered.

**So why gate at all.**  Three reasons, none of which is the metric:

1. *A guarantee is not an observation.*  35/35 describes one model at one
   temperature under one prompt.  C-06 runs the same system on E2B, E4B and 12B,
   and a smaller model's willingness to say "I don't know" is exactly the kind of
   thing that degrades with size.  A threshold on retrieval scores does not care
   which model comes after it.
2. *Cost.*  On E-02 the LLM spent 11.5 s per open_ragbench query to conclude it
   had nothing to say.  A gate that never makes the call spends none of it.
3. *Auditability.*  A number in `config.py` is a stated policy that can be
   reviewed and changed; a model's inclination to abstain is neither.

**The policy is a budget, not a threshold.**  What a human chooses is how many
answerable questions may be refused — `ABSTENTION_BUDGET`.  The threshold is
then *derived from data* by `scripts/calibrate_abstention.py`, which is what
makes this "decided by code" rather than a number somebody liked.

**Calibration never sees an unanswerable query.**  The threshold is the budget-th
percentile of top-1 scores over *answerable* queries only, so the correct
abstention rate reported on E-02 is measured out of sample.  Tuning on the set
you report is how a metric gets inflated by construction — see `docs/progress.md`
C-03 §8 for the same trap in a different task.

**A threshold belongs to a (collection, retrieval mode) pair.**  Dense cosine
scores sit around 0.8; RRF fusion scores sit around 0.02.  Applying one to the
other silently abstains on everything or on nothing, so an uncalibrated pair
returns None and the caller records that the gate did not run.
"""

from __future__ import annotations

from dataclasses import dataclass

import src.config as cfg


@dataclass(frozen=True)
class AbstentionDecision:
    """Why the gate did or did not fire, kept for the EvalRun.

    `active` is False when no threshold exists for this (collection, mode).
    That is different from "the scores were high enough", and a result that
    cannot tell the two apart cannot be compared with one where the gate ran.
    """

    abstain: bool
    active: bool
    score: float
    threshold: float | None

    @property
    def margin(self) -> float | None:
        """How far the query sat from the decision, for the failure report."""
        return None if self.threshold is None else self.score - self.threshold


def threshold_for(collection: str, retrieval_mode: str) -> float | None:
    """Calibrated threshold, or None when this pair was never calibrated."""
    if retrieval_mode != cfg.ABSTENTION_CALIBRATED_MODE:
        return None
    return cfg.ABSTENTION_THRESHOLDS.get(collection)


def decide(
    scores: list[float],
    collection: str,
    retrieval_mode: str = "dense",
) -> AbstentionDecision:
    """Abstain when the best retrieved chunk is below the calibrated threshold.

    Top-1 rather than the mean of top-k: measured on both datasets, top-1
    separated answerable from unanswerable at least as well (AUC 0.972 vs 0.954
    on open_ragbench) and it is the score of the chunk the answer would actually
    be built on.  A mean over five chunks dilutes one good hit with four fillers,
    which is the case the gate most needs to let through.
    """
    top1 = scores[0] if scores else 0.0
    thr = threshold_for(collection, retrieval_mode)
    if thr is None:
        return AbstentionDecision(abstain=False, active=False, score=top1, threshold=None)
    return AbstentionDecision(abstain=top1 < thr, active=True, score=top1, threshold=thr)
