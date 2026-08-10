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
    """Current HEAD, suffixed `-dirty` when tracked files are modified.

    The suffix is the point.  Without it, an evaluation run with uncommitted
    changes records a sha describing code that never existed in that form, and
    re-running at that sha silently produces a different number with nothing to
    warn you.  Recording provenance that can be wrong is worse than recording
    less provenance.

    It goes at the end so `git_commit[:7]` keeps yielding the sha prefix — the
    dashboard renders it that way in three places.

    **Untracked files are ignored on purpose.** Every run writes its own result
    files, and the harness would otherwise mark itself dirty from the previous
    run's untracked output; a flag that is always on carries no information.
    What matters for reproduction is the tracked state, which is what
    `git checkout <sha>` restores.

    Never raises: a result that records "unknown" is worse than one that records
    the real sha, but far better than an evaluation that dies at the last line
    after an hour of GPU time.
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"
    try:
        modified = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return sha
    return f"{sha}-dirty" if modified else sha


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
