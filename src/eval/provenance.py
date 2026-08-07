"""Where a result came from: git commit, golden set.

Both helpers were copy-pasted across `harness.py`, `generation_harness.py` and
`noise_floor.py`.  They are not incidental duplication: `git_commit` is a
required field of `EvalRun` (ROADMAP §3.3), so three copies of the function that
produces it are three places for the provenance of a measurement to drift.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.datasets.golden import GoldenQuery


def git_commit() -> str:
    """Current HEAD, or "unknown" outside a repo.

    Never raises: a result that records "unknown" is worse than one that records
    the real sha, but far better than an evaluation that dies at the last line
    after an hour of GPU time.
    """
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def load_golden(path: Path) -> list[GoldenQuery]:
    """Read a golden JSONL file into GoldenQuery objects.

    Strict on purpose — unlike the dashboard's tolerant loader, a malformed line
    here raises. Silently evaluating on fewer queries than intended would change
    a measurement without changing anything visible in the result file.
    """
    queries: list[GoldenQuery] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(GoldenQuery.model_validate_json(line))
    return queries
