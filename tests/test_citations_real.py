"""C-02 — the parser against citation constructs the model actually produced.

`test_citations.py` covers the T-06 parser on variants invented while writing
it.  This module covers the ones that exist.  Its material is
`tests/fixtures/malformed_citations.jsonl`, cut from the five C-01 generation
dumps by `scripts/extract_malformed.py` — 897 scored answers over both datasets.

The distinction matters because the two sets barely overlap.  T-06 imagined
`[1,2]` and `[1-3]`: plausible, and absent from the corpus.  What the corpus
contains instead is `[1] [3]`, `[102-109]` and `[16,17,18,19]` — the model
citing the *source document's* reference numbering, which C-01 established is
the dominant failure mode on open_ragbench (23% of its chunks carry `[n]`
markers of their own; LEDGER carries none).

A fixture regenerated from new runs will change these counts.  The tests assert
the *shape* of the corpus, not its exact size, except where a count is the
evidence for a design decision — those say so.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.generation.citation_format import check_format
from src.generation.citations import parse

FIXTURE = Path(__file__).parent / "fixtures" / "malformed_citations.jsonl"

_MULTI_NUMBER_KINDS = ("comma_list", "range", "dash_joined", "conjunction")
_DIGITS = re.compile(r"\d+")


def _load() -> list[dict]:
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]


CASES = _load()


def _of_kind(*kinds: str) -> list[dict]:
    return [c for c in CASES if c["kind"] in kinds]


class TestFixture:
    """Guards on the material itself — a silently empty fixture passes every
    other test in this file."""

    def test_fixture_is_present_and_populated(self):
        assert len(CASES) >= 40

    def test_carries_provenance(self):
        for c in CASES:
            assert c["runs"], c
            assert c["query_id"]

    def test_covers_the_kinds_c01_reported(self):
        kinds = {c["kind"] for c in CASES}
        assert {"spaced_markers", "out_of_range", "range", "comma_list"} <= kinds

    def test_spaced_markers_is_the_largest_repairable_kind(self):
        """The C-01 residual: 21 of the 45 non-compliant answers that the T-06
        parser could not fix were `[1] [3]`, and it had no rule for them."""
        by_kind = {}
        for c in CASES:
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + c["occurrences"]
        repairable = {k: v for k, v in by_kind.items() if k != "out_of_range"}
        assert max(repairable, key=repairable.get) == "spaced_markers"


class TestCorpusShape:
    """The measurements the repair rules are designed against.

    These are assertions about the corpus, and they are here so that a rule
    justified by "no real construct looks like this" fails loudly if a future
    run produces one.
    """

    def test_no_multi_number_construct_fits_its_context(self):
        """0 of 16 occurrences. Every `[1-7]`, `[16,17,18,19]`, `[1]-[21]` in
        the corpus names numbers outside the chunks in context — they are the
        source paper's bibliography, not a malformed citation of ours.

        This is the entire evidence for expanding such constructs only when
        every number is a valid chunk index: on this corpus the T-06 expansion
        repaired nothing and fabricated citations 16 times.
        """
        for c in _of_kind(*_MULTI_NUMBER_KINDS):
            nums = [int(d) for d in _DIGITS.findall(c["snippet"])]
            assert not all(1 <= n <= c["n_chunks"] for n in nums), c

    def test_benign_bracketed_constructs_occur(self):
        """Mathematical intervals appear in real answers. A repair rule is only
        safe if it leaves them alone, so the corpus has to contain some."""
        assert _of_kind("not_a_citation")


class TestRepair:
    """`parse` on each real construct, in the sentence it appeared in."""

    @pytest.mark.parametrize("case", _of_kind("spaced_markers"), ids=lambda c: c["snippet"])
    def test_spaced_markers_become_contiguous(self, case):
        out = parse(case["text"], case["n_chunks"])
        assert "spaced_markers" not in check_format(out, case["n_chunks"]).kinds

    def test_a_chain_of_three_closes_in_one_pass(self):
        assert parse("misura [1] [2] [3] fine", 5) == "misura [1][2][3] fine"

    def test_a_newline_between_markers_is_not_a_gap_to_close(self):
        """Markers on separate lines are separate citations, not a spaced pair.
        `citation_format` does not flag them, so repairing them would silently
        merge what the model deliberately kept apart."""
        assert parse("- punto [1]\n- punto [2]", 5) == "- punto [1]\n- punto [2]"
