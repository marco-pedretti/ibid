"""Collection Stats — what is actually indexed in Qdrant."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import src.config as cfg
from dashboard.components import dataframe
from dashboard.state import GOLDEN_DIR, client


def _render_collection(qc, name: str) -> None:
    with st.expander(f"**{name}**", expanded=True):
        try:
            info = qc.get_collection(name)
        except Exception as e:
            st.error(f"Errore per collection `{name}`: {e}")
            return

        points = info.points_count or 0
        vectors = getattr(info, "vectors_count", None)
        c = st.columns(2)
        c[0].metric("Punti (chunk)", f"{points:,}")
        c[1].metric("Vettori totali", f"{vectors:,}" if vectors is not None else "—")

        vconf = info.config.params.vectors
        if isinstance(vconf, dict):
            rows = [
                {
                    "nome": vname,
                    "dimensione": getattr(vparams, "size", "—"),
                    "distanza": str(getattr(vparams, "distance", "—")),
                }
                for vname, vparams in vconf.items()
            ]
            if rows:
                dataframe(pd.DataFrame(rows), hide_index=True)

        sparse = getattr(info.config.params, "sparse_vectors", None)
        if sparse:
            st.write(f"**Sparse vectors:** {list(sparse.keys())}")


def render() -> None:
    st.title("Collection Stats")
    st.caption(f"Qdrant: `{cfg.QDRANT_URL}`")

    try:
        qc = client()
        cols = qc.get_collections().collections
    except Exception as e:
        st.error(f"Impossibile connettersi a Qdrant: {e}")
        st.stop()

    if not cols:
        st.warning("Nessuna collection trovata. Esegui `make ingest` per indicizzare.")
        st.stop()

    for info in sorted(cols, key=lambda c: c.name):
        _render_collection(qc, info.name)

    st.divider()
    st.caption("File golden disponibili:")
    for path in sorted(GOLDEN_DIR.glob("*.jsonl")):
        n = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        st.write(f"- `{path.name}` — {n:,} query")
