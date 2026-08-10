"""Does a generation respect the citation format of ROADMAP §3.2?  (C-01)

**This checks the raw model output, before `citations.normalize()` touches it.**

That is the whole point of the module.  C-01 asks whether the *prompt* obtains
the format; C-02 asks whether the *parser* can repair it when it does not.  If
compliance were measured after normalisation, every malformed variant the parser
already knows about would score as compliant, C-01 would report ~100% by
construction, and the number would say nothing about the prompt.  Any repair
applied before `check_format` invalidates its result.

§3.2 accepts exactly one form: contiguous `[n]` markers, one number per chunk,
pointing at a chunk present in context — `Il valore massimo è 400ms [2][3].`
Everything else is a violation, and each violation is classified so the failures
can be read as a list of prompt defects rather than one opaque rate.

Abstentions are excluded from the denominator, not counted as compliant.  An
answer with no citations because the context was insufficient is a correct
outcome with nothing to cite; scoring it as a format failure would make the rate
track the abstention rate.  Scoring it as compliant would let a model that
abstains on everything report perfect compliance.  `compliance_rate()` therefore
returns the rate over scored answers *and* the abstention count, and the caller
is expected to report both — one without the other is not interpretable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from src.generation.baseline_prompts import ABSTENTION_PHRASES

#: C-01 is accepted at ≥95% compliance.
COMPLIANCE_TARGET = 0.95

#: Every violation kind, in reporting order.  Exposed so callers can emit a
#: metric key per kind on every run, including the kinds that did not occur —
#: a missing key and a zero are different claims, and only one of them is true.
VIOLATION_KINDS: tuple[str, ...] = (
    "comma_list",
    "range",
    "conjunction",
    "dash_joined",
    "spaced_markers",
    "named_marker",
    "out_of_range",
    "no_citation",
)

# Each pattern matches a *malformed* citation construct in raw output.
# Order matters only for readability: a text can violate several at once, and
# all of them are reported.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # [1,2] / [1, 2, 3]
    ("comma_list", re.compile(r"\[\d+(?:\s*,\s*\d+)+\]")),
    # [1-3] / [1–3]
    ("range", re.compile(r"\[\d+\s*[-–—]\s*\d+\]")),
    # [1 e 2] / [1 and 2]
    ("conjunction", re.compile(r"\[\d+\s+(?:e|and|und|et)\s+\d+\]", re.IGNORECASE)),
    # [1]-[2] / [1] - [2]
    ("dash_joined", re.compile(r"\[\d+\]\s*[-–—]\s*\[\d+\]")),
    # [1] [2] — markers separated by whitespace instead of contiguous
    ("spaced_markers", re.compile(r"\[\d+\][ \t]+\[\d+\]")),
    # [Chunk 2] / [Source 2] / [Doc 2] / (Chunk 2) — a marker that carries a word
    ("named_marker", re.compile(
        r"[\[(]\s*(?:chunk|source|doc|document|fonte|ref|reference)\s*\.?\s*:?\s*\d+\s*[\])]",
        re.IGNORECASE,
    )),
)

_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class Violation:
    kind: str
    snippet: str


@dataclass(frozen=True)
class FormatReport:
    """Verdict on one generation.

    `compliant` is meaningful only when `abstained` is False — see the module
    docstring.  For an abstention it is left False and no violation is recorded.
    """

    compliant: bool
    abstained: bool
    markers: list[int] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)

    @property
    def kinds(self) -> set[str]:
        return {v.kind for v in self.violations}


#: An abstention is the fixed refusal string the prompt asks for (22 characters).
#: Anything an order of magnitude longer that merely *contains* one of the
#: phrases is prose — e.g. "the paper gives insufficient information on the
#: sample size, but reports the mean" — and prose with no citation is a format
#: failure, not a refusal.  Without this bound, ABSTENTION_PHRASES entries as
#: short as "non so" would quietly excuse uncited answers from the denominator
#: and inflate the compliance rate.
_MAX_ABSTENTION_CHARS = 200


def has_abstention_phrase(text: str) -> bool:
    """True when the text contains one of the E-04/E-05 refusal phrases.

    Same phrase list as the generation baselines, so "abstained" means the same
    thing in a citation run as it does there.  Phrase presence alone is not
    enough to call an answer an abstention — see `is_abstention`.
    """
    lower = text.lower()
    return any(p in lower for p in ABSTENTION_PHRASES)


def is_abstention(text: str) -> bool:
    """True when the model declined to answer rather than answering uncited.

    Three conditions, all necessary: the refusal phrase, no citation markers,
    and a short answer.  An answer that cites is an answer whatever else it
    says, and a long one that merely mentions missing information is prose.
    """
    return (
        has_abstention_phrase(text)
        and not _MARKER.search(text)
        and len(text.strip()) <= _MAX_ABSTENTION_CHARS
    )


def find_violations(text: str, n_chunks: int) -> list[Violation]:
    """Every §3.2 violation in raw output, one entry per occurrence."""
    out: list[Violation] = []
    for kind, pattern in _PATTERNS:
        out.extend(Violation(kind, m.group(0)) for m in pattern.finditer(text))

    # Markers pointing outside the context. §3.2 requires the parser to discard
    # them; producing them is still a prompt failure, so they are counted here.
    for m in _MARKER.finditer(text):
        n = int(m.group(1))
        if not 1 <= n <= n_chunks:
            out.append(Violation("out_of_range", m.group(0)))

    if not _MARKER.search(text):
        out.append(Violation("no_citation", ""))
    return out


def check_format(text: str, n_chunks: int) -> FormatReport:
    """Classify one raw generation against ROADMAP §3.2."""
    if is_abstention(text):
        return FormatReport(compliant=False, abstained=True)
    violations = find_violations(text, n_chunks)
    return FormatReport(
        compliant=not violations,
        abstained=False,
        markers=sorted({int(m) for m in _MARKER.findall(text)}),
        violations=violations,
    )


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the 95% Wilson interval for a proportion k/n.

    C-01 asks for "≥95%", and a point estimate cannot answer that on a sample.
    39/40 is 97.5% with a lower bound of 87% — the same point estimate that
    passes on 400 answers fails on 40.  Wilson rather than the normal
    approximation because the interval sits near 1, where the normal one
    produces bounds above 100%.

    Full-population runs are not affordable here (one answer costs ~20s of GPU
    against ~10ms for a retrieval query), so the sample is all there is and its
    width has to be reported with it.
    """
    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


