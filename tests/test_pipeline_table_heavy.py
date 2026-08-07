"""I-05: unit tests for the table_heavy chunking pipeline.

Acceptance criterion: no chunk contains a truncated table — verified by
checking that every chunk with '<table' also has a matching '</table>'.
"""

from __future__ import annotations

import re


from src.datasets.schema import Chunk
from src.ingestion.pipeline_table_heavy import (
    _first_heading,
    _split_segments,
    chunk_document,
)

_TABLE_OPEN_RE = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_CLOSE_RE = re.compile(r"</table>", re.IGNORECASE)

TABLE_SIMPLE = "<table><tr><td>Revenue</td><td>100</td></tr></table>"
TABLE_ATTR = '<table border="1"><tr><td>EBITDA</td><td>50</td></tr></table>'


def _no_truncated_tables(chunks: list[Chunk]) -> bool:
    """Return True if every chunk has balanced <table> / </table> tags."""
    for c in chunks:
        opens = len(_TABLE_OPEN_RE.findall(c.text))
        closes = len(_TABLE_CLOSE_RE.findall(c.text))
        if opens != closes:
            return False
    return True


# --- _split_segments ---

def test_split_no_table():
    segs = _split_segments("Just plain text.")
    assert segs == [("text", "Just plain text.")]


def test_split_only_table():
    segs = _split_segments(TABLE_SIMPLE)
    assert segs == [("table", TABLE_SIMPLE)]


def test_split_text_then_table():
    page = f"Intro paragraph.\n\n{TABLE_SIMPLE}"
    segs = _split_segments(page)
    assert segs[0] == ("text", "Intro paragraph.")
    assert segs[1][0] == "table"
    assert "<table" in segs[1][1]


def test_split_table_then_text():
    page = f"{TABLE_SIMPLE}\n\nFootnote text."
    segs = _split_segments(page)
    assert segs[0][0] == "table"
    assert segs[1] == ("text", "Footnote text.")


def test_split_two_tables():
    page = f"{TABLE_SIMPLE}\n\n{TABLE_ATTR}"
    segs = _split_segments(page)
    tables = [s for s in segs if s[0] == "table"]
    assert len(tables) == 2


def test_split_text_table_text():
    page = f"Header.\n\n{TABLE_SIMPLE}\n\nFooter."
    segs = _split_segments(page)
    kinds = [k for k, _ in segs]
    assert kinds == ["text", "table", "text"]


def test_split_discards_empty_segments():
    page = f"{TABLE_SIMPLE}{TABLE_ATTR}"  # no text between them
    segs = _split_segments(page)
    assert all(k == "table" for k, _ in segs)
    assert len(segs) == 2


def test_split_table_with_attributes():
    segs = _split_segments(TABLE_ATTR)
    assert segs[0][0] == "table"
    assert "EBITDA" in segs[0][1]


# --- _first_heading ---

def test_first_heading_found():
    assert _first_heading("## Financial Highlights\n\nSome text.") == "Financial Highlights"


def test_first_heading_strips_trailing_punctuation():
    assert _first_heading("## 3. Methods.") == "3. Methods"


def test_first_heading_not_found():
    assert _first_heading("Plain text without a heading.") == ""


def test_first_heading_level4():
    assert _first_heading("#### Abstract\n\nSummary.") == "Abstract"


def test_first_heading_uses_first_match():
    text = "## Section A\n\n## Section B"
    assert _first_heading(text) == "Section A"


# --- chunk_document ---

def _base(**overrides) -> dict:
    return {
        "doc_id": "NYSE_SHW_2017",
        "dataset_id": "ledger",
        "doc_genre": "table_heavy",
        "source_uri": "ledger:NYSE:SHW:2017",
        **overrides,
    }


def test_empty_text():
    assert chunk_document("", **_base()) == []


def test_pure_text_page():
    chunks = chunk_document("Management discussion here.", **_base())
    assert len(chunks) == 1
    assert chunks[0].content_type == "text"


