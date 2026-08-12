"""Tests for scripts/compare_generations.py (C-07).

The script is thin — `src/eval/paired.py` holds the statistics and is tested
separately.  What is tested here is the part that decides *which* queries reach
the test, because that is where a paired comparison stops being paired.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "compare_generations", ROOT / "scripts" / "compare_generations.py"
)
compare_generations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare_generations)


def _record(query_id: str, compliant: bool, abstained: bool = False, **kw) -> dict:
    return {
        "query_id": query_id,
        "query_text": "Q?",
        "chunk_ids": ["c1"],
        "n_chunks": 1,
        "answer": "Vero [1].",
        "compliant": compliant,
        "abstained": abstained,
        "markers": [1],
        "violations": [],
        "latency_s": 1.0,
        "finish_reason": "stop",
        "completion_tokens": 100,
        **kw,
    }


def _write(tmp_path: Path, name: str, records: list[dict]) -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


class TestLoad:
    def test_keys_by_query_id(self, tmp_path):
        path = _write(tmp_path, "a.jsonl", [_record("q1", True), _record("q2", False)])
        loaded = compare_generations.load(path)
        assert set(loaded) == {"q1", "q2"}
        assert loaded["q1"]["compliant"] is True

    def test_a_partial_run_is_refused(self, tmp_path):
        """`.partial` means the run did not reach the end.

        Scoring a prefix of one arm against the whole of the other is not a
        paired comparison, and the file name is the only warning there is —
        `GenerationWriter` promotes it only after the last record.
        """
        path = _write(tmp_path, "a.jsonl.partial", [_record("q1", True)])
        with pytest.raises(SystemExit):
            compare_generations.load(path)


class TestPairing:
    """Only queries both arms actually answered enter the test."""

    def _capture(self, capsys, recs_a, recs_b, tmp_path):
        a = _write(tmp_path, "a.jsonl", recs_a)
        b = _write(tmp_path, "b.jsonl", recs_b)
        sys.argv = ["compare_generations.py", "--a", str(a), "--b", str(b)]
        compare_generations.main()
        return capsys.readouterr().out

    def test_abstained_on_one_side_leaves_the_paired_test(self, capsys, tmp_path):
        """An abstention carries no citation, so scoring it as a format failure
        blames the prompt for a refusal — the reason C-01 excludes it too.  A
        query counts only when *both* arms answered."""
        out = self._capture(
            capsys,
            [_record("q1", True), _record("q2", True), _record("q3", False)],
            [_record("q1", True), _record("q2", False, abstained=True), _record("q3", False)],
            tmp_path,
        )
        assert "1 query astenute da un solo braccio" in out
        assert "su 2)" in out  # q1 and q3 only

    def test_disjoint_query_sets_are_fatal(self, capsys, tmp_path):
        a = _write(tmp_path, "a.jsonl", [_record("q1", True)])
        b = _write(tmp_path, "b.jsonl", [_record("q9", True)])
        sys.argv = ["compare_generations.py", "--a", str(a), "--b", str(b)]
        with pytest.raises(SystemExit):
            compare_generations.main()

    def test_identical_arms_report_no_difference(self, capsys, tmp_path):
        recs = [_record(f"q{i}", i % 2 == 0) for i in range(10)]
        out = self._capture(capsys, recs, list(recs), tmp_path)
        assert "identici su ogni query" in out

    def test_delta_is_b_minus_a(self, capsys, tmp_path):
        out = self._capture(
            capsys,
            [_record(f"q{i}", False) for i in range(4)],
            [_record(f"q{i}", True) for i in range(4)],
            tmp_path,
        )
        assert "delta +1.0000" in out


class TestRepaired:
    """C-07: un guadagno che il parser produrrebbe comunque non è un guadagno.

    C-01 misura il testo grezzo di proposito, ma il sistema serve ciò che esce da
    `citations.normalize`. Sul confronto vero di C-07 il ragionamento guadagna
    +4,4 punti sul grezzo (p=0,0386) e +0,6 sul riparato (p=1,0000): tutto il
    guadagno era in una variante che il parser ripara gratis.
    """

    def test_raw_verdict_uses_the_stored_flag(self, tmp_path):
        rec = _record("q1", False, answer="Vero [1] [2].", n_chunks=2)
        assert compare_generations.compliant(rec, repaired=False) is False

    def test_repaired_verdict_rechecks_the_text(self, tmp_path):
        """`[1] [2]` è la variante che il parser unisce, ed è l'intero effetto
        misurato in C-07."""
        rec = _record("q1", False, answer="Vero [1] [2].", n_chunks=2)
        assert compare_generations.compliant(rec, repaired=True) is True

    def test_repair_does_not_rescue_an_unfixable_answer(self, tmp_path):
        """Un marcatore fuori contesto viene scartato, non riparato: la risposta
        resta non conforme."""
        rec = _record("q1", False, answer="Vero senza citazione.", n_chunks=2)
        assert compare_generations.compliant(rec, repaired=True) is False

    def test_stored_flag_is_not_trusted_when_repairing(self, tmp_path):
        """Il verdetto riparato non è ricavabile da quello grezzo, quindi va
        ricalcolato invece che dedotto."""
        rec = _record("q1", True, answer="Vero [1] [2].", n_chunks=2)
        assert compare_generations.compliant(rec, repaired=True) is True
