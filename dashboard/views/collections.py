"""Collection Stats — cosa è indicizzato, letto dal backend.

Prima di A-06 questa pagina apriva un client Qdrant e ne leggeva la
configurazione interna. Era la vista che più somigliava a una console di
amministrazione di un altro servizio — e Qdrant la sua console ce l'ha già,
su `:6333/dashboard`.

Quel che resta è ciò che riguarda **questo** sistema: quanti chunk ci sono, con
che dimensione di vettore sono stati costruiti, e se la collection ha anche
l'indice sparso. Sono i tre fatti che dicono se l'indice è quello che si crede,
ed è il motivo per cui `/datasets` li riporta.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import api_client
from dashboard.components import dataframe
from dashboard.state import GOLDEN_DIR, capabilities


def render() -> None:
    st.title("Collection Stats")
    st.caption(f"Backend: `{api_client.BASE_URL}`")

    caps = capabilities()
    if caps is None:
        st.error(
            f"Il backend non risponde su `{api_client.BASE_URL}`.\n\n"
            "Avvialo con `make api-local` (oppure `make api` in container), "
            "o imposta `IBID_API_URL` se gira altrove."
        )
        st.stop()

    if not caps.collections:
        st.warning("Nessuna collection trovata. Esegui `make ingest` per indicizzare.")
        st.stop()

    #: I dataset del registro, per marcare quali collection sono "quelle note".
    del_registro = set(caps.dataset_ids)

    dataframe(
        pd.DataFrame([
            {
                "collection": c["name"],
                "nel registro": "sì" if c["name"] in del_registro else "n/d",
                "punti": f"{c['points']:,}",
                "dim. densa": c["dense_size"],
                "sparso": "sì" if c["has_sparse"] else "**no**",
            }
            for c in caps.collections
        ]),
        hide_index=True,
    )

    # Una dimensione diversa fra due collection è l'errore più silenzioso
    # possibile: interrogare un indice con un embedder diverso da quello che
    # l'ha costruito restituisce risultati plausibili e privi di senso.
    dimensioni = {c["dense_size"] for c in caps.collections if c["dense_size"]}
    if len(dimensioni) > 1:
        st.warning(
            f"Dimensioni dense diverse fra collection: {sorted(dimensioni)}. "
            "Sono state costruite con modelli di embedding diversi, e non sono "
            "confrontabili fra loro."
        )

    senza_sparso = [c["name"] for c in caps.collections if not c["has_sparse"]]
    if senza_sparso:
        st.caption(
            "Senza indice sparso (su queste `hybrid` userebbe solo il ramo denso): "
            + ", ".join(f"`{n}`" for n in senza_sparso)
        )

    st.divider()
    st.caption("File golden disponibili:")
    for path in sorted(GOLDEN_DIR.glob("*.jsonl")):
        n = sum(1 for line in path.open(encoding="utf-8") if line.strip())
        st.write(f"- `{path.name}`: {n:,} query")