def test_pure_table_page():
    chunks = chunk_document(TABLE_SIMPLE, **_base())
    assert len(chunks) == 1
    assert chunks[0].content_type == "table"


def test_table_chunk_is_atomic():
    # A big table must be a single chunk, not split.
    big_table = (
        "<table>"
        + "".join(f"<tr><td>Row {i}</td><td>{i * 1000}</td></tr>" for i in range(200))
        + "</table>"
    )
    chunks = chunk_document(big_table, **_base())
    table_chunks = [c for c in chunks if c.content_type == "table"]
    assert len(table_chunks) == 1
    assert big_table in table_chunks[0].text


def test_no_truncated_tables_mixed_page():
    page = f"## Revenue\n\n{TABLE_SIMPLE}\n\nSee footnote.\n\n{TABLE_ATTR}"
    chunks = chunk_document(page, **_base())
    assert _no_truncated_tables(chunks)


def test_two_tables_produce_two_table_chunks():
    page = f"{TABLE_SIMPLE}\n\n{TABLE_ATTR}"
    chunks = chunk_document(page, **_base())
    table_chunks = [c for c in chunks if c.content_type == "table"]
    assert len(table_chunks) == 2


def test_section_path_from_heading():
    page = f"## Financial Highlights\n\n{TABLE_SIMPLE}"
    chunks = chunk_document(page, **_base())
    table_chunk = next(c for c in chunks if c.content_type == "table")
    assert table_chunk.section_path == "Financial Highlights"


def test_section_path_updates_on_new_heading():
    page = (
        f"## Revenue\n\n{TABLE_SIMPLE}\n\n"
        f"## Assets\n\n{TABLE_ATTR}"
    )
    chunks = chunk_document(page, **_base())
    table_chunks = [c for c in chunks if c.content_type == "table"]
    assert table_chunks[0].section_path == "Revenue"
    assert table_chunks[1].section_path == "Assets"


def test_section_path_empty_when_no_heading():
    chunks = chunk_document(TABLE_SIMPLE, **_base())
    assert chunks[0].section_path == ""


def test_pipeline_field():
    chunks = chunk_document(TABLE_SIMPLE, **_base())
    assert all(c.pipeline == "table_heavy" for c in chunks)


def test_chunk_id_format():
    page = f"{TABLE_SIMPLE}\n\n{TABLE_ATTR}"
    chunks = chunk_document(page, **_base())
    assert chunks[0].chunk_id == "ledger:NYSE_SHW_2017:0000"
    assert chunks[1].chunk_id == "ledger:NYSE_SHW_2017:0001"


def test_seq_offset():
    chunks = chunk_document(TABLE_SIMPLE, **_base(), seq_offset=5)
    assert chunks[0].chunk_id == "ledger:NYSE_SHW_2017:0005"


def test_page_field():
    chunks = chunk_document(TABLE_SIMPLE, **_base(), page=7)
    assert chunks[0].page == 7


def test_long_text_sub_chunked():
    long_para = "\n\n".join(["word " * 60] * 8)
    chunks = chunk_document(long_para, **_base(), chunk_size=500, overlap=100)
    assert len(chunks) > 1
    assert all(c.content_type == "text" for c in chunks)


def test_no_truncated_tables_on_real_ledger_page():
    # Approximates a real LEDGER page structure.
    table1 = (
        "<table><tr><td>Revenues</td><td>$13,030,000</td></tr>"
        "<tr><td>Net earnings</td><td>$1,171,000</td></tr></table>"
    )
    table2 = (
        "<table><tr><td>Total assets</td><td>$33,020,000</td></tr>"
        "<tr><td>Long-term debt</td><td>-</td></tr></table>"
    )
    page = f"## FINANCIAL AND OPERATING HIGHLIGHTS\n\n{table1}\n\n{table2}\n\n* MCF = thousand cubic feet"
    chunks = chunk_document(page, **_base())
    assert _no_truncated_tables(chunks)
    table_chunks = [c for c in chunks if c.content_type == "table"]
    assert len(table_chunks) == 2
