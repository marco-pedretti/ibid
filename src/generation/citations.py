"""Citation marker parser — normalises and validates [n] markers in LLM output.

Rules from ROADMAP §3.2:
- Only contiguous [n][m] markers are valid.
- Known malformed variants are normalised; markers out of context are discarded.
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
