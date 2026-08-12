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

The parsing itself lives in `src/ingestion/ocr_tables.py`: it is also what the
C-03 entailment verifier needs to read a table premise, and the library must not
depend on the dashboard.  What stays here is the Streamlit half.

Splitting reuses `_split_segments` from the table_heavy ingestion pipeline, so
what the dashboard shows as one table is exactly what ingestion treated as one
atomic chunk.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ingestion.ocr_tables import parse_html_table, table_density
from src.ingestion.pipeline_table_heavy import _split_segments


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
