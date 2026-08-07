"""Render a chunk's text the way it is actually structured.

LEDGER chunks are Mathpix OCR output: prose with raw `<table>` blocks inline.
`st.markdown` escapes HTML, so those blocks arrive on screen as a wall of
`</td><td>` — unreadable, and worse, it hides the thing you opened the chunk to
look at.

Two ways to fix that, and this module takes the second:

  1. `st.markdown(..., unsafe_allow_html=True)` — one line, but it executes
     whatever markup the corpus contains. The corpus is third-party data today
     and user-uploaded documents under X-01, so that is a script-injection path
     into an internal tool. Rejected.
  2. Parse the table and hand the *values* to `st.dataframe`. The markup never
     reaches the browser as markup, and the result is a real sortable table.

Parsing uses `html.parser` from the standard library rather than
lxml/beautifulsoup: the tables are flat `<tr><td>` from OCR, no dependency is
worth adding for that, and STACK.md requires a license review for every new one.
(`bs4` happens to be importable here as a transitive dependency of something
else — relying on that would be borrowing a package the project never declared.)

Splitting reuses `_split_segments` from the table_heavy ingestion pipeline, so
what the dashboard shows as one table is exactly what ingestion treated as one
atomic chunk.
"""

from __future__ import annotations

from html.parser import HTMLParser

import pandas as pd
import streamlit as st

from src.ingestion.pipeline_table_heavy import _split_segments


class _TableParser(HTMLParser):
    """Collect `<tr>`/`<td>` contents as a list of rows.

    Deliberately forgiving: OCR output has unclosed tags and stray whitespace,
    and a debug view that refuses to show a malformed table is useless exactly
    when you need it most.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:  # cell outside any row
                self._row = []
            if self._cell is not None:  # previous cell never closed — flush it
                self._row.append("".join(self._cell).strip())
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:  # unclosed final cell
                self._row.append("".join(self._cell).strip())
                self._cell = None
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def close(self) -> None:  # noqa: D102
        super().close()
        if self._row:  # unclosed final row
            if self._cell is not None:
                self._row.append("".join(self._cell).strip())
            self.rows.append(self._row)
            self._row = None


def parse_html_table(html: str) -> list[list[str]]:
    """Table markup -> rows of cell text. Empty list when nothing parses.

    Rows are padded to equal width so ragged tables (colspan, missing cells)
    still form a rectangle.  Padding rather than dropping: a missing cell is
    information about the OCR, not something to hide.
    """
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    rows = parser.rows
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def table_density(rows: list[list[str]]) -> float:
    """Fraction of cells that are empty.

    Surfaced in the caption because it is diagnostic, not cosmetic: the LEDGER
    tables that routing sub-chunks most aggressively are also the emptiest, and
    a chunk that is mostly blank cells has very little for an embedding model to
    hold on to.  Worth seeing while reading a failure.
    """
    total = sum(len(r) for r in rows)
    if not total:
        return 0.0
    return sum(1 for r in rows for c in r if not c.strip()) / total


def render_chunk(text: str, max_chars: int | None = None) -> None:
    """Render chunk text, turning inline `<table>` blocks into real tables.

    `max_chars` caps each prose segment.  It is applied per segment rather than
    to the whole string so a cap can never land inside a table block and leave
    half a tag on screen.
    """
    if not text:
        st.markdown("*(testo assente)*")
        return

    for kind, segment in _split_segments(text):
        if kind == "text":
            body = segment if max_chars is None else segment[:max_chars]
            if max_chars is not None and len(segment) > max_chars:
                body += " …"
            st.markdown(body)
            continue

        rows = parse_html_table(segment)
        if not rows:
            # Never silently drop content: show the markup rather than nothing.
            st.caption("Tabella non interpretabile — markup grezzo:")
            st.code(segment[:2000], language="html")
            continue

        df = pd.DataFrame(rows)
        df.columns = [str(i) for i in range(df.shape[1])]
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption(
            f"{df.shape[0]} righe × {df.shape[1]} colonne · "
            f"{table_density(rows):.0%} celle vuote"
        )
