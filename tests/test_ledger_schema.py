"""Schema validation for LEDGER loader (no network required)."""

from __future__ import annotations

import tempfile
from pathlib import Path


from src.datasets.ledger import PAGE_SEP, _content_type, _parse_doc_id, iter_chunks, qrel_doc_id
from src.datasets.schema import PIPELINE_GENERIC
from src.datasets.schema import Chunk


# --- _parse_doc_id ---

def test_parse_doc_id_simple():
    p = Path("NYSE_SHW_2017.mmd")
    exchange, ticker, year = _parse_doc_id(p)
    assert exchange == "NYSE"
    assert ticker == "SHW"
    assert year == "2017"


def test_parse_doc_id_compound_ticker():
    # Some tickers have underscores (e.g. BRK_B would be AMEX_BRK_B_2020)
    p = Path("AMEX_BRK_B_2020.mmd")
    exchange, ticker, year = _parse_doc_id(p)
    assert exchange == "AMEX"
    assert ticker == "BRK_B"
    assert year == "2020"


# --- _content_type ---

def test_content_type_text():
    assert _content_type("This is a paragraph with enough words to count as text.") == "text"


def test_content_type_table():
    html = "<table><tr><td>Revenue</td><td>100</td></tr></table>"
    assert _content_type(html) == "table"


def test_content_type_mixed():
    page = "## Financial Highlights\n\n<table><tr><td>Revenue</td><td>100</td></tr></table>"
    assert _content_type(page) == "mixed"


def test_content_type_empty_table_no_text():
    # Short text + table → still table (plain < 30 chars after stripping HTML)
    page = "x<table><tr><td></td></tr></table>"
    # "x" is 1 char < 30 threshold → table
    assert _content_type(page) == "table"


# --- iter_chunks (offline with temp files) ---

def _make_mmd_dir(tmp_path: Path, files: dict[str, str]) -> Path:
    mmd_dir = tmp_path / "eval" / "mmd"
    mmd_dir.mkdir(parents=True)
    for name, content in files.items():
        (mmd_dir / name).write_text(content, encoding="utf-8")
    return tmp_path


def test_iter_chunks_basic():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"Cover page text here.\n{PAGE_SEP}\nPage two text here, longer content.\n{PAGE_SEP}\n<table><tr><td>Revenue</td></tr></table>",
        })
        chunks = list(iter_chunks(dataset_dir))

    assert len(chunks) == 3
    assert all(isinstance(c, Chunk) for c in chunks)


def test_iter_chunks_pipeline_says_no_pipeline_ran():
    """Il campo dice cosa ha prodotto il chunk, e qui non ha prodotto niente.

    Scriveva `doc_genre`, cioe' `table_heavy` su tutto LEDGER: lo stesso valore
    che la collection *routed* porta per davvero, dove la pipeline `table_heavy`
    gira sul serio. Le due modalita' erano indistinguibili nel payload, e il
    campo dichiarava una pipeline che non aveva girato -- la stessa famiglia di
    `reasoning_enabled` e di `context_window`.
    """
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"<table><tr><td>Revenue</td></tr></table>\n{PAGE_SEP}\nAltro testo.",
        })
        chunks = list(iter_chunks(dataset_dir))

    assert all(c.pipeline == PIPELINE_GENERIC for c in chunks)
    # Il genere resta osservato: lo calcola `assign_genre` dalle feature del
    # documento, ed e' l'ingresso della decisione di routing.
    assert all(c.doc_genre == "table_heavy" for c in chunks)
    assert all(c.pipeline != c.doc_genre for c in chunks)


def test_iter_chunks_dataset_id():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"Page one.\n{PAGE_SEP}\nPage two.",
        })
        chunks = list(iter_chunks(dataset_dir))
    assert all(c.dataset_id == "ledger" for c in chunks)


def test_iter_chunks_doc_id():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"Page one.\n{PAGE_SEP}\nPage two.",
        })
        chunks = list(iter_chunks(dataset_dir))
    assert all(c.doc_id == "NYSE_SHW_2017" for c in chunks)


