"""`citation_precision` and what has to be read next to it (C-03).

ROADMAP §0 claim 1: *sentence-level verified attribution is measurable, and small
models without verification get it systematically wrong.*  This module is the
measurement.

**The unit is the (claim, cited chunk) pair.**  ROADMAP §8 words C-03 as
"entailment affermazione ↔ chunk citato", one pair at a time, so a sentence
citing three chunks contributes three pairs.  That is deliberately stricter than
scoring the union of a sentence's citations: a model that pads a correct
citation with two irrelevant ones is doing the thing this project exists to
catch, and a union-based score would give it full marks.

**Three numbers, and none of them is readable alone:**

    citation_precision  of the pairs produced, how many are entailed
    citation_recall     of the verifiable claims, how many have any support
    uncited_claim_rate  of the verifiable claims, how many cite nothing at all

Precision alone is trivially gamed by citing less — one confident citation and
nothing else scores 1.0.  `uncited_claim_rate` is what stops that reading, which
is why it is computed here and not left to the caller.

Everything is reported per `dataset_id` (§14).  C-01 and C-02 both found the
failure mode to be genre-dependent, and the verifier itself was measured at
AUC 0.939 on one corpus and 0.910 on the other — an average over the two would
be a number about neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.generation.claims import Claim, citation_pairs, split_claims
from src.generation.entailment import Verdict


@dataclass(frozen=True)
class PairVerdict:
    """One (claim, cited chunk) judgement, kept for the failure report.

    The scores are stored rather than only the booleans: a run whose
    unsupported pairs sit at 0.49 says something different from one where they
    sit at 0.01, and that difference is invisible after thresholding.
    """

    claim: str
    chunk_id: str
    marker: int
    supported: bool
    score: float
    n_premises: int


@dataclass(frozen=True)
class CitationReport:
    """Everything C-03 measures for one answer set."""

    n_answers: int
    n_claims: int
    n_verifiable: int
    n_uncited: int
    n_pairs: int
    n_supported: int
    n_claims_supported: int
    n_windowed: int
    verdicts: list[PairVerdict] = field(default_factory=list)

    @property
    def citation_precision(self) -> float:
        """Share of produced citations that the cited chunk actually entails."""
        return self.n_supported / self.n_pairs if self.n_pairs else 0.0

    @property
    def citation_recall(self) -> float:
        """Share of verifiable claims with at least one entailing citation."""
        return self.n_claims_supported / self.n_verifiable if self.n_verifiable else 0.0

    @property
    def uncited_claim_rate(self) -> float:
        """Share of verifiable claims carrying no citation at all.

        Reported beside precision because precision is raised by citing less.
        """
        return self.n_uncited / self.n_verifiable if self.n_verifiable else 0.0

    @property
    def windowed_rate(self) -> float:
        """Share of pairs whose premise had to be split.

        The artefact the model choice exists to avoid: a max over N windows
        inflates with N.  Expected near zero — if a run reports otherwise, its
        precision is partly a measure of chunk length.
        """
        return self.n_windowed / self.n_pairs if self.n_pairs else 0.0


def verify_answer(
    answer: str,
    chunks: list[dict],
    verifier=None,
) -> tuple[list[Claim], list[PairVerdict]]:
    """Verify every (claim, cited chunk) pair of one answer.

    Args:
        answer: the generated text, **after** `citations.parse` — markers must be
            canonical and in range before they can be read as a citation set.
        chunks: the context in marker order, so `[n]` is `chunks[n - 1]`.  Each
            needs `chunk_id` and `text`.
        verifier: callable (chunk_text, claim) -> Verdict.  Injected so the
            metric can be tested, and re-scored later without regenerating.

    Returns:
        (claims, verdicts) — the claims include the uncited ones, which produce
        no verdicts but belong to the denominator of recall.
    """
    if verifier is None:
        from src.generation.entailment import verify as verifier  # noqa: N813

    claims = split_claims(answer, n_chunks=len(chunks))
    out: list[PairVerdict] = []
    for claim, marker in citation_pairs(claims):
        chunk = chunks[marker - 1]
        v: Verdict = verifier(chunk["text"], claim.text)
        out.append(PairVerdict(
            claim=claim.text,
            chunk_id=chunk["chunk_id"],
            marker=marker,
            supported=v.supported,
            score=v.score,
            n_premises=v.n_premises,
        ))
    return claims, out


def summarize(per_answer: list[tuple[list[Claim], list[PairVerdict]]]) -> CitationReport:
    """Aggregate per-answer results into the C-03 numbers."""
    n_claims = n_verifiable = n_uncited = n_claims_supported = 0
    verdicts: list[PairVerdict] = []

    for claims, pair_verdicts in per_answer:
        n_claims += len(claims)
        verifiable = [c for c in claims if c.is_verifiable]
        n_verifiable += len(verifiable)
        n_uncited += sum(1 for c in verifiable if not c.is_cited)
        supported_claims = {v.claim for v in pair_verdicts if v.supported}
        n_claims_supported += sum(1 for c in verifiable if c.text in supported_claims)
        verdicts.extend(pair_verdicts)

    return CitationReport(
        n_answers=len(per_answer),
        n_claims=n_claims,
        n_verifiable=n_verifiable,
        n_uncited=n_uncited,
        n_pairs=len(verdicts),
        n_supported=sum(1 for v in verdicts if v.supported),
        n_claims_supported=n_claims_supported,
        n_windowed=sum(1 for v in verdicts if v.n_premises > 1),
        verdicts=verdicts,
    )


def build_metrics(report: CitationReport) -> dict[str, float]:
    """Flatten into the EvalRun metrics dict.

    `citation_precision` is the C-03 criterion.  The other four are not
    decoration: each one is a way the headline number can be true and
    misleading at the same time, so they travel with it.
    """
    return {
        "citation_precision": report.citation_precision,
        "citation_recall": report.citation_recall,
        "uncited_claim_rate": report.uncited_claim_rate,
        "windowed_premise_rate": report.windowed_rate,
        "citations_per_answer": (
            report.n_pairs / report.n_answers if report.n_answers else 0.0
        ),
        "claims_per_answer": (
            report.n_claims / report.n_answers if report.n_answers else 0.0
        ),
    }
