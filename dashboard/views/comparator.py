"""EvalRun Comparator — compare measured runs within one dataset.

Two rules from ROADMAP are enforced by the UI rather than left to discipline:
  §11  the dataset is a single choice, so a cross-dataset delta cannot be built
  §12  a delta is only coloured when it clears the E-07 noise floor, and only
       called attributable when exactly one parameter differs
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from dashboard.components import (
    grouped_bar_chart,
    render_noise_caption,
    render_run_detail,
)
from dashboard.eval_store import (
    compare_table,
    config_diff,
    config_matrix,
    match_noise_floor,
    noise_std,
    run_label,
    significance_label,
)
from dashboard.state import RESULTS_DIR, ROOT, load_floors, load_runs


def _render_run_card(run) -> None:
    with st.container(border=True):
        st.markdown(f"### {run.pipeline_mode}")
        st.caption(
            f"{run.dataset_id}  ·  `{run.git_commit[:7]}`  ·  "
            f"{run.timestamp.strftime('%d %b %H:%M')}"
        )
        st.divider()
        render_run_detail(run)


def _render_single(run, floors) -> None:
    _render_run_card(run)
    st.divider()
    st.subheader("Metriche")
    metrics_df = pd.DataFrame({"Valore": run.metrics}).sort_index()
    metrics_df.index.name = "Metric"
    st.dataframe(metrics_df, width='stretch')

    floor = match_noise_floor(run, floors)
    stds = {m: s for m in run.metrics if (s := noise_std(floor, m)) is not None}
    grouped_bar_chart(metrics_df.rename(columns={"Valore": run_label(run)}), stds=stds)
    render_noise_caption(floor)


def _render_delta(sel, table, floor) -> None:
    st.subheader("Delta (run 2 − run 1)")

    changed = config_diff(sel[0], sel[1])
    if len(changed) == 0:
        st.info("Stessa configurazione: il delta è puro rumore di esecuzione.")
    elif len(changed) == 1:
        st.success(f"Cambia un parametro solo: **{changed[0]}** — delta attribuibile.")
    else:
        st.warning(
            f"Cambiano **{len(changed)}** parametri ({', '.join(changed)}): il delta "
            "non è attribuibile a nessuno di essi in particolare (ROADMAP §12)."
        )

    rows = []
    for metric, vals in table.items():
        if any(math.isnan(v) for v in vals):
            continue
        d = vals[1] - vals[0]
        rows.append({
            "Metric": metric,
            "Δ": d,
            "Verdetto": significance_label(d, noise_std(floor, metric)),
        })
    if not rows:
        st.caption("Nessuna metrica in comune fra i due run.")
        return

    delta_df = pd.DataFrame(rows).set_index("Metric")

    def _color(row: pd.Series) -> list[str]:
        """Green/red only when the delta clears the noise floor."""
        if not row["Verdetto"].startswith("significativo"):
            return ["color: gray"] * len(row)
        return [f"color: {'green' if row['Δ'] > 0 else 'red'}"] * len(row)

    st.dataframe(
        delta_df.style.apply(_color, axis=1).format({"Δ": "{:+.4f}"}),
        width='stretch',
    )


def _render_multi(sel, table, floors) -> None:
    for col, run in zip(st.columns(len(sel)), sel):
        with col:
            _render_run_card(run)

    st.divider()
    st.subheader("Configurazioni a confronto")
    st.caption("Solo i parametri che differiscono fra i run selezionati.")
    matrix = config_matrix(sel)
    labels = [run_label(r, include_dataset=False) for r in sel]
    if len(matrix) <= 1 and not matrix.get("pipeline_mode"):
        st.info("I run selezionati hanno configurazione identica.")
    else:
        st.dataframe(
            pd.DataFrame(matrix, index=labels).T.rename_axis("Parametro"),
            width='stretch',
        )

    st.subheader("Metriche")
    df = pd.DataFrame(table, index=labels).T
    df.index.name = "Metric"
    st.dataframe(df, width='stretch')

    st.subheader("Grafico")
    floor = match_noise_floor(sel[0], floors)
    stds = {m: s for m in table if (s := noise_std(floor, m)) is not None}
    grouped_bar_chart(df, stds=stds)
    render_noise_caption(floor)

    if len(sel) == 2:
        _render_delta(sel, table, floor)


def render() -> None:
    st.title("EvalRun Comparator")

    runs = load_runs()
    floors = load_floors()
    if not runs:
        st.warning(
            "Nessun EvalRun trovato in `eval/results/`. "
            "Esegui `make eval` o `make eval-generation`."
        )
        st.stop()

    # ROADMAP §11 vieta le metriche aggregate su dataset diversi: il dataset è
    # una scelta singola, non un filtro multiplo, così un delta cross-dataset
    # non è nemmeno esprimibile.
    datasets = sorted({r.dataset_id for r in runs})
    dataset = st.sidebar.selectbox("Dataset", datasets)
    st.caption(f"`{RESULTS_DIR.relative_to(ROOT)}` · dataset **{dataset}**")

    filtered = [r for r in runs if r.dataset_id == dataset]
    if not filtered:
        st.info("Nessun run per questo dataset.")
        st.stop()

    labels = [run_label(r, include_dataset=False) for r in filtered]
    label_to_run = dict(zip(labels, filtered))

    selected = st.multiselect(
        "Seleziona 1 run (dettaglio) o ≥ 2 (confronto)",
        options=labels,
        default=labels[: min(2, len(labels))],
    )
    if not selected:
        st.info("Seleziona almeno un run.")
        st.stop()

    sel = [label_to_run[lbl] for lbl in selected]
    if len(sel) == 1:
        _render_single(sel[0], floors)
    else:
        _render_multi(sel, compare_table(sel), floors)
