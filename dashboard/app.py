"""D-01: Internal Streamlit dashboard.

Four pages:
  1. EvalRun Comparator — compare ≥2 EvalRun JSONs from eval/results/ within a
                          single dataset, with E-07 noise floor as error bars
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

import altair as alt
import pandas as pd
import streamlit as st

import src.config as cfg
from dashboard.eval_store import (
    compare_table,
    config_diff,
    config_matrix,
    load_eval_runs,
    load_noise_floors,
    match_noise_floor,
    noise_std,
    run_label,
    significance_label,
)
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


@st.cache_data(show_spinner=False)
def _load_floors() -> list:
    return load_noise_floors(RESULTS_DIR)


if st.sidebar.button("↻ Ricarica risultati", width='stretch'):
    # Without this, a run written while the dashboard is open stays invisible
    # until the process is restarted.
    st.cache_data.clear()
    st.rerun()


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


def _render_noise_caption(floor) -> None:
    """State plainly whether a noise floor backs the chart, or that none exists."""
    if floor is None:
        st.warning(
            "Nessun rumore di fondo misurato per questo dataset: le barre non hanno "
            "intervallo e nessun delta può essere dichiarato un miglioramento "
            "(ROADMAP §12). Esegui `make noise-floor`.",
            icon="⚠️",
        )
    else:
        st.caption(
            f"Whisker = ±σ dal rumore di fondo E-07 "
            f"({floor.n_runs} run, {floor.retrieval_mode}, "
            f"`{floor.git_commit[:7]}`, {floor.timestamp.strftime('%d %b')})."
        )


def _render_run_meta(run) -> None:
    """Show EvalRun metadata as structured fields, not raw JSON."""
    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("Dataset", run.dataset_id)
    r1c2.metric("Pipeline", run.pipeline_mode)
    r1c3.metric("Model", run.model)
    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("Commit", run.git_commit[:7])
    r2c2.metric("Quantization", run.quantization)
    r2c3.metric("Config hash", run.config_hash)
    r3c1, r3c2, r3c3 = st.columns(3)
    r3c1.metric("Temperatura", run.temperature)
    r3c2.metric("Context window", run.context_window if run.context_window else "—")
    r3c3.metric("Reasoning", "✅" if run.reasoning_enabled else "❌")
    if run.config:
        r4c1, r4c2, r4c3 = st.columns(3)
        r4c1.metric("Retrieval", run.config.get("retrieval_mode", "—"))
        r4c2.metric("Collection", run.config.get("collection", "—"))
        r4c3.metric("top_k", run.config.get("top_k", "—"))
        active = [
            k for k in ("rerank", "query_rewrite", "doc_aggregate") if run.config.get(k)
        ]
        if run.config.get("filter_content_type"):
            active.append(f"filter={run.config['filter_content_type']}")
        st.caption("Flag attivi: " + (", ".join(active) if active else "nessuno"))


def _grouped_bar_chart(
    df: pd.DataFrame,
    height: int = 300,
    stds: dict[str, float] | None = None,
) -> None:
    """Altair grouped bar chart. df: index=metrics, columns=run labels.

    When `stds` is given (metric -> noise-floor std from E-07), each bar carries
    a ±σ whisker.  Bars whose difference is visually smaller than the whisker
    are not a result — that is the whole point of showing it.
    """
    melted = (
        df.reset_index()
        .rename(columns={"index": "Metric"})
        .melt(id_vars="Metric", var_name="Run", value_name="Score")
    )
    base = alt.Chart(melted)
    bars = base.mark_bar().encode(
        x=alt.X("Metric:N", sort=None, axis=alt.Axis(labelAngle=-30, title="")),
        y=alt.Y("Score:Q", axis=alt.Axis(title="Score")),
        color=alt.Color("Run:N", legend=alt.Legend(orient="bottom")),
        xOffset="Run:N",
        tooltip=["Metric:N", "Run:N", alt.Tooltip("Score:Q", format=".4f")],
    )
    layers = bars

    if stds:
        melted["lo"] = melted.apply(
            lambda r: r["Score"] - stds.get(r["Metric"], 0.0), axis=1
        )
        melted["hi"] = melted.apply(
            lambda r: r["Score"] + stds.get(r["Metric"], 0.0), axis=1
        )
        whiskers = (
            alt.Chart(melted)
            .mark_rule(strokeWidth=1.5, color="#444")
            .encode(
                x=alt.X("Metric:N", sort=None),
                y=alt.Y("lo:Q"),
                y2=alt.Y2("hi:Q"),
                xOffset="Run:N",
            )
        )
        layers = bars + whiskers

    st.altair_chart(layers.properties(height=height), width='stretch')


# =============================================================================
# PAGE 1 — EvalRun Comparator
# =============================================================================
if page == "EvalRun Comparator":
    st.title("EvalRun Comparator")

    runs = _load_runs()
    floors = _load_floors()
    if not runs:
        st.warning("Nessun EvalRun trovato in `eval/results/`. Esegui `make eval` o `make eval-generation`.")
        st.stop()

    # ROADMAP §11 vieta le metriche aggregate su dataset diversi: il dataset è
    # una scelta singola, non un filtro multiplo, così un delta cross-dataset
    # non è nemmeno esprimibile.
    datasets_available = sorted({r.dataset_id for r in runs})
    dataset = st.sidebar.selectbox("Dataset", datasets_available)
    st.caption(f"`{RESULTS_DIR.relative_to(ROOT)}` · dataset **{dataset}**")
    filtered_runs = [r for r in runs if r.dataset_id == dataset]

    if not filtered_runs:
        st.info("Nessun run per questo dataset.")
        st.stop()

    labels = [run_label(r, include_dataset=False) for r in filtered_runs]
    label_to_run = dict(zip(labels, filtered_runs))

    selected_labels: list[str] = st.multiselect(
        "Seleziona 1 run (dettaglio) o ≥ 2 (confronto)",
        options=labels,
        default=labels[: min(2, len(labels))],
    )
    if not selected_labels:
        st.info("Seleziona almeno un run.")
        st.stop()

    sel = [label_to_run[lbl] for lbl in selected_labels]

    # --- Single run: detail view ---
    if len(sel) == 1:
        run = sel[0]
        with st.container(border=True):
            st.markdown(f"### {run.pipeline_mode}")
            st.caption(
                f"{run.dataset_id}  ·  "
                f"`{run.git_commit[:7]}`  ·  "
                f"{run.timestamp.strftime('%d %b %H:%M')}"
            )
            st.divider()
            _render_run_meta(run)
        st.divider()
        st.subheader("Metriche")
        metrics_df = pd.DataFrame({"Valore": run.metrics}).sort_index()
        metrics_df.index.name = "Metric"
        st.dataframe(metrics_df, width='stretch')
        floor = match_noise_floor(run, floors)
        stds = {m: s for m in run.metrics if (s := noise_std(floor, m)) is not None}
        _grouped_bar_chart(
            metrics_df.rename(columns={"Valore": run_label(run, include_dataset=False)}),
            stds=stds,
        )
        _render_noise_caption(floor)

    # --- Multi-run: comparison view ---
    else:
        meta_cols = st.columns(len(sel))
        for col, run in zip(meta_cols, sel):
            with col:
                with st.container(border=True):
                    st.markdown(f"### {run.pipeline_mode}")
                    st.caption(
                        f"{run.dataset_id}  ·  "
                        f"`{run.git_commit[:7]}`  ·  "
                        f"{run.timestamp.strftime('%d %b %H:%M')}"
                    )
                    st.divider()
                    _render_run_meta(run)

        st.divider()
        st.subheader("Configurazioni a confronto")
        st.caption("Solo i parametri che differiscono fra i run selezionati.")
        matrix = config_matrix(sel)
        short_labels = [run_label(r, include_dataset=False) for r in sel]
        if len(matrix) <= 1 and not matrix.get("pipeline_mode"):
            st.info("I run selezionati hanno configurazione identica.")
        else:
            st.dataframe(
                pd.DataFrame(matrix, index=short_labels).T.rename_axis("Parametro"),
                width='stretch',
            )

        st.subheader("Metriche")
        table = compare_table(sel)
        df = pd.DataFrame(table, index=short_labels).T
        df.index.name = "Metric"
        st.dataframe(df, width='stretch')

        st.subheader("Grafico")
        floor = match_noise_floor(sel[0], floors)
        stds = {m: s for m in table if (s := noise_std(floor, m)) is not None}
        _grouped_bar_chart(df, stds=stds)
        _render_noise_caption(floor)

        if len(sel) == 2:
            st.subheader("Delta (run 2 − run 1)")

            # ROADMAP §12: un delta è attribuibile solo se cambia una cosa sola.
            changed = config_diff(sel[0], sel[1])
            if len(changed) == 0:
                st.info("Stessa configurazione: il delta è puro rumore di esecuzione.")
            elif len(changed) == 1:
                st.success(f"Cambia un parametro solo: **{changed[0]}** — delta attribuibile.")
            else:
                st.warning(
                    "Cambiano **" + str(len(changed)) + "** parametri "
                    f"({', '.join(changed)}): il delta non è attribuibile a nessuno "
                    "di essi in particolare (ROADMAP §12)."
                )

            rows = []
            for metric, vals in table.items():
                if any(math.isnan(v) for v in vals):
                    continue
                d = vals[1] - vals[0]
                std = noise_std(floor, metric)
                rows.append(
                    {
                        "Metric": metric,
                        "Δ": d,
                        "Verdetto": significance_label(d, std),
                    }
                )
            delta_df = pd.DataFrame(rows).set_index("Metric")

            def _color(row: pd.Series) -> list[str]:
                """Green/red only when the delta clears the noise floor."""
                if not row["Verdetto"].startswith("significativo"):
                    return ["color: gray"] * len(row)
                tint = "green" if row["Δ"] > 0 else "red"
                return [f"color: {tint}"] * len(row)

            st.dataframe(
                delta_df.style.apply(_color, axis=1).format({"Δ": "{:+.4f}"}),
                width='stretch',
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
        width='stretch',
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
                vc = getattr(info, "vectors_count", None)

                mc1, mc2 = st.columns(2)
                mc1.metric("Punti (chunk)", f"{pc:,}")
                mc2.metric("Vettori totali", f"{vc:,}" if vc is not None else "—")

                # Named vector config
                vconf = info.config.params.vectors
                if isinstance(vconf, dict):
                    rows = []
                    for vname, vparams in vconf.items():
                        size = getattr(vparams, "size", "—")
                        dist = getattr(vparams, "distance", "—")
                        rows.append({"nome": vname, "dimensione": size, "distanza": str(dist)})
                    if rows:
                        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

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
