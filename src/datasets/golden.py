"""Golden query/qrel schema and loaders for E-01.

Output format: eval/golden/{dataset_id}.jsonl
Each line is a GoldenQuery serialised as JSON.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class GoldenQrel(BaseModel):
    chunk_id: str
    relevance: int  # 0, 1, or 2


class GoldenQuery(BaseModel):
    query_id: str
    dataset_id: str
    query_text: str
    qrels: list[GoldenQrel]
    reference_answer: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_open_ragbench_golden(data_dir: Path) -> list[GoldenQuery]:
    """Load queries + qrels from open_ragbench JSON files.

    Each query has exactly one relevant chunk (relevance=2).
    chunk_id format: "open_ragbench:{doc_id}:{section_id}"
    """
    base = data_dir / "open_ragbench" / "pdf" / "arxiv"
    queries: dict[str, dict] = json.loads((base / "queries.json").read_text(encoding="utf-8"))
    qrels: dict[str, dict] = json.loads((base / "qrels.json").read_text(encoding="utf-8"))
    answers: dict[str, str] = json.loads((base / "answers.json").read_text(encoding="utf-8"))

    result: list[GoldenQuery] = []
    for qid, q in queries.items():
        qrel = qrels.get(qid)
        if qrel is None:
            continue
        chunk_id = f"open_ragbench:{qrel['doc_id']}:{qrel['section_id']}"
        result.append(
            GoldenQuery(
                query_id=qid,
                dataset_id="open_ragbench",
                query_text=q["query"],
                qrels=[GoldenQrel(chunk_id=chunk_id, relevance=2)],
                reference_answer=answers.get(qid),
                meta={"type": q.get("type", ""), "source": q.get("source", "")},
            )
        )
    return result


def load_ledger_golden(data_dir: Path) -> list[GoldenQuery]:
    """Load queries + qrels from the LEDGER parquet QA file.

    Qrel doc_ids follow "EXCHANGE_TICKER_YEAR/page_NNNN" format;
    these are converted to chunk_ids "ledger:EXCHANGE_TICKER_YEAR:NNNN".
    """
    import pandas as pd  # noqa: PLC0415

    eval_dir = data_dir / "ledger" / "eval"
    shards = sorted(eval_dir.glob("data-*-of-*.parquet"))
    if not shards:
        raise FileNotFoundError(
            f"No sharded parquet files found in {eval_dir}. "
            "Run: python scripts/build_golden.py --dataset ledger"
        )
    cols = ["query_id", "query_text", "ticker", "exchange",
            "company_name", "industry", "year", "kpi", "value", "qrels"]
    df = pd.concat([pd.read_parquet(s, columns=cols) for s in shards], ignore_index=True)

    result: list[GoldenQuery] = []
    for row in df.itertuples(index=False):
        golden_qrels: list[GoldenQrel] = []
        for qr in row.qrels:
            doc_id_str: str = qr["doc_id"]
            doc_part, page_part = doc_id_str.split("/")
            page_num = int(page_part.replace("page_", ""))
            chunk_id = f"ledger:{doc_part}:{page_num:04d}"
            golden_qrels.append(GoldenQrel(chunk_id=chunk_id, relevance=int(qr["relevance"])))

        value = row.value
        ref_answer = str(int(value)) if not (value != value) and value == int(value) else str(value)

        result.append(
            GoldenQuery(
                query_id=row.query_id,
                dataset_id="ledger",
                query_text=row.query_text,
                qrels=golden_qrels,
                reference_answer=ref_answer,
                meta={
                    "kpi": row.kpi,
                    "ticker": row.ticker,
                    "exchange": row.exchange,
                    "company_name": row.company_name,
                    "industry": row.industry,
                    "year": int(row.year),
                },
            )
        )
    return result


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def save_golden(queries: list[GoldenQuery], output_path: Path) -> None:
    """Write queries to a JSONL file, one GoldenQuery per line."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(q.model_dump_json() + "\n")


def validate_golden_file(path: Path) -> int:
    """Validate a golden JSONL file. Returns query count; raises ValueError on first bad line."""
    count = 0
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = GoldenQuery.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"Line {i}: {exc}") from exc
            if not obj.qrels:
                raise ValueError(f"Line {i}: qrels is empty for query_id={obj.query_id!r}")
            count += 1
    return count
