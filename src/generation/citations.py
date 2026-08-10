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


def _expand_comma(m: re.Match) -> str:
    nums = re.findall(r"\d+", m.group(0))
    return "".join(f"[{n}]" for n in nums)


def _expand_range(m: re.Match) -> str:
    start, end = int(m.group(1)), int(m.group(2))
    if start <= end:
        return "".join(f"[{n}]" for n in range(start, end + 1))
    return m.group(0)


def normalize(text: str) -> str:
    """Normalize malformed citation forms to canonical [n][m] sequence."""
    # [1]-[2] → [1][2]  (two markers joined by a dash)
    text = re.sub(r"\[(\d+)\]-\[(\d+)\]", r"[\1][\2]", text)
    # [1,2] / [1, 2] / [1,2,3]  (comma-separated list)
    text = re.sub(r"\[\d+(?:,\s*\d+)+\]", _expand_comma, text)
    # [1 e 2] / [1 and 2]  (Italian / English "and")
    text = re.sub(r"\[(\d+)\s+(?:e|and)\s+(\d+)\]", r"[\1][\2]", text, flags=re.IGNORECASE)
    # [1-3] / [1–3]  (hyphen or en-dash range, must follow [1]-[2] rule)
    text = re.sub(r"\[(\d+)[-–]\s*(\d+)\]", _expand_range, text)
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
    """Remove [n] markers where n < 1 or n > n_chunks."""
    def _keep(m: re.Match) -> str:
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= n_chunks else ""

    return re.sub(r"\[(\d+)\]", _keep, text)


def parse(text: str, n_chunks: int) -> str:
    """Normalize malformed markers, then discard out-of-range ones."""
    return filter_valid(normalize(text), n_chunks)


def extract_cited(text: str) -> list[int]:
    """Return sorted unique 1-based citation numbers present in text."""
    return sorted({int(m) for m in re.findall(r"\[(\d+)\]", text)})
