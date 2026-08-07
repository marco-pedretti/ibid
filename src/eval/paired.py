"""Paired significance test for two retrieval configurations.

Why this exists, and why it is not the E-07 noise floor.

E-07 measures dispersion by running the same configuration N times.  That is the
right instrument for *generation*, where the model samples and the same question
gets different answers.  For retrieval it measures nothing: the pipeline is
deterministic — ONNX embeddings, a fixed Qdrant index, no sampling — and five
runs give bit-identical results.  Measured 2026-08-07: σ = 0.000000 on every
metric, both datasets.

A σ of zero read carelessly says "every delta is significant".  It says no such
thing.  It says the *measurement* has no jitter; the uncertainty that remains is
sampling error over the golden query set, which E-07 cannot see.

The right instrument for "is config B better than config A" is a paired test on
the same queries.  Only the queries where the two disagree carry information —
the ones both get right, or both get wrong, say nothing about which is better.
That is McNemar's test, computed here exactly (binomial), not via the
chi-squared approximation, because the discordant counts are routinely small
(7 out of 200 in the R-07 comparison).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PairedResult:
    """Outcome of comparing two systems on the same queries."""

    n: int
    rate_a: float
    rate_b: float
    only_a: int  # queries A gets right and B does not
    only_b: int  # queries B gets right and A does not
    p_value: float

    @property
    def delta(self) -> float:
        return self.rate_b - self.rate_a

    @property
    def discordant(self) -> int:
        return self.only_a + self.only_b

    def verdict(self, alpha: float = 0.05) -> str:
        if self.discordant == 0:
            return "identici su ogni query"
        if self.p_value < alpha:
            winner = "B" if self.only_b > self.only_a else "A"
            return f"differenza reale (p={self.p_value:.4f}), vince {winner}"
        return (
            f"non distinguibile dal caso (p={self.p_value:.4f}, "
            f"{self.discordant} query discordanti su {self.n})"
        )


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value.

    Under the null the discordant pairs split 50/50, so the p-value is the
    two-sided binomial tail.  Exact rather than chi-squared: with a handful of
    discordant queries the approximation is not trustworthy, and a handful is
    the normal case here.
    """
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2 * tail / 2**n)


def compare_paired(hits_a: list[bool], hits_b: list[bool]) -> PairedResult:
    """Compare two systems' per-query outcomes on the same, identically ordered queries.

    Args:
        hits_a, hits_b: one boolean per query — did the system succeed on it.
            Same length, same order; a mismatch means the two runs did not see
            the same queries and the comparison is meaningless.

    Raises:
        ValueError: if the two lists differ in length.
    """
    if len(hits_a) != len(hits_b):
        raise ValueError(
            f"query non appaiate: {len(hits_a)} contro {len(hits_b)} — "
            "un confronto appaiato richiede le stesse query nello stesso ordine"
        )
    n = len(hits_a)
    if n == 0:
        return PairedResult(0, 0.0, 0.0, 0, 0, 1.0)

    only_a = sum(1 for a, b in zip(hits_a, hits_b) if a and not b)
    only_b = sum(1 for a, b in zip(hits_a, hits_b) if b and not a)
    return PairedResult(
        n=n,
        rate_a=sum(hits_a) / n,
        rate_b=sum(hits_b) / n,
        only_a=only_a,
        only_b=only_b,
        p_value=mcnemar_exact(only_a, only_b),
    )
