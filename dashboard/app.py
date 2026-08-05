"""D-01: Internal Streamlit dashboard.

Four pages:
  1. EvalRun Comparator — compare ≥2 EvalRun JSONs from eval/results/
  2. Chunk Inspector    — free-form query against open_ragbench or ledger;
                          dense, sparse, or side-by-side comparison
  3. Golden Query Browser — browse golden JSONL, filter, live retrieval + recall@k
  4. Collection Stats   — Qdrant collection point counts and vector config

Usage:
    streamlit run dashboard/app.py
    # or:  python -m streamlit run dashboard/app.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

import src.config as cfg
from dashboard.eval_store import compare_table, load_eval_runs, run_label
from dashboard.golden_store import (
    example_queries,
    filter_queries,
    load_golden_queries,
    recall_at_k,
)

RESULTS_DIR = ROOT / "eval" / "results"
GOLDEN_DIR = ROOT / "eval" / "golden"

st.set_page_config(page_title="ibid — dashboard interna", layout="wide")
st.sidebar.title("ibid")
page = st.sidebar.selectbox(
    "Pagina",
    ["EvalRun Comparator", "Chunk Inspector", "Golden Query Browser", "Collection Stats"],
)

# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load_golden(dataset: str) -> list:
    return load_golden_queries(GOLDEN_DIR / f"{dataset}.jsonl")


@st.cache_data(show_spinner=False)
def _load_runs() -> list:
    return load_eval_runs(RESULTS_DIR)


# ---------------------------------------------------------------------------
# Shared retrieval helper
# ---------------------------------------------------------------------------

def _retrieve(query_text: str, dataset: str, mode: str, top_k: int) -> list:
    """Embed query and search Qdrant. Returns list of QueryResponse."""
    from src.index.embed import encode, encode_sparse
    from src.index.store import get_client, search

    client = get_client(cfg.QDRANT_URL)
    if mode == "dense":
        vec = encode([query_text], cfg.EMBEDDING_MODEL, batch_size=1)[0]
    else:
        vec = encode_sparse([query_text], cfg.SPARSE_EMBEDDING_MODEL)[0]
    return search(client, dataset, vec, top_k=top_k, using=mode)


def _render_results(results: list, show_scores_chart: bool = True) -> None:
    """Render retrieved chunks as expandable cards with full metadata."""
    if not results:
        st.warning("Nessun risultato.")
        return

    # --- summary metrics row ---
    doc_ids = [r.payload.get("doc_id", "") for r in results]
    genres = [r.payload.get("doc_genre", "") for r in results]
    scores = [r.score for r in results]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chunk", len(results))
    c2.metric("Documenti unici", len(set(doc_ids)))
    c3.metric("Score max", f"{max(scores):.4f}")
    c4.metric("Score min", f"{min(scores):.4f}")

    # --- score decay chart ---
    if show_scores_chart and len(results) > 1:
        scores_df = pd.DataFrame(
            {"Score": scores},
            index=[f"#{i + 1}" for i in range(len(results))],
        )
        st.bar_chart(scores_df, height=140)

    # --- chunk cards ---
    for i, r in enumerate(results):
        p = r.payload or {}
        header = (
            f"#{i + 1}  score={r.score:.4f}  ·  {p.get('doc_id', '?')} "
            f"·  {p.get('content_type', '?')}  ·  {p.get('doc_genre', '?')}"
        )
        with st.expander(header, expanded=(i == 0)):
            meta_cols = st.columns(3)
            meta_cols[0].write(f"**Pipeline:** {p.get('pipeline', '—')}")
            meta_cols[1].write(f"**Pagina:** {p.get('page', '—')}")
            meta_cols[2].write(f"**content_type:** {p.get('content_type', '—')}")
            if p.get("section_path"):
                st.caption(f"Sezione: {p['section_path']}")
            st.divider()
            st.markdown(p.get("text", "*(testo assente)*"))


# =============================================================================
# PAGE 1 — EvalRun Comparator
# =============================================================================
if page == "EvalRun Comparator":
    st.title("EvalRun Comparator")
    st.caption(f"`{RESULTS_DIR.relative_to(ROOT)}`")

    runs = _load_runs()
    if not runs:
        st.warning("Nessun EvalRun trovato in `eval/results/`. Esegui `make eval` o `make eval-generation`.")
        st.stop()

    # Sidebar filters
    datasets_available = sorted({r.dataset_id for r in runs})
    selected_datasets = st.sidebar.multiselect("Filtra dataset", datasets_available, default=datasets_available)
    filtered_runs = [r for r in runs if r.dataset_id in selected_datasets]

    if not filtered_runs:
        st.info("Nessun run corrisponde al filtro.")
        st.stop()

    labels = [run_label(r) for r in filtered_runs]
    label_to_run = dict(zip(labels, filtered_runs))

    selected_labels: list[str] = st.multiselect(
        "Seleziona ≥ 2 run da confrontare",
        options=labels,
        default=labels[: min(2, len(labels))],
    )
    if len(selected_labels) < 2:
        st.info("Seleziona almeno 2 run per confrontarli.")
        st.stop()

    sel = [label_to_run[l] for l in selected_labels]

    # Metadata cards
    meta_cols = st.columns(len(sel))
    for col, run in zip(meta_cols, sel):
        with col:
            st.markdown(f"**{run_label(run)}**")
            st.json({
                "dataset": run.dataset_id,
                "pipeline": run.pipeline_mode,
                "model": run.model,
                "commit": run.git_commit[:7],
                "temperature": run.temperature,
                "context_window": run.context_window,
                "quantization": run.quantization,
                "reasoning": run.reasoning_enabled,
            })

    st.divider()
    st.subheader("Metriche")

    table = compare_table(sel)
    short_labels = [run_label(r) for r in sel]
    df = pd.DataFrame(table, index=short_labels).T
    df.index.name = "Metric"

    st.dataframe(
        df.style.highlight_max(axis=1, color="#d4edda").highlight_min(axis=1, color="#f8d7da"),
        use_container_width=True,
    )

    # Visual bar chart
    st.subheader("Grafico")
    chart_df = pd.DataFrame(table, index=short_labels).T
    st.bar_chart(chart_df, use_container_width=True)

    # Delta table (2-run only)
    if len(sel) == 2:
        st.subheader("Delta (run 2 − run 1)")
        delta = {
            m: vals[1] - vals[0]
            for m, vals in table.items()
            if not any(math.isnan(v) for v in vals)
        }
        delta_df = pd.DataFrame(
            {"Metric": list(delta.keys()), "Δ": list(delta.values())}
        ).set_index("Metric")
        st.dataframe(
            delta_df.style.map(
                lambda v: "color: green" if v > 0 else ("color: red" if v < 0 else ""),
                subset=["Δ"],
            ),
            use_container_width=True,
        )

# =============================================================================
# PAGE 2 — Chunk Inspector
# =============================================================================
elif page == "Chunk Inspector":
    st.title("Chunk Inspector")

    dataset = st.sidebar.selectbox("Dataset", ["open_ragbench", "ledger"])
    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)

    # Example queries from golden set
    with st.spinner("Carico esempi dal golden set…"):
        golden = _load_golden(dataset)
    examples = example_queries(golden, n=6)

    example_choice = st.selectbox(
        "Esempio (golden set):",
        ["— inserisci query libera —"] + examples,
        format_func=lambda x: x[:110] if x != "— inserisci query libera —" else x,
    )
    preset = example_choice if example_choice != "— inserisci query libera —" else ""
    query_text = st.text_input("Query libera:", value=preset)

    if not query_text:
        st.info("Seleziona un esempio o scrivi una query.")
        st.stop()

    # Retrieval tabs
    tab_dense, tab_sparse, tab_compare = st.tabs(["Dense", "Sparse", "Dense vs Sparse"])

    with tab_dense:
        with st.spinner("Ricerca dense…"):
            try:
                res_dense = _retrieve(query_text, dataset, "dense", top_k)
                _render_results(res_dense)
            except Exception as e:
                st.error(f"Errore: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")

    with tab_sparse:
        with st.spinner("Ricerca sparse (BM25)…"):
            try:
                res_sparse = _retrieve(query_text, dataset, "sparse", top_k)
                _render_results(res_sparse)
            except Exception as e:
                st.error(f"Errore: {e}")

    with tab_compare:
        st.caption("I risultati sono calcolati indipendentemente per ogni modalità.")
        col_d, col_s = st.columns(2)

        with col_d:
            st.markdown("### Dense")
            with st.spinner("…"):
                try:
                    if "res_dense" not in dir():
                        res_dense = _retrieve(query_text, dataset, "dense", top_k)
                    _render_results(res_dense, show_scores_chart=False)
                except Exception as e:
                    st.error(str(e))

        with col_s:
            st.markdown("### Sparse (BM25)")
            with st.spinner("…"):
                try:
                    if "res_sparse" not in dir():
                        res_sparse = _retrieve(query_text, dataset, "sparse", top_k)
                    _render_results(res_sparse, show_scores_chart=False)
                except Exception as e:
                    st.error(str(e))

# =============================================================================
# PAGE 3 — Golden Query Browser
# =============================================================================
elif page == "Golden Query Browser":
    st.title("Golden Query Browser")

    dataset = st.sidebar.selectbox("Dataset", ["open_ragbench", "ledger"])
    answerable_filter = st.sidebar.radio(
        "Rispondibilità", ["Tutte", "Solo rispondibili", "Solo non rispondibili"]
    )
    top_k = st.sidebar.slider("Top-k per retrieval", min_value=1, max_value=20, value=cfg.TOP_K)

    with st.spinner(f"Carico {dataset}…"):
        golden = _load_golden(dataset)

    if not golden:
        st.warning(f"Nessuna query trovata per {dataset}. Esegui `python scripts/build_golden.py --dataset {dataset}`.")
        st.stop()

    # Filter
    ans_map = {"Tutte": None, "Solo rispondibili": True, "Solo non rispondibili": False}
    search_text = st.text_input("Cerca nel testo della query:", placeholder="filtro libero…")
    filtered = filter_queries(golden, answerable=ans_map[answerable_filter], search=search_text)

    st.caption(f"{len(filtered):,} query su {len(golden):,} totali")

    if not filtered:
        st.info("Nessuna query corrisponde ai filtri.")
        st.stop()

    # Build display DataFrame (cap at 500 rows for performance)
    display = filtered[:500]
    table_data = {
        "query_text": [q.query_text[:90] for q in display],
        "answerable": ["✅" if q.answerable else "❌" for q in display],
        "n_qrels": [len(q.qrels) for q in display],
        "reference_answer": [(q.reference_answer or "")[:50] for q in display],
    }
    df_browse = pd.DataFrame(table_data)
    df_browse.index.name = "#"

    if len(filtered) > 500:
        st.caption(f"Mostrando i primi 500 risultati su {len(filtered):,}.")

    # Row selection
    event = st.dataframe(
        df_browse,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun",
        height=300,
    )

    selected_rows = event.selection.rows if event.selection else []
    if not selected_rows:
        st.info("Clicca una riga per ispezionarla.")
        st.stop()

    selected_query = display[selected_rows[0]]
    st.divider()
    st.subheader("Query selezionata")

    st.markdown(f"**{selected_query.query_text}**")
    info_cols = st.columns(3)
    info_cols[0].write(f"Rispondibile: {'✅' if selected_query.answerable else '❌'}")
    info_cols[1].write(f"Qrel count: {len(selected_query.qrels)}")
    info_cols[2].write(f"ID: `{selected_query.query_id}`")

    if selected_query.reference_answer:
        st.info(f"**Risposta attesa:** {selected_query.reference_answer}")

    if selected_query.qrels:
        with st.expander("Chunk rilevanti (golden qrels)", expanded=False):
            for qr in selected_query.qrels:
                st.write(f"- `{qr.chunk_id}` (relevance={qr.relevance})")

    # Live retrieval + recall
    if st.button("Retrieva live (dense)"):
        try:
            with st.spinner("Retrieval…"):
                results = _retrieve(selected_query.query_text, dataset, "dense", top_k)
            retrieved_ids = [r.payload.get("chunk_id", "") for r in results]
            r_at_1 = recall_at_k(selected_query, retrieved_ids, k=1)
            r_at_k = recall_at_k(selected_query, retrieved_ids, k=top_k)

            col_r1, col_rk = st.columns(2)
            col_r1.metric("Recall@1", f"{r_at_1:.2f}", delta=None)
            col_rk.metric(f"Recall@{top_k}", f"{r_at_k:.2f}", delta=None)

            # Highlight golden chunks in results
            golden_ids = {qr.chunk_id for qr in selected_query.qrels if qr.relevance >= 1}
            for i, r in enumerate(results):
                p = r.payload or {}
                chunk_id = p.get("chunk_id", "")
                is_golden = chunk_id in golden_ids
                badge = "🎯 GOLDEN" if is_golden else ""
                header = (
                    f"#{i + 1}  {badge}  score={r.score:.4f}  ·  {p.get('doc_id', '?')}"
                )
                with st.expander(header, expanded=is_golden):
                    if p.get("section_path"):
                        st.caption(f"Sezione: {p['section_path']}")
                    st.markdown(p.get("text", "*(testo assente)*"))
        except Exception as e:
            st.error(f"Errore retrieval: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")

# =============================================================================
# PAGE 4 — Collection Stats
# =============================================================================
elif page == "Collection Stats":
    st.title("Collection Stats")
    st.caption(f"Qdrant: `{cfg.QDRANT_URL}`")

    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=cfg.QDRANT_URL, timeout=5)
        collections = client.get_collections().collections
    except Exception as e:
        st.error(f"Impossibile connettersi a Qdrant: {e}")
        st.stop()

    if not collections:
        st.warning("Nessuna collection trovata. Esegui `make ingest` per indicizzare i dataset.")
        st.stop()

    for col_info in sorted(collections, key=lambda c: c.name):
        name = col_info.name
        with st.expander(f"**{name}**", expanded=True):
            try:
                info = client.get_collection(name)
                pc = info.points_count or 0
                vc = info.vectors_count or 0

                mc1, mc2 = st.columns(2)
                mc1.metric("Punti (chunk)", f"{pc:,}")
                mc2.metric("Vettori totali", f"{vc:,}")

                # Named vector config
                vconf = info.config.params.vectors
                if isinstance(vconf, dict):
                    rows = []
                    for vname, vparams in vconf.items():
                        size = getattr(vparams, "size", "—")
                        dist = getattr(vparams, "distance", "—")
                        rows.append({"nome": vname, "dimensione": size, "distanza": str(dist)})
                    if rows:
                        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # Sparse vector config
                svconf = getattr(info.config.params, "sparse_vectors", None)
                if svconf:
                    st.write(f"**Sparse vectors:** {list(svconf.keys())}")

            except Exception as e:
                st.error(f"Errore per collection `{name}`: {e}")

    st.divider()
    st.caption("File golden disponibili:")
    for p in sorted(GOLDEN_DIR.glob("*.jsonl")):
        line_count = sum(1 for _ in p.open(encoding="utf-8") if _.strip())
        st.write(f"- `{p.name}` — {line_count:,} query")
