"""Tests for E-02: unanswerable query generation."""

from __future__ import annotations

from pathlib import Path


from src.datasets.golden import GoldenQuery, save_golden, GoldenQrel
from src.datasets.unanswerable import (
    _HANDWRITTEN_LEDGER,
    _HANDWRITTEN_OPEN_RAGBENCH,
    build_unanswerable_for_ledger,
    build_unanswerable_for_open_ragbench,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal golden files in tmp_path
# ---------------------------------------------------------------------------

def _write_golden_fixtures(golden_dir: Path) -> None:
    golden_dir.mkdir(parents=True, exist_ok=True)

    # 30 fake open_ragbench queries
    orb = [
        GoldenQuery(
            query_id=f"orb_{i:04d}",
            dataset_id="open_ragbench",
            query_text=f"Science question {i}?",
            qrels=[GoldenQrel(chunk_id=f"open_ragbench:doc:{i}", relevance=2)],
        )
        for i in range(30)
    ]
    save_golden(orb, golden_dir / "open_ragbench.jsonl")

    # 30 fake ledger queries
    ledger = [
        GoldenQuery(
            query_id=f"led_{i:04d}",
            dataset_id="ledger",
            query_text=f"Financial KPI question {i}?",
            qrels=[GoldenQrel(chunk_id=f"ledger:NYSE_CO_{i}:0001", relevance=2)],
        )
        for i in range(30)
    ]
    save_golden(ledger, golden_dir / "ledger.jsonl")


# ---------------------------------------------------------------------------
# Handwritten lists sanity checks
# ---------------------------------------------------------------------------

class TestHandwrittenLists:
    def test_orb_has_ten_entries(self):
        assert len(_HANDWRITTEN_OPEN_RAGBENCH) == 10

    def test_ledger_has_ten_entries(self):
        assert len(_HANDWRITTEN_LEDGER) == 10

    def test_orb_entries_are_nonempty_strings(self):
        for q in _HANDWRITTEN_OPEN_RAGBENCH:
            assert isinstance(q, str) and q.strip()

    def test_ledger_entries_are_nonempty_strings(self):
        for q in _HANDWRITTEN_LEDGER:
            assert isinstance(q, str) and q.strip()

    def test_no_duplicates_in_orb(self):
        assert len(set(_HANDWRITTEN_OPEN_RAGBENCH)) == len(_HANDWRITTEN_OPEN_RAGBENCH)

    def test_no_duplicates_in_ledger(self):
        assert len(set(_HANDWRITTEN_LEDGER)) == len(_HANDWRITTEN_LEDGER)


# ---------------------------------------------------------------------------
# build_unanswerable_for_open_ragbench
# ---------------------------------------------------------------------------

class TestBuildUnanswerableORB:
    def test_count(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_open_ragbench(tmp_path, n_cross=25)
        assert len(qs) == 25 + 10  # cross + manual

    def test_all_answerable_false(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_open_ragbench(tmp_path):
            assert q.answerable is False

    def test_all_qrels_empty(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_open_ragbench(tmp_path):
            assert q.qrels == []

    def test_dataset_id(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_open_ragbench(tmp_path):
            assert q.dataset_id == "open_ragbench"

    def test_cross_source_meta(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_open_ragbench(tmp_path, n_cross=25)
        cross = [q for q in qs if q.meta.get("source") == "cross_dataset_ledger"]
        assert len(cross) == 25
        for q in cross:
            assert "original_query_id" in q.meta

    def test_manual_source_meta(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_open_ragbench(tmp_path)
        manual = [q for q in qs if q.meta.get("source") == "manual"]
        assert len(manual) == 10

    def test_unique_query_ids(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_open_ragbench(tmp_path)
        ids = [q.query_id for q in qs]
        assert len(ids) == len(set(ids))

    def test_deterministic_with_same_seed(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        a = build_unanswerable_for_open_ragbench(tmp_path, seed=42)
        b = build_unanswerable_for_open_ragbench(tmp_path, seed=42)
        assert [q.query_text for q in a] == [q.query_text for q in b]

    def test_different_seed_different_cross(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        a = build_unanswerable_for_open_ragbench(tmp_path, seed=1)
        b = build_unanswerable_for_open_ragbench(tmp_path, seed=2)
        cross_a = [q.query_text for q in a if q.meta.get("source") == "cross_dataset_ledger"]
        cross_b = [q.query_text for q in b if q.meta.get("source") == "cross_dataset_ledger"]
        assert cross_a != cross_b

    def test_n_cross_capped_at_available(self, tmp_path):
        _write_golden_fixtures(tmp_path)  # only 30 ledger entries
        qs = build_unanswerable_for_open_ragbench(tmp_path, n_cross=50)
        cross = [q for q in qs if q.meta.get("source") == "cross_dataset_ledger"]
        assert len(cross) == 30  # capped at available


# ---------------------------------------------------------------------------
# build_unanswerable_for_ledger
# ---------------------------------------------------------------------------

class TestBuildUnanswerableLedger:
    def test_count(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_ledger(tmp_path, n_cross=25)
        assert len(qs) == 25 + 10

    def test_all_answerable_false(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_ledger(tmp_path):
            assert q.answerable is False

    def test_all_qrels_empty(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_ledger(tmp_path):
            assert q.qrels == []

    def test_dataset_id(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        for q in build_unanswerable_for_ledger(tmp_path):
            assert q.dataset_id == "ledger"

    def test_cross_source_meta(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_ledger(tmp_path, n_cross=25)
        cross = [q for q in qs if q.meta.get("source") == "cross_dataset_open_ragbench"]
        assert len(cross) == 25

    def test_unique_query_ids(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        qs = build_unanswerable_for_ledger(tmp_path)
        ids = [q.query_id for q in qs]
        assert len(ids) == len(set(ids))

    def test_deterministic_with_same_seed(self, tmp_path):
        _write_golden_fixtures(tmp_path)
        a = build_unanswerable_for_ledger(tmp_path, seed=42)
        b = build_unanswerable_for_ledger(tmp_path, seed=42)
        assert [q.query_text for q in a] == [q.query_text for q in b]
