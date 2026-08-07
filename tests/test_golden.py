"""Tests for E-01: GoldenQuery schema and dataset loaders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.datasets.golden import (
    GoldenQrel,
    GoldenQuery,
    load_ledger_golden,
    load_open_ragbench_golden,
    save_golden,
    validate_golden_file,
)


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------

class TestGoldenQrel:
    def test_valid(self):
        q = GoldenQrel(chunk_id="open_ragbench:2401.00001v1:3", relevance=2)
        assert q.chunk_id == "open_ragbench:2401.00001v1:3"
        assert q.relevance == 2

    def test_relevance_zero(self):
        q = GoldenQrel(chunk_id="ledger:NYSE_SHW_2017:0003", relevance=0)
        assert q.relevance == 0


class TestGoldenQuery:
    def _make(self, **kw):
        defaults = dict(
            query_id="q1",
            dataset_id="open_ragbench",
            query_text="What is X?",
            qrels=[GoldenQrel(chunk_id="open_ragbench:2401.00001v1:1", relevance=2)],
        )
        defaults.update(kw)
        return GoldenQuery(**defaults)

    def test_required_fields(self):
        q = self._make()
        assert q.query_id == "q1"
        assert q.dataset_id == "open_ragbench"
        assert q.query_text == "What is X?"
        assert len(q.qrels) == 1

    def test_defaults(self):
        q = self._make()
        assert q.reference_answer is None
        assert q.meta == {}

    def test_with_answer_and_meta(self):
        q = self._make(reference_answer="42", meta={"type": "extractive"})
        assert q.reference_answer == "42"
        assert q.meta["type"] == "extractive"

    def test_serialisation_roundtrip(self):
        q = self._make(reference_answer="answer", meta={"kpi": "revenue"})
        restored = GoldenQuery.model_validate_json(q.model_dump_json())
        assert restored == q

    def test_multiple_qrels(self):
        q = self._make(qrels=[
            GoldenQrel(chunk_id="ledger:NYSE_SHW_2017:0003", relevance=2),
            GoldenQrel(chunk_id="ledger:NYSE_SHW_2017:0020", relevance=0),
        ])
        assert len(q.qrels) == 2


# ---------------------------------------------------------------------------
# load_open_ragbench_golden (with fake files in tmp_path)
# ---------------------------------------------------------------------------

def _write_orb_fixtures(base: Path) -> Path:
    d = base / "open_ragbench" / "pdf" / "arxiv"
    d.mkdir(parents=True)
    (d / "queries.json").write_text(json.dumps({
        "q-uuid-1": {"query": "What is X?", "type": "abstractive", "source": "text"},
        "q-uuid-2": {"query": "What is Y?", "type": "extractive", "source": "text-image"},
        "q-uuid-3": {"query": "What is Z?", "type": "abstractive", "source": "table"},
    }), encoding="utf-8")
    (d / "qrels.json").write_text(json.dumps({
        "q-uuid-1": {"doc_id": "2401.00001v1", "section_id": 3},
        "q-uuid-2": {"doc_id": "2401.00002v1", "section_id": 10},
        # q-uuid-3 intentionally missing → should be skipped
    }), encoding="utf-8")
    (d / "answers.json").write_text(json.dumps({
        "q-uuid-1": "X is the variable.",
        "q-uuid-2": "Y is the parameter.",
    }), encoding="utf-8")
    return base


class TestLoadOpenRagbenchGolden:
    def test_count(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        qs = load_open_ragbench_golden(tmp_path)
        assert len(qs) == 2  # q-uuid-3 skipped (no qrel)

    def test_dataset_id(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        for q in load_open_ragbench_golden(tmp_path):
            assert q.dataset_id == "open_ragbench"

    def test_chunk_id_format(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_open_ragbench_golden(tmp_path)}
        assert qs["q-uuid-1"].qrels[0].chunk_id == "open_ragbench:2401.00001v1:3"
        assert qs["q-uuid-2"].qrels[0].chunk_id == "open_ragbench:2401.00002v1:10"

    def test_single_qrel_per_query(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        for q in load_open_ragbench_golden(tmp_path):
            assert len(q.qrels) == 1

    def test_relevance_is_2(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        for q in load_open_ragbench_golden(tmp_path):
            assert q.qrels[0].relevance == 2

    def test_reference_answer(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_open_ragbench_golden(tmp_path)}
        assert qs["q-uuid-1"].reference_answer == "X is the variable."

    def test_meta_type_source(self, tmp_path):
        _write_orb_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_open_ragbench_golden(tmp_path)}
        assert qs["q-uuid-1"].meta["type"] == "abstractive"
        assert qs["q-uuid-2"].meta["source"] == "text-image"


# ---------------------------------------------------------------------------
# load_ledger_golden (with fake parquet in tmp_path)
# ---------------------------------------------------------------------------

def _write_ledger_fixtures(base: Path) -> Path:
    import pandas as pd

    d = base / "ledger" / "eval"
    d.mkdir(parents=True)

    qrels_1 = [
        {"doc_id": "NYSE_SHW_2017/page_0003", "relevance": 0},
        {"doc_id": "NYSE_SHW_2017/page_0020", "relevance": 2},
    ]
    qrels_2 = [
        {"doc_id": "NASDAQ_AMTX_2019/page_0012", "relevance": 1},
    ]
    df = pd.DataFrame([
        {
            "query_id": "SHW_revenue_2017",
            "query_text": "What is SHW revenue in 2017?",
            "ticker": "SHW",
            "exchange": "NYSE",
            "company_name": "Sherwin-Williams",
            "industry": "Chemicals",
            "year": 2017,
            "kpi": "revenue",
            "value": 14984000000.0,
            "qrels": qrels_1,
        },
        {
            "query_id": "AMTX_capex_2019",
            "query_text": "What is AMTX capex in 2019?",
            "ticker": "AMTX",
            "exchange": "NASDAQ",
            "company_name": "Aemetis Inc",
            "industry": "Energy",
            "year": 2019,
            "kpi": "capex",
            "value": 5000000.0,
            "qrels": qrels_2,
        },
    ])
    df.to_parquet(d / "data-00000-of-00001.parquet", index=False)
    return base


class TestLoadLedgerGolden:
    def test_count(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        qs = load_ledger_golden(tmp_path)
        assert len(qs) == 2

    def test_dataset_id(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        for q in load_ledger_golden(tmp_path):
            assert q.dataset_id == "ledger"

    def test_chunk_id_format(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_ledger_golden(tmp_path)}
        chunk_ids = [qr.chunk_id for qr in qs["SHW_revenue_2017"].qrels]
        assert "ledger:NYSE_SHW_2017:0003" in chunk_ids
        assert "ledger:NYSE_SHW_2017:0020" in chunk_ids

    def test_relevance_values(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_ledger_golden(tmp_path)}
        rel_map = {qr.chunk_id: qr.relevance for qr in qs["SHW_revenue_2017"].qrels}
        assert rel_map["ledger:NYSE_SHW_2017:0003"] == 0
        assert rel_map["ledger:NYSE_SHW_2017:0020"] == 2

    def test_meta_fields(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_ledger_golden(tmp_path)}
        meta = qs["SHW_revenue_2017"].meta
        assert meta["ticker"] == "SHW"
        assert meta["kpi"] == "revenue"
        assert meta["year"] == 2017

    def test_reference_answer(self, tmp_path):
        _write_ledger_fixtures(tmp_path)
        qs = {q.query_id: q for q in load_ledger_golden(tmp_path)}
        assert qs["AMTX_capex_2019"].reference_answer == "5000000"


# ---------------------------------------------------------------------------
# save_golden + validate_golden_file
# ---------------------------------------------------------------------------

class TestSaveAndValidate:
    def _sample_queries(self) -> list[GoldenQuery]:
        return [
            GoldenQuery(
                query_id=f"q{i}",
                dataset_id="open_ragbench",
                query_text=f"Query {i}?",
                qrels=[GoldenQrel(chunk_id=f"open_ragbench:doc:{i}", relevance=2)],
                reference_answer=f"Answer {i}",
            )
            for i in range(5)
        ]

    def test_saves_correct_count(self, tmp_path):
        out = tmp_path / "test.jsonl"
        qs = self._sample_queries()
        save_golden(qs, out)
        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 5

    def test_each_line_valid_json(self, tmp_path):
        out = tmp_path / "test.jsonl"
        save_golden(self._sample_queries(), out)
        for line in out.read_text(encoding="utf-8").splitlines():
            obj = json.loads(line)
            assert "query_id" in obj
            assert "qrels" in obj

    def test_validate_returns_count(self, tmp_path):
        out = tmp_path / "test.jsonl"
        save_golden(self._sample_queries(), out)
        assert validate_golden_file(out) == 5

    def test_validate_raises_on_answerable_with_empty_qrels(self, tmp_path):
        out = tmp_path / "test.jsonl"
        # answerable=True (default) with empty qrels → error
        out.write_text('{"query_id": "q1", "dataset_id": "x", "query_text": "Q?", "qrels": [], "answerable": true}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="empty qrels"):
            validate_golden_file(out)

    def test_validate_accepts_unanswerable_with_empty_qrels(self, tmp_path):
        out = tmp_path / "test.jsonl"
        out.write_text('{"query_id": "q1", "dataset_id": "x", "query_text": "Q?", "qrels": [], "answerable": false}\n', encoding="utf-8")
        assert validate_golden_file(out) == 1

    def test_validate_raises_on_missing_field(self, tmp_path):
        out = tmp_path / "test.jsonl"
        out.write_text('{"query_id": "q1"}\n', encoding="utf-8")
        with pytest.raises(ValueError):
            validate_golden_file(out)

    def test_creates_parent_dir(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "golden.jsonl"
        save_golden(self._sample_queries(), out)
        assert out.exists()
