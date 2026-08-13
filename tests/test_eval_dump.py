"""Q-02: il meccanismo dei dump per query.

Il valore di questo modulo non è che scriva JSON — è che **un file troncato non
si confonda con uno finito**. Un dump letto come completo quando non lo è
produce un tasso calcolato su un denominatore diverso da quello che dichiara,
che è peggio di nessun dump.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.eval.dump import JsonlWriter, aligned, partial_path, read_jsonl, write_all


@dataclass
class _Rec:
    query_id: str
    value: int


class TestPartialUntilFinished:
    def test_records_go_to_the_partial_file(self, tmp_path):
        w = JsonlWriter(tmp_path / "d.jsonl")
        w.append(_Rec("q1", 1))
        assert partial_path(tmp_path / "d.jsonl").exists()
        assert not (tmp_path / "d.jsonl").exists()

    def test_the_final_name_appears_only_at_the_end(self, tmp_path):
        """L'esistenza del nome definitivo è la prova che la run è arrivata in
        fondo — è tutto ciò su cui un lettore può contare."""
        p = tmp_path / "d.jsonl"
        w = JsonlWriter(p)
        w.append(_Rec("q1", 1))
        assert not p.exists()
        w.finish()
        assert p.exists() and not partial_path(p).exists()

    def test_a_dead_run_keeps_what_it_had(self, tmp_path):
        """Il motivo per cui si scrive incrementalmente: una run morta alla
        query 190 su 200 non deve perdere le 190."""
        w = JsonlWriter(tmp_path / "d.jsonl")
        for i in range(190):
            w.append(_Rec(f"q{i}", i))
        # nessun finish(): la run è morta qui
        lines = partial_path(tmp_path / "d.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 190

    def test_counts_what_it_wrote(self, tmp_path):
        w = JsonlWriter(tmp_path / "d.jsonl")
        for i in range(3):
            w.append(_Rec(f"q{i}", i))
        assert w.n == 3


class TestReadRefusesPartials:
    def test_reading_a_partial_raises(self, tmp_path):
        """Leggerlo in silenzio è esattamente il difetto che il suffisso previene."""
        p = tmp_path / "d.jsonl"
        w = JsonlWriter(p)
        w.append(_Rec("q1", 1))
        with pytest.raises(ValueError, match="non finita"):
            read_jsonl(partial_path(p))

    def test_round_trip(self, tmp_path):
        p = write_all(tmp_path / "d.jsonl", [_Rec("q1", 1), _Rec("q2", 2)])
        assert [r["query_id"] for r in read_jsonl(p)] == ["q1", "q2"]

    def test_blank_lines_are_skipped(self, tmp_path):
        p = tmp_path / "d.jsonl"
        p.write_text('{"query_id": "q1"}\n\n{"query_id": "q2"}\n', encoding="utf-8")
        assert len(read_jsonl(p)) == 2


class TestSidecar:
    def test_written_up_front(self, tmp_path):
        """Una run che muore lascia comunque i propri record interpretabili."""
        JsonlWriter(tmp_path / "d.jsonl", sidecar="IL PROMPT")
        assert (tmp_path / "d.prompt.txt").read_text(encoding="utf-8") == "IL PROMPT"

    def test_absent_when_not_asked(self, tmp_path):
        JsonlWriter(tmp_path / "d.jsonl")
        assert not (tmp_path / "d.prompt.txt").exists()


class TestAligned:
    def test_same_queries_gives_sorted_ids(self):
        a = {"q2": {}, "q1": {}}
        assert aligned(a, {"q1": {}, "q2": {}}) == ["q1", "q2"]

    def test_different_queries_refused(self):
        """Un test appaiato su un'intersezione decisa dal caso non è appaiato:
        la popolazione la sceglierebbe la differenza fra i due file."""
        with pytest.raises(ValueError, match="stesse query"):
            aligned({"q1": {}}, {"q1": {}, "q2": {}})

    def test_the_message_says_how_many(self):
        with pytest.raises(ValueError, match="1 solo in A"):
            aligned({"q1": {}, "q3": {}}, {"q3": {}, "q2": {}})
