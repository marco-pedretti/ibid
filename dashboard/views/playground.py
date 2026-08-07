"""Retrieval Playground — one query, any collection, any retrieval mode.

The A/B tab is the point: it is the only place where `ledger` and
`ledger_routed` can be put side by side on the same query, which is what the
R-07 ablation actually claims something about.
"""

from __future__ import annotations

import streamlit as st

import src.config as cfg
from dashboard.components import render_hits
from dashboard.golden_store import example_queries
from dashboard.retrieval_probe import (
    RETRIEVAL_MODES,
    ProbeConfig,
    compare_hits,
    dataset_of_collection,
)
from dashboard.state import KNOWN_DATASETS, collections, load_golden, run_probe

FREE = "— inserisci query libera —"


def _config_picker(key_prefix: str, colls: list[str], top_k: int,
                   default_index: int = 0) -> ProbeConfig:
    return ProbeConfig(
        collection=st.selectbox("Collection", colls, index=default_index,
                                key=f"{key_prefix}_coll"),
        retrieval_mode=st.selectbox("Modalità", RETRIEVAL_MODES, key=f"{key_prefix}_mode"),
        rerank=st.checkbox("Rerank (R-02)", key=f"{key_prefix}_rerank"),
        top_k=top_k,
    )


def _render_single_tab(colls: list[str], top_k: int, query_text: str) -> None:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        coll = st.selectbox("Collection", colls, key="single_coll")
    with c2:
        mode = st.selectbox("Modalità", RETRIEVAL_MODES, key="single_mode")
    with c3:
        do_rerank = st.checkbox("Rerank (R-02)", key="single_rerank")

    conf = ProbeConfig(collection=coll, retrieval_mode=mode,
                       rerank=do_rerank, top_k=top_k)
    with st.spinner(f"Retrieval — {conf.label()}…"):
        try:
            render_hits(run_probe(query_text, conf))
        except Exception as e:
            st.error(f"Errore: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")


def _render_ab_tab(colls: list[str], top_k: int, query_text: str) -> None:
    st.caption(
        "Due configurazioni qualsiasi sulla stessa query — per esempio "
        "`ledger` contro `ledger_routed`, che è l'ablation R-07."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### A")
        conf_a = _config_picker("a", colls, top_k, 0)
    with col_b:
        st.markdown("#### B")
        conf_b = _config_picker("b", colls, top_k, min(1, len(colls) - 1))

    if not st.button("Confronta", type="primary"):
        return

    try:
        with st.spinner("Retrieval A…"):
            hits_a = run_probe(query_text, conf_a)
        with st.spinner("Retrieval B…"):
            hits_b = run_probe(query_text, conf_b)
    except Exception as e:
        st.error(f"Errore: {e}")
        return

    cmp = compare_hits(hits_a, hits_b)
    st.divider()
    m = st.columns(3)
    m[0].metric("Chunk in comune", f"{len(cmp.shared)}/{len(hits_a)}")
    m[1].metric("Jaccard chunk", f"{cmp.jaccard:.2f}")
    m[2].metric("Jaccard documento", f"{cmp.doc_jaccard:.2f}")

    if cmp.jaccard == 0.0 and cmp.doc_jaccard > 0:
        st.info(
            "Zero chunk in comune ma documenti condivisi: le due collection usano "
            "pipeline di chunking diverse, quindi i `chunk_id` non coincidono per "
            "costruzione. Solo il livello documento è confrontabile — è la ragione "
            "per cui R-07 si legge su doc_R@5.",
            icon="ℹ️",
        )
    if cmp.shared_docs:
        st.caption("Documenti trovati da entrambe: "
                   + ", ".join(f"`{d}`" for d in cmp.shared_docs))

    res_a, res_b = st.columns(2)
    with res_a:
        st.markdown(f"### A — {conf_a.label()}")
        render_hits(hits_a, show_scores_chart=False, highlight=set(cmp.shared))
    with res_b:
        st.markdown(f"### B — {conf_b.label()}")
        render_hits(hits_b, show_scores_chart=False, highlight=set(cmp.shared))


def render() -> None:
    st.title("Retrieval Playground")

    colls = collections()
    if not colls:
        st.error(
            f"Nessuna collection su `{cfg.QDRANT_URL}`. "
            "Avvia Qdrant e lancia `make ingest`."
        )
        st.stop()

    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)

    dataset = dataset_of_collection(colls[0], KNOWN_DATASETS)
    with st.spinner("Carico esempi dal golden set…"):
        golden = load_golden(dataset)
    examples = example_queries(golden, n=6)

    choice = st.selectbox(
        f"Esempio (golden set {dataset}):",
        [FREE] + examples,
        format_func=lambda x: x[:110] if x != FREE else x,
    )
    query_text = st.text_input("Query libera:", value=choice if choice != FREE else "")

    if not query_text:
        st.info("Seleziona un esempio o scrivi una query.")
        st.stop()

    tab_single, tab_ab = st.tabs(["Config singola", "A/B fra due config"])
    with tab_single:
        _render_single_tab(colls, top_k, query_text)
    with tab_ab:
        _render_ab_tab(colls, top_k, query_text)
