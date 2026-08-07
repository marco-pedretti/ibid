"""Failure Explorer — batch a golden slice, ranked worst-first.

Queries that succeed teach nothing, so the default view is the failures, and
the expected chunk is shown next to what actually came back: without both, a
bad retrieval and a bad label look identical.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import src.config as cfg
from dashboard.chunk_render import render_chunk
from dashboard.components import render_hits
from dashboard.failure_store import (
    chunk_id_mismatch,
    evaluate_queries,
    failure_summary,
    sort_by_failure,
)
from dashboard.retrieval_probe import (
    RETRIEVAL_MODES,
    ProbeConfig,
    ProbeHit,
    dataset_of_collection,
    fetch_chunks_by_id,
)
from dashboard.state import KNOWN_DATASETS, client, collections, load_golden


def _run_batch(subset, conf) -> list | None:
    bar = st.progress(0.0, text="Retrieval…")
    try:
        outcomes = evaluate_queries(
            client(), subset, conf,
            on_progress=lambda i, n: bar.progress(i / n, text=f"Scoring {i}/{n}"),
        )
    except Exception as e:
        bar.empty()
        st.error(f"Errore: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")
        return None
    bar.empty()
    return outcomes


def _render_summary(outcomes) -> None:
    s = failure_summary(outcomes)
    c = st.columns(4)
    c[0].metric("Query", int(s["n"]))
    c[1].metric("Recall chunk medio", f"{s['mean_recall']:.3f}")
    c[2].metric("Recall doc medio", f"{s['mean_doc_recall']:.3f}")
    c[3].metric("Fallimenti totali", int(s["n_failures"]),
                delta=f"{s['failure_rate']:.0%}", delta_color="inverse")

    if chunk_id_mismatch(outcomes):
        st.info(
            "Recall chunk 0 su tutte le query ma documenti trovati: i `chunk_id` di "
            "questa collection non coincidono con quelli dei qrels, perché è stata "
            "costruita con una pipeline di chunking diversa. Leggi il **recall "
            "documento**, non quello chunk — è la stessa ragione per cui R-07 si "
            "misura su doc_R@5.",
            icon="ℹ️",
        )


def _render_detail(outcome, collection: str) -> None:
    st.divider()
    st.markdown(f"### {outcome.query.query_text}")
    i = st.columns(3)
    i[0].metric("Recall chunk", f"{outcome.recall:.2f}")
    i[1].metric("Recall doc", f"{outcome.doc_recall:.2f}")
    i[2].metric("Query ID", outcome.query.query_id)
    if outcome.query.reference_answer:
        st.info(f"**Risposta attesa:** {outcome.query.reference_answer}")

    col_exp, col_got = st.columns(2)

    with col_exp:
        st.markdown("#### Atteso (golden qrels)")
        golden_ids = sorted(outcome.golden_ids)
        try:
            texts = fetch_chunks_by_id(client(), collection, golden_ids)
        except Exception as e:
            texts = {}
            st.caption(f"(testo non recuperabile: {e})")
        for cid in golden_ids:
            payload = texts.get(cid)
            label = f"`{cid}`" + ("" if payload else "  ⚠️ assente")
            with st.expander(label, expanded=True):
                if payload:
                    st.caption(
                        f"{payload.get('doc_id', '?')} · "
                        f"{payload.get('content_type', '?')} · "
                        f"{len(payload.get('text', ''))} caratteri"
                    )
                    # Il cap va per segmento, non sulla stringa intera: tagliare
                    # a 2000 caratteri secchi cadeva dentro un tag <table>.
                    render_chunk(payload.get("text", ""), max_chars=2000)
                else:
                    st.warning(
                        f"Questo `chunk_id` non esiste in `{collection}`: il qrel è "
                        "stato scritto contro una collection con chunking diverso. "
                        "Non è un errore di retrieval.",
                        icon="⚠️",
                    )

    with col_got:
        st.markdown("#### Recuperato")
        hits = [
            ProbeHit(rank=n, chunk_id=cid, score=sc, payload=pl)
            for n, (cid, sc, pl) in enumerate(
                zip(outcome.retrieved_ids, outcome.scores, outcome.payloads), 1
            )
        ]
        render_hits(hits, show_scores_chart=False, golden_ids=outcome.golden_ids)


def render() -> None:
    st.title("Failure Explorer")
    st.caption(
        "Esegue un batch di query golden e le ordina dalla peggiore. "
        "Le query che funzionano non spiegano niente."
    )

    colls = collections()
    if not colls:
        st.error(f"Nessuna collection su `{cfg.QDRANT_URL}`.")
        st.stop()

    coll = st.sidebar.selectbox("Collection", colls)
    dataset = dataset_of_collection(coll, KNOWN_DATASETS)
    st.sidebar.caption(f"Golden set: `{dataset}`")
    mode = st.sidebar.selectbox("Modalità", RETRIEVAL_MODES)
    do_rerank = st.sidebar.checkbox("Rerank (R-02)")
    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)
    n_queries = st.sidebar.slider(
        "Query da eseguire", min_value=10, max_value=500, value=50, step=10,
        help="Un batch, non l'intero golden set: la dashboard è uno strumento di "
             "debug, la misura ufficiale la fa scripts/eval.py.",
    )

    with st.spinner(f"Carico golden {dataset}…"):
        golden = load_golden(dataset)
    if not golden:
        st.warning(
            f"Nessuna query per {dataset}. "
            f"Esegui `python scripts/build_golden.py --dataset {dataset}`."
        )
        st.stop()

    answerable = [q for q in golden if q.answerable and q.qrels]
    st.caption(
        f"{len(answerable):,} query rispondibili su {len(golden):,} totali nel golden set."
    )

    conf = ProbeConfig(collection=coll, retrieval_mode=mode,
                       rerank=do_rerank, top_k=top_k)

    if st.button(f"Esegui {n_queries} query — {conf.label()}", type="primary"):
        outcomes = _run_batch(answerable[:n_queries], conf)
        if outcomes is None:
            st.stop()
        # Un solo oggetto: le tre informazioni descrivono lo stesso batch e
        # tenerle in chiavi separate le lascia divergere.
        st.session_state["batch"] = {
            "outcomes": outcomes, "label": conf.label(), "collection": coll,
        }

    batch = st.session_state.get("batch") or {}
    outcomes = batch.get("outcomes")
    if not outcomes:
        st.info("Premi il bottone per eseguire il batch.")
        st.stop()

    st.divider()
    st.subheader(f"Risultati — {batch['label']}")
    _render_summary(outcomes)

    ranked = sort_by_failure(outcomes)
    only_failures = st.checkbox("Mostra solo i fallimenti (recall doc = 0)", value=True)
    shown = [o for o in ranked if o.is_failure] if only_failures else ranked
    if not shown:
        st.success("Nessun fallimento in questo batch.")
        st.stop()

    df = pd.DataFrame({
        "query": [o.query.query_text[:100] for o in shown],
        "recall_chunk": [o.recall for o in shown],
        "recall_doc": [o.doc_recall for o in shown],
        "top_score": [o.top_score for o in shown],
        "n_qrels": [len(o.query.qrels) for o in shown],
    })
    df.index.name = "#"
    # Questa tabella e larga di suo: qui lo stretch aiuta invece di allontanare
    # i valori dalle etichette.
    event = st.dataframe(df, width="stretch", selection_mode="single-row",
                         on_select="rerun", height=300)

    rows = event.selection.rows if event.selection else []
    if not rows:
        st.info("Clicca una riga per confrontare atteso e recuperato.")
        st.stop()

    _render_detail(shown[rows[0]], batch["collection"])
