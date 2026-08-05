"""D-01: Internal Streamlit dashboard.

Two features accessible from the sidebar:
  1. EvalRun Comparator — select ≥ 2 EvalRun JSONs from eval/results/ and compare
     metrics side-by-side with delta highlighting.
  2. Chunk Inspector — free-form query against open_ragbench or ledger; shows
     retrieved chunks with score, doc_id, section_path, and text preview.

Usage:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

import src.config as cfg
from dashboard.eval_store import compare_table, load_eval_runs, run_label

RESULTS_DIR = ROOT / "eval" / "results"

st.set_page_config(page_title="ibid — dashboard interna", layout="wide")
st.sidebar.title("ibid dashboard")
page = st.sidebar.selectbox("Pagina", ["EvalRun Comparator", "Chunk Inspector"])

# =============================================================================
# PAGE 1 — EvalRun Comparator
# =============================================================================
if page == "EvalRun Comparator":
    st.title("EvalRun Comparator")
    st.caption(f"Fonte: `{RESULTS_DIR.relative_to(ROOT)}`")

    runs = load_eval_runs(RESULTS_DIR)
    if not runs:
        st.warning(
            "Nessun EvalRun trovato. Esegui prima `make eval` o `make eval-generation`."
        )
        st.stop()

    labels = [run_label(r) for r in runs]
    label_to_run = dict(zip(labels, runs))

    selected_labels: list[str] = st.multiselect(
        "Seleziona ≥ 2 run da confrontare",
        options=labels,
        default=labels[: min(2, len(labels))],
    )

    if len(selected_labels) < 2:
        st.info("Seleziona almeno 2 run per confrontarli.")
        st.stop()

    selected_runs = [label_to_run[lbl] for lbl in selected_labels]

    # Metadata cards
    meta_cols = st.columns(len(selected_runs))
    for col, run in zip(meta_cols, selected_runs):
        with col:
            st.markdown(f"**{run_label(run)}**")
            st.json(
                {
                    "dataset": run.dataset_id,
                    "pipeline": run.pipeline_mode,
                    "model": run.model,
                    "commit": run.git_commit[:7],
                    "temperature": run.temperature,
                    "context_window": run.context_window,
                }
            )

    st.divider()
    st.subheader("Metriche")

    table = compare_table(selected_runs)
    short_labels = [run_label(r) for r in selected_runs]
    df = pd.DataFrame(table, index=short_labels).T
    df.index.name = "Metric"

    st.dataframe(
        df.style.highlight_max(axis=1, color="#d4edda").highlight_min(
            axis=1, color="#f8d7da"
        ),
        use_container_width=True,
    )

    # Delta column when exactly 2 runs selected
    if len(selected_runs) == 2:
        st.subheader("Delta (run 2 − run 1)")
        delta = {
            m: vals[1] - vals[0]
            for m, vals in table.items()
            if not any(__import__("math").isnan(v) for v in vals)
        }
        delta_df = pd.DataFrame(
            {"Metric": list(delta.keys()), "Δ": list(delta.values())}
        ).set_index("Metric")
        st.dataframe(
            delta_df.style.applymap(
                lambda v: "color: green" if v > 0 else ("color: red" if v < 0 else ""),
                subset=["Δ"],
            ),
            use_container_width=True,
        )

# =============================================================================
# PAGE 2 — Chunk Inspector
# =============================================================================
else:
    st.title("Chunk Inspector")

    dataset = st.sidebar.selectbox("Dataset", ["open_ragbench", "ledger"])
    retrieval_mode = st.sidebar.radio("Retrieval mode", ["dense", "sparse"])
    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)

    query_text = st.text_input(
        "Query", placeholder="Es. What is the standard deviation of RMSE for Ridge Regression?"
    )

    if not query_text:
        st.info("Scrivi una query per recuperare i chunk.")
        st.stop()

    with st.spinner("Embedding + ricerca Qdrant…"):
        try:
            from src.index.embed import encode, encode_sparse
            from src.index.store import get_client, search

            client = get_client(cfg.QDRANT_URL)

            if retrieval_mode == "dense":
                vecs = encode([query_text], cfg.EMBEDDING_MODEL, batch_size=1)
                vec = vecs[0]
            else:
                svecs = encode_sparse([query_text], cfg.SPARSE_EMBEDDING_MODEL)
                vec = svecs[0]

            results = search(client, dataset, vec, top_k=top_k, using=retrieval_mode)
        except Exception as exc:
            st.error(f"Errore di retrieval: {exc}\n\nQdrant in ascolto su `{cfg.QDRANT_URL}`?")
            st.stop()

    if not results:
        st.warning("Nessun risultato. Il dataset è indicizzato in Qdrant?")
        st.stop()

    st.success(
        f"{len(results)} chunk recuperati da **{dataset}** (mode=`{retrieval_mode}`, top_k={top_k})"
    )

    for i, r in enumerate(results):
        p = r.payload or {}
        score = r.score
        header = (
            f"#{i + 1} | score={score:.4f} | {p.get('doc_id', '?')} "
            f"| {p.get('content_type', '?')}"
        )
        with st.expander(header, expanded=(i == 0)):
            if p.get("section_path"):
                st.caption(f"Sezione: {p['section_path']}")
            if p.get("page"):
                st.caption(f"Pagina: {p['page']}")
            st.markdown(p.get("text", "*(testo assente)*"))
