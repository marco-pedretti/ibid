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

Il parsing vive in `src/ingestion/ocr_tables.py`: serve anche al verificatore di
entailment di C-03 per leggere una premessa tabellare, e la libreria non deve
dipendere dalla dashboard. Qui resta la metà Streamlit.

**È l'unico import da `src.` rimasto in questo pacchetto insieme ai contratti
dati**, ed è deliberato: leggere il markup di una tabella OCR non è eseguire la
pipeline, è interpretare un formato. Vedi la nota su A-06 in ROADMAP §11.

La suddivisione usa `split_segments` di `ocr_tables`, così ciò che la dashboard
mostra come una tabella è esattamente ciò che l'ingestione ha trattato come un
chunk atomico. Da A-06 quella funzione è pubblica e sta accanto al parser invece
che dentro la pipeline: la importavano in sei, e quattro da fuori l'ingestione.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ingestion.ocr_tables import parse_html_table, split_segments, table_density


def render_chunk(text: str, max_chars: int | None = None) -> None:
    """Render chunk text, turning inline `<table>` blocks into real tables.

    `max_chars` caps each prose segment.  It is applied per segment rather than
    to the whole string so a cap can never land inside a table block and leave
    half a tag on screen.
    """
    if not text:
        st.markdown("*(testo assente)*")
        return

    for kind, segment in split_segments(text):
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
