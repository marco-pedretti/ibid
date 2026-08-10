"""Citation marker parser — normalises and validates [n] markers in LLM output.

Rules from ROADMAP §3.2:
- Only contiguous [n][m] markers are valid.
- Known malformed variants are normalised; markers out of context are discarded.

"Known variants" means known *from the corpus*, not from imagination.  The T-06
rules here were written before any generation existed; C-02 rebuilt them against
`tests/fixtures/malformed_citations.jsonl`, cut from 897 real answers.  Where a
rule and the corpus disagreed, the corpus won — see the comments on the
individual rules for what each one is actually evidenced by.
"""

from __future__ import annotations

import re


def _in_context(nums: list[int], n_chunks: int) -> bool:
    """True when every number could be a chunk index in this context.

    The gate on all four multi-number expansions, and the single most consequential
    rule in the module.  Measured on the C-02 fixture: of the 16 real occurrences
    of `[1-7]`, `[16,17,18,19]`, `[1]-[21]` and friends, **zero** name numbers that
    fit their context.  They are the source paper's bibliography, reproduced by a
    model that saw `[n]` markers in its own chunks — C-01's dominant failure mode
    on open_ragbench.

    Expanding them is not a repair, it is fabrication: `[1-7]` against 5 chunks
    became `[1][2][3][4][5]`, five confident citations of chunks the model never
    pointed at, and the discard step afterwards could not tell them from real ones
    because by then they looked real.  On this corpus the T-06 expansion repaired
    nothing and invented citations 16 times out of 16.

    The expansions stay because `[1,2]` against 5 chunks *is* a malformed citation
    of ours and this corpus simply does not contain one.  Gating them costs
    nothing when the construct is genuine and stops the fabrication when it is not.
    """
    return all(1 <= n <= n_chunks for n in nums)


def _expand_comma(m: re.Match, n_chunks: int) -> str:
    nums = [int(n) for n in re.findall(r"\d+", m.group(0))]
    if not _in_context(nums, n_chunks):
        return m.group(0)
    return "".join(f"[{n}]" for n in nums)


def _expand_range(m: re.Match, n_chunks: int) -> str:
    start, end = int(m.group(1)), int(m.group(2))
    if start > end or not _in_context([start, end], n_chunks):
        return m.group(0)
    return "".join(f"[{n}]" for n in range(start, end + 1))


def _expand_pair(m: re.Match, n_chunks: int) -> str:
    a, b = int(m.group(1)), int(m.group(2))
    if not _in_context([a, b], n_chunks):
        return m.group(0)
    return f"[{a}][{b}]"


def normalize(text: str, n_chunks: int) -> str:
    """Normalize malformed citation forms to canonical [n][m] sequence.

    `n_chunks` is required, not optional: whether `[1-7]` is a citation to repair
    or the source document's bibliography to leave alone is not a property of the
    string — it depends on how many chunks were in context.  A default would let a
    caller expand blind, which is the behaviour this signature exists to prevent.
    """
    # [1]-[2] → [1][2]  (two markers joined by a dash)
    text = re.sub(r"\[(\d+)\]-\[(\d+)\]", lambda m: _expand_pair(m, n_chunks), text)
    # [1,2] / [1, 2] / [1,2,3]  (comma-separated list)
    text = re.sub(r"\[\d+(?:,\s*\d+)+\]", lambda m: _expand_comma(m, n_chunks), text)
    # [1 e 2] / [1 and 2]  (Italian / English "and")
    text = re.sub(r"\[(\d+)\s+(?:e|and)\s+(\d+)\]", lambda m: _expand_pair(m, n_chunks),
                  text, flags=re.IGNORECASE)
    # [1-3] / [1–3]  (hyphen or en-dash range, must follow [1]-[2] rule)
    text = re.sub(r"\[(\d+)[-–]\s*(\d+)\]", lambda m: _expand_range(m, n_chunks), text)
    # [1] [3] → [1][3]  (markers separated by whitespace instead of contiguous)
    #
    # The most frequent repairable defect in the corpus: 40 occurrences, and
    # 21 of the answers the T-06 parser left non-compliant were this and
    # nothing else — it had no rule for it at all.
    #
    # Last, because expansion produces spaced pairs of its own: `[1] [2,3]`
    # becomes `[1] [2][3]` and only then has a gap to close.  The lookahead
    # rather than a two-marker match is what closes chains of three or more in
    # a single pass.
    #
    # Space and tab only.  A newline between two markers separates lines of a
    # list, where contiguity was never claimed; joining those would merge two
    # citations the model kept apart.  `citation_format` draws the boundary in
    # the same place, so what it flags is exactly what this repairs.
    text = re.sub(r"\[(\d+)\][ \t]+(?=\[\d+\])", r"[\1]", text)
    return text


def filter_valid(text: str, n_chunks: int) -> str:
    """Remove [n] markers where n < 1 or n > n_chunks.

    A dash-joined pair is stepped over rather than taken apart.  Any `[1]-[21]`
    still standing here has already been judged by `normalize` and found to
    overflow — one that fitted would have become `[1][21]` and would not match.
    Stripping only its out-of-range half would leave `[1]-`, turning the source
    document's reference into a citation of our chunk 1: the same fabrication the
    expansion gate exists to prevent, arrived at from the other side.

    A discarded marker takes the space in front of it with it.  Removing `[8]`
    from "in the frequency domain [8]." used to leave "domain ." — a gap where a
    citation was, in text that goes to a reader.  The space is part of what the
    marker occupied, so it goes with the marker; a kept marker keeps its own.
    """
    def _keep(m: re.Match) -> str:
        if m.group("pair"):
            return m.group(0)
        n = int(m.group("num"))
        return m.group(0) if 1 <= n <= n_chunks else ""

    return re.sub(
        r"(?P<lead>[ \t]*)(?:(?P<pair>\[\d+\]\s*[-–—]\s*\[\d+\])|\[(?P<num>\d+)\])",
        _keep,
        text,
    )


def parse(text: str, n_chunks: int) -> str:
    """Normalize malformed markers, then discard out-of-range ones."""
    return filter_valid(normalize(text, n_chunks), n_chunks)


def extract_cited(text: str) -> list[int]:
    """Return sorted unique 1-based citation numbers present in text."""
    return sorted({int(m) for m in re.findall(r"\[(\d+)\]", text)})
