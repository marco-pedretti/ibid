"""D-01: Internal Streamlit dashboard.

Four pages:
  1. EvalRun Comparator   — compare EvalRun JSONs within a single dataset, with
                            the E-07 noise floor drawn as ±σ whiskers and deltas
                            below it refused the colour green (ROADMAP §12)
  2. Retrieval Playground — free-form query against any Qdrant collection, in
                            dense / sparse / hybrid, with or without reranking;
                            A/B tab compares two configs on the same query
  3. Failure Explorer     — batch a slice of the golden set, rank worst-first,
                            and put the expected chunk next to what came back
  4. Collection Stats     — Qdrant point counts and vector config

The pages are ordered by how the tool is actually used: measure, then probe,
then explain.

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
from dashboard.failure_store import (
    chunk_id_mismatch,
    evaluate_queries,
    failure_summary,
    sort_by_failure,
)
from dashboard.golden_store import example_queries, load_golden_queries
from dashboard.retrieval_probe import (
    RETRIEVAL_MODES,
    ProbeConfig,
    ProbeHit,
    compare_hits,
    dataset_of_collection,
    fetch_chunks_by_id,
    list_collections,
    probe,
)

RESULTS_DIR = ROOT / "eval" / "results"
GOLDEN_DIR = ROOT / "eval" / "golden"
KNOWN_DATASETS = ("open_ragbench", "ledger")

st.set_page_config(page_title="ibid — dashboard interna", layout="wide")
st.sidebar.title("ibid")
page = st.sidebar.selectbox(
    "Pagina",
    [
        "EvalRun Comparator",
        "Retrieval Playground",
        "Failure Explorer",
        "Collection Stats",
    ],
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
# Shared retrieval helpers
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _client():
    """One Qdrant client for the session, not one per query."""
    from src.index.store import get_client

    return get_client(cfg.QDRANT_URL)


@st.cache_data(show_spinner=False, ttl=30)
def _collections() -> list[str]:
    try:
        return list_collections(_client())
    except Exception:
        return []


def _probe(query_text: str, conf: ProbeConfig) -> list[ProbeHit]:
    return probe(_client(), query_text, conf)


def _render_hits(
    hits: list[ProbeHit],
    show_scores_chart: bool = True,
    highlight: set[str] | None = None,
    golden_ids: set[str] | None = None,
) -> None:
    """Render ranked hits as expandable cards with full metadata.

    `highlight` marks chunks shared with another probe; `golden_ids` marks the
    chunks the qrels say are relevant.
    """
    if not hits:
        st.warning("Nessun risultato.")
        return

    doc_ids = [h.payload.get("doc_id", "") for h in hits]
    scores = [h.score for h in hits]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chunk", len(hits))
    c2.metric("Documenti unici", len(set(doc_ids)))
    c3.metric("Score max", f"{max(scores):.4f}")
    c4.metric("Score min", f"{min(scores):.4f}")

    if show_scores_chart and len(hits) > 1:
        st.bar_chart(
            pd.DataFrame({"Score": scores}, index=[f"#{h.rank}" for h in hits]),
            height=140,
        )

    for h in hits:
        p = h.payload
        badges = ""
        if golden_ids and h.chunk_id in golden_ids:
            badges += " 🎯 GOLDEN"
        if highlight and h.chunk_id in highlight:
            badges += " 🔗 in comune"
        header = (
            f"#{h.rank}{badges}  score={h.score:.4f}  ·  {p.get('doc_id', '?')} "
            f"·  {p.get('content_type', '?')}  ·  {p.get('doc_genre', '?')}"
        )
        is_notable = bool(golden_ids and h.chunk_id in golden_ids)
        with st.expander(header, expanded=is_notable or h.rank == 1):
            meta_cols = st.columns(4)
            meta_cols[0].write(f"**Pipeline:** {p.get('pipeline', '—')}")
            meta_cols[1].write(f"**Pagina:** {p.get('page', '—')}")
            meta_cols[2].write(f"**content_type:** {p.get('content_type', '—')}")
            meta_cols[3].write(f"**Caratteri:** {len(p.get('text', ''))}")
            st.caption(f"`{h.chunk_id}`")
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
# PAGE 2 — Retrieval Playground
# =============================================================================
elif page == "Retrieval Playground":
    st.title("Retrieval Playground")

    collections = _collections()
    if not collections:
        st.error(
            f"Nessuna collection su `{cfg.QDRANT_URL}`. "
            "Avvia Qdrant e lancia `make ingest`."
        )
        st.stop()

    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)

    # Esempi dal golden set del dataset a cui la collection appartiene.
    default_coll = collections[0]
    dataset = dataset_of_collection(default_coll, KNOWN_DATASETS)
    with st.spinner("Carico esempi dal golden set…"):
        golden = _load_golden(dataset)
    examples = example_queries(golden, n=6)

    FREE = "— inserisci query libera —"
    example_choice = st.selectbox(
        f"Esempio (golden set {dataset}):",
        [FREE] + examples,
        format_func=lambda x: x[:110] if x != FREE else x,
    )
    query_text = st.text_input(
        "Query libera:", value=example_choice if example_choice != FREE else ""
    )

    if not query_text:
        st.info("Seleziona un esempio o scrivi una query.")
        st.stop()

    tab_single, tab_ab = st.tabs(["Config singola", "A/B fra due config"])

    with tab_single:
        c1, c2, c3 = st.columns([2, 1, 1])
        coll = c1.selectbox("Collection", collections, key="single_coll")
        mode = c2.selectbox("Modalità", RETRIEVAL_MODES, key="single_mode")
        do_rerank = c3.checkbox("Rerank (R-02)", key="single_rerank")

        conf = ProbeConfig(collection=coll, retrieval_mode=mode,
                           rerank=do_rerank, top_k=top_k)
        with st.spinner(f"Retrieval — {conf.label()}…"):
            try:
                _render_hits(_probe(query_text, conf))
            except Exception as e:
                st.error(f"Errore: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")

    with tab_ab:
        st.caption(
            "Due configurazioni qualsiasi sulla stessa query — per esempio "
            "`ledger` contro `ledger_routed`, che è l'ablation R-07."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### A")
            conf_a = ProbeConfig(
                collection=st.selectbox("Collection", collections, key="a_coll"),
                retrieval_mode=st.selectbox("Modalità", RETRIEVAL_MODES, key="a_mode"),
                rerank=st.checkbox("Rerank", key="a_rerank"),
                top_k=top_k,
            )
        with col_b:
            st.markdown("#### B")
            conf_b = ProbeConfig(
                collection=st.selectbox(
                    "Collection", collections,
                    index=min(1, len(collections) - 1), key="b_coll",
                ),
                retrieval_mode=st.selectbox("Modalità", RETRIEVAL_MODES, key="b_mode"),
                rerank=st.checkbox("Rerank", key="b_rerank"),
                top_k=top_k,
            )

        if st.button("Confronta", type="primary"):
            try:
                with st.spinner("Retrieval A…"):
                    hits_a = _probe(query_text, conf_a)
                with st.spinner("Retrieval B…"):
                    hits_b = _probe(query_text, conf_b)
            except Exception as e:
                st.error(f"Errore: {e}")
                st.stop()

            cmp = compare_hits(hits_a, hits_b)
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Chunk in comune", f"{len(cmp.shared)}/{len(hits_a)}")
            m2.metric("Jaccard chunk", f"{cmp.jaccard:.2f}")
            m3.metric("Jaccard documento", f"{cmp.doc_jaccard:.2f}")

            if cmp.jaccard == 0.0 and cmp.doc_jaccard > 0:
                st.info(
                    "Zero chunk in comune ma documenti condivisi: le due collection "
                    "usano pipeline di chunking diverse, quindi i `chunk_id` non "
                    "coincidono per costruzione. Solo il livello documento è "
                    "confrontabile — è la ragione per cui R-07 si legge su doc_R@5.",
                    icon="ℹ️",
                )
            if cmp.shared_docs:
                st.caption("Documenti trovati da entrambe: " +
                           ", ".join(f"`{d}`" for d in cmp.shared_docs))

            res_a, res_b = st.columns(2)
            with res_a:
                st.markdown(f"### A — {conf_a.label()}")
                _render_hits(hits_a, show_scores_chart=False, highlight=set(cmp.shared))
            with res_b:
                st.markdown(f"### B — {conf_b.label()}")
                _render_hits(hits_b, show_scores_chart=False, highlight=set(cmp.shared))

# =============================================================================
# PAGE 3 — Failure Explorer
# =============================================================================
elif page == "Failure Explorer":
    st.title("Failure Explorer")
    st.caption(
        "Esegue un batch di query golden e le ordina dalla peggiore. "
        "Le query che funzionano non spiegano niente."
    )

    collections = _collections()
    if not collections:
        st.error(f"Nessuna collection su `{cfg.QDRANT_URL}`.")
        st.stop()

    coll = st.sidebar.selectbox("Collection", collections)
    dataset = dataset_of_collection(coll, KNOWN_DATASETS)
    st.sidebar.caption(f"Golden set: `{dataset}`")
    mode = st.sidebar.selectbox("Modalità", RETRIEVAL_MODES)
    do_rerank = st.sidebar.checkbox("Rerank (R-02)")
    top_k = st.sidebar.slider("Top-k", min_value=1, max_value=20, value=cfg.TOP_K)
    n_queries = st.sidebar.slider(
        "Query da eseguire", min_value=10, max_value=500, value=50, step=10,
        help="Un batch, non l'intero golden set: la dashboard e uno strumento di "
             "debug, la misura ufficiale la fa scripts/eval.py.",
    )

    with st.spinner(f"Carico golden {dataset}…"):
        golden = _load_golden(dataset)
    if not golden:
        st.warning(
            f"Nessuna query per {dataset}. "
            f"Esegui `python scripts/build_golden.py --dataset {dataset}`."
        )
        st.stop()

    answerable = [q for q in golden if q.answerable and q.qrels]
    st.caption(
        f"{len(answerable):,} query rispondibili su {len(golden):,} totali "
        f"nel golden set."
    )

    conf = ProbeConfig(collection=coll, retrieval_mode=mode,
                       rerank=do_rerank, top_k=top_k)

    if st.button(f"Esegui {n_queries} query — {conf.label()}", type="primary"):
        subset = answerable[:n_queries]
        bar = st.progress(0.0, text="Retrieval…")
        try:
            outcomes = evaluate_queries(
                _client(), subset, conf,
                on_progress=lambda i, n: bar.progress(i / n, text=f"Scoring {i}/{n}"),
            )
        except Exception as e:
            bar.empty()
            st.error(f"Errore: {e}\n\nQdrant su `{cfg.QDRANT_URL}`?")
            st.stop()
        bar.empty()
        # Un solo oggetto: le tre informazioni descrivono lo stesso batch e
        # tenerle in chiavi separate le lascia divergere.
        st.session_state["batch"] = {
            "outcomes": outcomes, "label": conf.label(), "dataset": dataset,
        }

    batch = st.session_state.get("batch") or {}
    outcomes = batch.get("outcomes")
    if not outcomes:
        st.info("Premi il bottone per eseguire il batch.")
        st.stop()

    st.divider()
    st.subheader(f"Risultati — {batch['label']}")

    summary = failure_summary(outcomes)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Query", int(summary["n"]))
    s2.metric("Recall chunk medio", f"{summary['mean_recall']:.3f}")
    s3.metric("Recall doc medio", f"{summary['mean_doc_recall']:.3f}")
    s4.metric(
        "Fallimenti totali", int(summary["n_failures"]),
        delta=f"{summary['failure_rate']:.0%}", delta_color="inverse",
    )

    if chunk_id_mismatch(outcomes):
        st.info(
            "Recall chunk 0 su tutte le query ma documenti trovati: i `chunk_id` "
            "di questa collection non coincidono con quelli dei qrels, perche e "
            "stata costruita con una pipeline di chunking diversa. Leggi il "
            "**recall documento**, non quello chunk — e la stessa ragione per cui "
            "R-07 si misura su doc_R@5.",
            icon="ℹ️",
        )

    ranked = sort_by_failure(outcomes)
    only_failures = st.checkbox("Mostra solo i fallimenti (recall doc = 0)", value=True)
    shown = [o for o in ranked if o.is_failure] if only_failures else ranked

    if not shown:
        st.success("Nessun fallimento in questo batch.")
        st.stop()

    df_fail = pd.DataFrame({
        "query": [o.query.query_text[:100] for o in shown],
        "recall_chunk": [o.recall for o in shown],
        "recall_doc": [o.doc_recall for o in shown],
        "top_score": [o.top_score for o in shown],
        "n_qrels": [len(o.query.qrels) for o in shown],
    })
    df_fail.index.name = "#"
    event = st.dataframe(
        df_fail, width='stretch', selection_mode="single-row",
        on_select="rerun", height=300,
    )

    rows = event.selection.rows if event.selection else []
    if not rows:
        st.info("Clicca una riga per confrontare atteso e recuperato.")
        st.stop()

    o = shown[rows[0]]
    st.divider()
    st.markdown(f"### {o.query.query_text}")
    i1, i2, i3 = st.columns(3)
    i1.metric("Recall chunk", f"{o.recall:.2f}")
    i2.metric("Recall doc", f"{o.doc_recall:.2f}")
    i3.metric("Query ID", o.query.query_id)
    if o.query.reference_answer:
        st.info(f"**Risposta attesa:** {o.query.reference_answer}")

    col_exp, col_got = st.columns(2)

    with col_exp:
        st.markdown("#### Atteso (golden qrels)")
        golden_ids = sorted(o.golden_ids)
        try:
            texts = fetch_chunks_by_id(_client(), coll, golden_ids)
        except Exception as e:
            texts = {}
            st.caption(f"(testo non recuperabile: {e})")
        for cid in golden_ids:
            payload = texts.get(cid)
            with st.expander(f"`{cid}`" + ("" if payload else "  ⚠️ assente"),
                             expanded=True):
                if payload:
                    st.caption(
                        f"{payload.get('doc_id', '?')} · "
                        f"{payload.get('content_type', '?')} · "
                        f"{len(payload.get('text', ''))} caratteri"
                    )
                    st.markdown(payload.get("text", "")[:2000])
                else:
                    st.warning(
                        "Questo `chunk_id` non esiste in `" + coll + "`: il qrel "
                        "e stato scritto contro una collection con chunking diverso. "
                        "Non e un errore di retrieval.",
                        icon="⚠️",
                    )

    with col_got:
        st.markdown("#### Recuperato")
        hits = [
            ProbeHit(rank=i, chunk_id=cid, score=sc, payload=pl)
            for i, (cid, sc, pl) in enumerate(
                zip(o.retrieved_ids, o.scores, o.payloads), 1
            )
        ]
        _render_hits(hits, show_scores_chart=False, golden_ids=o.golden_ids)

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
