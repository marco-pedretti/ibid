"""Tests for src/eval/provenance.py — the `-dirty` marker and when it is read.

`git_commit` is a required field of EvalRun (ROADMAP §3.3) and it is the only
thing that says which code produced a number.  Two ways it could lie, both
closed here: recording a clean sha while the tree had uncommitted changes, and
reading HEAD at the end of a run that took forty minutes.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.eval.provenance import git_commit

SHA = "a" * 40


def _outputs(*results):
    """subprocess.check_output stub returning each result in turn."""
    it = iter(results)

    def fake(cmd, **kw):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r.encode()

    return fake


class TestDirtyMarker:
    def test_clean_tree_is_the_bare_sha(self):
        with patch.object(subprocess, "check_output", _outputs(SHA, "")):
            assert git_commit() == SHA

    def test_modified_tracked_file_marks_dirty(self):
        with patch.object(subprocess, "check_output", _outputs(SHA, " M src/config.py")):
            assert git_commit() == f"{SHA}-dirty"

    def test_suffix_goes_last_so_the_prefix_still_reads(self):
        # The dashboard renders git_commit[:7] in three places.
        with patch.object(subprocess, "check_output", _outputs(SHA, " M x.py")):
            assert git_commit()[:7] == SHA[:7]

    def test_untracked_files_are_not_dirt(self):
        """Every run writes its own result files.

        `--untracked-files=no` is passed for this reason: without it the harness
        would mark itself dirty from the previous run's output, and a flag that
        is always on carries no information.
        """
        captured = {}

        def fake(cmd, **kw):
            if "status" in cmd:
                captured["cmd"] = cmd
                return b""
            return SHA.encode()

        with patch.object(subprocess, "check_output", fake):
            git_commit()
        assert "--untracked-files=no" in captured["cmd"]


class TestNeverRaises:
    def test_outside_a_repo_is_unknown(self):
        with patch.object(subprocess, "check_output", _outputs(FileNotFoundError())):
            assert git_commit() == "unknown"

    def test_status_failure_falls_back_to_the_sha(self):
        # Losing the dirty flag is bad; losing an hour of GPU at the last line
        # is worse.
        with patch.object(subprocess, "check_output", _outputs(SHA, OSError())):
            assert git_commit() == SHA


class TestReadAtStart:
    """The commit is captured before the run, not when the EvalRun is built.

    A commit made during the forty minutes in between would otherwise be
    recorded as the one that generated the answers.
    """

    def test_citation_harness_reads_it_once_up_front(self):
        import inspect

        from src.eval import citation_harness

        src = inspect.getsource(citation_harness.run_citation_eval)
        assert "commit = git_commit()" in src
        assert "git_commit=commit," in src
        # Not called again where the EvalRun is assembled.
        assert "git_commit=git_commit()" not in src

    def test_retrieval_harness_reads_it_once_up_front(self):
        import inspect

        from src.eval import harness

        src = inspect.getsource(harness.run_retrieval_eval)
        assert "commit = git_commit()" in src
        assert "git_commit=git_commit()" not in src

    def test_generation_harness_reads_it_once_up_front(self):
        import inspect

        from src.eval import generation_harness

        src = inspect.getsource(generation_harness.run_generation_eval)
        assert "commit = git_commit()" in src
        assert "git_commit=git_commit()" not in src
