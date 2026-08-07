"""Streamlit render helpers shared by more than one view.

Anything that draws and is used by a single view stays in that view module;
this file is only for what genuinely repeats.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.retrieval_probe import ProbeHit

def render_noise_caption(floor) -> None:
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


def render_run_detail(run) -> None:
    """Full metadata for a run, as metric tiles."""
    r1 = st.columns(3)
    r1[0].metric("Dataset", run.dataset_id)
    r1[1].metric("Pipeline", run.pipeline_mode)
    r1[2].metric("Model", run.model)
    r2 = st.columns(3)
    r2[0].metric("Commit", run.git_commit[:7])
    r2[1].metric("Quantization", run.quantization)
    r2[2].metric("Config hash", run.config_hash)
    r3 = st.columns(3)
    r3[0].metric("Temperatura", run.temperature)
    r3[1].metric("Context window", run.context_window if run.context_window else "—")
    r3[2].metric("Reasoning", "✅" if run.reasoning_enabled else "❌")
    if run.config:
        r4 = st.columns(3)
        r4[0].metric("Retrieval", run.config.get("retrieval_mode", "—"))
        r4[1].metric("Collection", run.config.get("collection", "—"))
        r4[2].metric("top_k", run.config.get("top_k", "—"))
        active = [
            k for k in ("rerank", "query_rewrite", "doc_aggregate") if run.config.get(k)
        ]
        if run.config.get("filter_content_type"):
            active.append(f"filter={run.config['filter_content_type']}")
        st.caption("Flag attivi: " + (", ".join(active) if active else "nessuno"))


def grouped_bar_chart(
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
    bars = alt.Chart(melted).mark_bar().encode(
        x=alt.X("Metric:N", sort=None, axis=alt.Axis(labelAngle=-30, title="")),
        y=alt.Y("Score:Q", axis=alt.Axis(title="Score")),
        color=alt.Color("Run:N", legend=alt.Legend(orient="bottom")),
        xOffset="Run:N",
        tooltip=["Metric:N", "Run:N", alt.Tooltip("Score:Q", format=".4f")],
    )
    layers = bars

    if stds:
        melted["lo"] = melted.apply(lambda r: r["Score"] - stds.get(r["Metric"], 0.0), axis=1)
        melted["hi"] = melted.apply(lambda r: r["Score"] + stds.get(r["Metric"], 0.0), axis=1)
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


def render_hits(
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
    c = st.columns(4)
    c[0].metric("Chunk", len(hits))
    c[1].metric("Documenti unici", len(set(doc_ids)))
    c[2].metric("Score max", f"{max(scores):.4f}")
    c[3].metric("Score min", f"{min(scores):.4f}")

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
            meta = st.columns(4)
            meta[0].write(f"**Pipeline:** {p.get('pipeline', '—')}")
            meta[1].write(f"**Pagina:** {p.get('page', '—')}")
            meta[2].write(f"**content_type:** {p.get('content_type', '—')}")
            meta[3].write(f"**Caratteri:** {len(p.get('text', ''))}")
            st.caption(f"`{h.chunk_id}`")
            if p.get("section_path"):
                st.caption(f"Sezione: {p['section_path']}")
            st.divider()
            st.markdown(p.get("text", "*(testo assente)*"))