@dataclass(frozen=True)
class ComplianceSummary:
    """Aggregate over a set of generations.

    `rate` is over `n_scored` (non-abstained) answers only.  `n_abstained` is
    carried alongside because the rate cannot be read without it.
    """

    n_total: int
    n_abstained: int
    n_scored: int
    n_compliant: int
    rate: float
    rate_lower95: float
    kind_rates: dict[str, float]
    markers_per_answer: float

    @property
    def meets_target(self) -> bool:
        """True when the *lower bound* clears the target, not the point estimate.

        The stricter reading of "≥95%": it is the one that does not let a small
        sample declare a pass it cannot support.
        """
        return self.rate_lower95 >= COMPLIANCE_TARGET


def summarize(reports: list[FormatReport]) -> ComplianceSummary:
    """Aggregate reports into the numbers C-01 is accepted on.

    `kind_rates` has an entry for every kind in VIOLATION_KINDS, zero included:
    a run that reports only the kinds it saw cannot be compared with one that
    saw different kinds.
    """
    n_total = len(reports)
    scored = [r for r in reports if not r.abstained]
    n_scored = len(scored)
    n_compliant = sum(1 for r in scored if r.compliant)

    kind_rates = {
        kind: (sum(1 for r in scored if kind in r.kinds) / n_scored if n_scored else 0.0)
        for kind in VIOLATION_KINDS
    }
    return ComplianceSummary(
        n_total=n_total,
        n_abstained=n_total - n_scored,
        n_scored=n_scored,
        n_compliant=n_compliant,
        rate=n_compliant / n_scored if n_scored else 0.0,
        rate_lower95=wilson_lower(n_compliant, n_scored),
        kind_rates=kind_rates,
        markers_per_answer=(
            sum(len(r.markers) for r in scored) / n_scored if n_scored else 0.0
        ),
    )
