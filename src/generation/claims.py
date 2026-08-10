"""Split a generated answer into the units that get verified (C-03).

ROADMAP §0 claim 1 is about attribution **at sentence level**, so the unit of
verification is one sentence together with the markers it carries.  An answer
verified as a whole would hide the failure the project exists to measure: three
correct sentences and one invented one, all under the same citation.

Two decisions live here.

**The markers come out of the claim text.**  What goes to the entailment model
is the sentence a reader would read, not `Il valore è 400ms [2][3].`  An NLI
model has never seen bracketed indices in training and they are not part of what
the sentence asserts; leaving them in feeds noise into the hypothesis.

**A sentence with no markers is kept, not dropped.**  It is the uncited claim —
the exact thing C-03 is supposed to surface — and dropping it would let a model
raise its own precision by citing less.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Sentence boundary: terminator, then whitespace.  Markers sit *before* the
#: terminator per §3.2 (`... 400ms [2][3].`), so they stay with their sentence.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

_MARKER = re.compile(r"\[(\d+)\]")

#: Below this a "sentence" is a fragment — a heading, a list bullet, a stray
#: `Fig.` — and asking whether a chunk entails it is not a meaningful question.
#: Fragments are still returned; the flag lets the metric exclude them and say
#: how many it excluded, rather than silently changing its own denominator.
MIN_CLAIM_CHARS = 30


@dataclass(frozen=True)
class Claim:
    """One sentence of an answer, and the chunks it cites.

    `text` has the markers removed and is what the verifier sees.  `raw` keeps
    the sentence as generated, because the failure reports are read by people
    and a claim without its markers is hard to locate in the answer.
    """

    text: str
    raw: str
    markers: list[int] = field(default_factory=list)

    @property
    def is_cited(self) -> bool:
        return bool(self.markers)

    @property
    def is_verifiable(self) -> bool:
        """Long enough that "does the chunk support this" has an answer."""
        return len(self.text) >= MIN_CLAIM_CHARS


def strip_markers(text: str) -> str:
    """Remove `[n]` markers and the whitespace they leave behind."""
    return re.sub(r"[ \t]*\[\d+\]", "", text).strip()


def split_claims(answer: str, n_chunks: int | None = None) -> list[Claim]:
    """Split an answer into per-sentence claims with their citations.

    Args:
        answer: the generated text.  Pass it **after** `citations.parse` — the
            markers have to be canonical and in range before they can be read as
            a citation set, and that repair is C-02's job, not this module's.
        n_chunks: when given, markers outside 1..n_chunks are dropped.  They
            point at nothing, so they cannot be verified either way; `parse`
            normally removes them already and this is a second line of defence
            for callers that skipped it.

    Returns:
        One Claim per sentence, in order, including uncited and fragment ones.
    """
    claims: list[Claim] = []
    for raw in _BOUNDARY.split(answer.strip()):
        raw = raw.strip()
        if not raw:
            continue
        markers = sorted({int(m) for m in _MARKER.findall(raw)})
        if n_chunks is not None:
            markers = [m for m in markers if 1 <= m <= n_chunks]
        claims.append(Claim(text=strip_markers(raw), raw=raw, markers=markers))
    return claims


def citation_pairs(claims: list[Claim]) -> list[tuple[Claim, int]]:
    """Every (claim, cited chunk) pair — the unit `citation_precision` is over.

    ROADMAP §8 words C-03 as "affermazione ↔ chunk citato", one pair at a time,
    so a sentence citing three chunks contributes three pairs and a sentence
    citing none contributes zero.
    """
    return [(c, m) for c in claims if c.is_verifiable for m in c.markers]
