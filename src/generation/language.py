"""Which language is an answer written in, and is it written in only one?  (C-05)

C-05 asks for "nessuna risposta mista incoerente": the failure is not *which*
language the model picks, it is picking more than one inside the same answer —
an English sentence followed by an Italian one, or a Spanish connector welded
onto an English clause.  So the unit of detection is the sentence, and the
metric is agreement between sentences.

**Function words, not a dependency.**  STACK.md requires a licence review for
every new library, and `langdetect`/`lingua` would be a package to vet, pin and
carry for a check that runs on twenty samples.  Function words are the highest
signal per line of code for this: they are frequent, short, and mostly disjoint
across the languages involved.

**What this is not.**  It is a closed-set detector over five languages, it needs
a handful of words to work, and it will label a sentence made of formulas or a
company name `unknown` rather than guess.  Those limits are why `unknown` is a
real answer here and not a failure — a metric that forces a label on evidence it
does not have would report mixed-language answers that are actually LaTeX.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Function words per language.  Chosen to be frequent and, as far as possible,
#: not shared: `la` is Italian *and* Spanish *and* French, so it is absent from
#: all three.  A word carried by two languages adds noise, not evidence.
_MARKERS: dict[str, set[str]] = {
    "en": {"the", "and", "of", "that", "with", "which", "this", "these", "from",
           "was", "were", "have", "has", "been", "not", "for", "are", "is", "it",
           "they", "their", "there", "when", "while", "between", "both", "such",
           "an", "on", "by", "as", "at", "its", "also", "than", "each"},
    "it": {"il", "lo", "gli", "di", "del", "della", "dei", "delle", "degli",
           "nel", "nella", "che", "non", "per", "sono", "come", "questo",
           "questa", "anche", "più", "essere", "stato", "viene", "hanno",
           "alla", "dal", "sul", "ma", "si", "ha", "nei", "sia", "tra"},
    "es": {"el", "los", "las", "por", "para", "pero", "más", "este", "esta",
           "son", "fue", "han", "sus", "del", "sobre", "cuando", "también",
           "porque", "está", "muy", "al", "se", "su", "lo", "ha", "ser", "y"},
    "fr": {"le", "les", "des", "pour", "avec", "dans", "sur", "est", "sont",
           "cette", "ces", "aux", "par", "plus", "être", "ont", "leur", "mais",
           "lorsque", "aussi", "peut", "qui", "du", "ne", "au", "une", "il"},
    "de": {"und", "der", "die", "das", "den", "dem", "des", "ist", "sind",
           "nicht", "auch", "eine", "einen", "mit", "für", "auf", "von", "bei",
           "wird", "werden", "wurde", "haben", "diese", "durch", "als", "im"},
}

#: A word claimed by k languages is worth 1/k, not zero.
#:
#: Dropping shared words outright was the first attempt and it was too blunt:
#: `il` is Italian *and* French, so Italian lost its single most frequent
#: marker and short Italian sentences came back `unknown`.  Weighting keeps the
#: word contributing to both, where it is exactly as ambiguous as it really is,
#: and lets the rest of the sentence break the tie.
_CLAIMS: dict[str, int] = {}
for _ws in _MARKERS.values():
    for _w in _ws:
        _CLAIMS[_w] = _CLAIMS.get(_w, 0) + 1

_WEIGHTS: dict[str, dict[str, float]] = {
    lang: {w: 1.0 / _CLAIMS[w] for w in ws} for lang, ws in _MARKERS.items()
}

_WORD = re.compile(r"[a-zà-öø-ÿ]+", re.IGNORECASE)
_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")

#: Below this much weighted evidence a sentence is `unknown`.  One stray word is
#: a coincidence — "die" appears in English text, "sono" inside a proper noun —
#: and two words shared with another language are worth one unshared word.
MIN_EVIDENCE = 1.5

#: The winner must lead the runner-up by this much.  A near-tie is precisely the
#: case where guessing would invent the mixed-language finding C-05 measures.
MIN_MARGIN = 0.5

UNKNOWN = "unknown"


def detect(text: str) -> str:
    """Best-guess language, or `unknown` when the evidence is too thin."""
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return UNKNOWN
    seen = set(words)
    hits = {lang: sum(w.get(x, 0.0) for x in seen) for lang, w in _WEIGHTS.items()}
    best = max(hits, key=lambda k: hits[k])
    runner_up = sorted(hits.values())[-2]
    if hits[best] < MIN_EVIDENCE or hits[best] - runner_up < MIN_MARGIN:
        return UNKNOWN
    return best


@dataclass(frozen=True)
class LanguageProfile:
    """Per-sentence languages of one answer.

    `is_mixed` is the C-05 failure: two *identified* languages in one answer.
    Sentences that could not be identified are counted but never make an answer
    mixed — an unlabelled sentence is missing evidence, not evidence of a second
    language.
    """

    dominant: str
    per_sentence: list[str] = field(default_factory=list)

    @property
    def identified(self) -> list[str]:
        return [x for x in self.per_sentence if x != UNKNOWN]

    @property
    def languages(self) -> set[str]:
        return set(self.identified)

    @property
    def is_mixed(self) -> bool:
        return len(self.languages) > 1

    @property
    def n_unknown(self) -> int:
        return sum(1 for x in self.per_sentence if x == UNKNOWN)


def profile(answer: str) -> LanguageProfile:
    """Detect the language of each sentence and the answer's dominant one."""
    sentences = [s.strip() for s in _BOUNDARY.split(answer.strip()) if s.strip()]
    per = [detect(s) for s in sentences]
    identified = [x for x in per if x != UNKNOWN]
    dominant = max(set(identified), key=identified.count) if identified else UNKNOWN
    return LanguageProfile(dominant=dominant, per_sentence=per)


def matches_query(answer: str, query: str) -> bool | None:
    """Is the answer in the language of the question?

    Returns None when either side could not be identified — the honest answer
    when there is nothing to compare, and distinct from a real mismatch.
    """
    q, a = detect(query), profile(answer).dominant
    if q == UNKNOWN or a == UNKNOWN:
        return None
    return q == a