def test_iter_chunks_page_numbers():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"Page one.\n{PAGE_SEP}\nPage two.\n{PAGE_SEP}\nPage three.",
        })
        chunks = list(iter_chunks(dataset_dir))
    assert [c.page for c in chunks] == [0, 1, 2]


def test_iter_chunks_skips_empty_pages():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"Page one.\n{PAGE_SEP}\n   \n{PAGE_SEP}\nPage three.",
        })
        chunks = list(iter_chunks(dataset_dir))
    # middle page is blank → skipped
    assert len(chunks) == 2


def test_iter_chunks_chunk_id_format():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": f"A page.\n{PAGE_SEP}\nAnother page.",
        })
        chunks = list(iter_chunks(dataset_dir))
    assert chunks[0].chunk_id == "ledger:NYSE_SHW_2017:0000"
    assert chunks[1].chunk_id == "ledger:NYSE_SHW_2017:0001"


def test_iter_chunks_doc_genre_table_heavy():
    # A page with HTML table → table_density=1.0 → "table_heavy"
    with tempfile.TemporaryDirectory() as td:
        page = "## Summary\n\n<table><tr><td>Revenue</td><td>100</td></tr></table>"
        dataset_dir = _make_mmd_dir(Path(td), {"NYSE_SHW_2017.mmd": page})
        chunks = list(iter_chunks(dataset_dir))
    assert chunks[0].doc_genre == "table_heavy"


def test_iter_chunks_doc_genre_continuous():
    # Plain text, short section → "continuous_text"
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {"NYSE_SHW_2017.mmd": "A page."})
        chunks = list(iter_chunks(dataset_dir))
    assert chunks[0].doc_genre == "continuous_text"


def test_iter_chunks_content_type_mixed():
    with tempfile.TemporaryDirectory() as td:
        page = "## Financial Summary\n\n<table><tr><td>Revenue</td><td>$100M</td></tr></table>"
        dataset_dir = _make_mmd_dir(Path(td), {"NYSE_SHW_2017.mmd": page})
        chunks = list(iter_chunks(dataset_dir))
    assert chunks[0].content_type == "mixed"


def test_iter_chunks_multiple_docs():
    with tempfile.TemporaryDirectory() as td:
        dataset_dir = _make_mmd_dir(Path(td), {
            "NYSE_SHW_2017.mmd": "Doc A, page 1.",
            "NASDAQ_AAPL_2022.mmd": f"Doc B, page 1.\n{PAGE_SEP}\nDoc B, page 2.",
        })
        chunks = list(iter_chunks(dataset_dir))
    doc_ids = {c.doc_id for c in chunks}
    assert doc_ids == {"NYSE_SHW_2017", "NASDAQ_AAPL_2022"}
    assert len(chunks) == 3


# --- qrel_doc_id ---

def test_qrel_doc_id_format():
    chunk = Chunk(
        chunk_id="ledger:NYSE_SHW_2017:0003",
        dataset_id="ledger",
        doc_id="NYSE_SHW_2017",
        doc_genre="table_heavy",
        pipeline="table_heavy",
        section_path="",
        page=3,
        bbox=None,
        content_type="mixed",
        text="Revenue table...",
        source_uri="ledger:NYSE:SHW:2017",
    )
    assert qrel_doc_id(chunk) == "NYSE_SHW_2017/page_0003"


def test_qrel_doc_id_page_zero():
    chunk = Chunk(
        chunk_id="ledger:NYSE_SHW_2017:0000",
        dataset_id="ledger",
        doc_id="NYSE_SHW_2017",
        doc_genre="table_heavy",
        pipeline="table_heavy",
        section_path="",
        page=0,
        bbox=None,
        content_type="text",
        text="Cover.",
        source_uri="ledger:NYSE:SHW:2017",
    )
    assert qrel_doc_id(chunk) == "NYSE_SHW_2017/page_0000"
