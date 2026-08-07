"""Shared paths, cached loaders and the Qdrant client.

Everything that must exist exactly once per session lives here, so the view
modules can import it without each building its own client or re-reading
eval/results from disk on every rerun.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

import src.config as cfg
from dashboard.eval_store import load_eval_runs, load_noise_floors
from dashboard.golden_store import load_golden_queries
from dashboard.retrieval_probe import ProbeConfig, ProbeHit, list_collections, probe

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / "eval" / "results"
GOLDEN_DIR = ROOT / "eval" / "golden"

#: Datasets with a golden set. Used to map a collection back to its qrels.
KNOWN_DATASETS = ("open_ragbench", "ledger")

PAGES = (
    "EvalRun Comparator",
    "Retrieval Playground",
    "Failure Explorer",
    "Collection Stats",
)


@st.cache_data(show_spinner=False)
def load_golden(dataset: str) -> list:
    return load_golden_queries(GOLDEN_DIR / f"{dataset}.jsonl")


@st.cache_data(show_spinner=False)
def load_runs() -> list:
    return load_eval_runs(RESULTS_DIR)


@st.cache_data(show_spinner=False)
def load_floors() -> list:
    return load_noise_floors(RESULTS_DIR)


@st.cache_resource(show_spinner=False)
def client():
    """One Qdrant client for the session, not one per query."""
    from src.index.store import get_client

    return get_client(cfg.QDRANT_URL)


@st.cache_data(show_spinner=False, ttl=30)
def collections() -> list[str]:
    """Collection names from the live server; empty list when unreachable.

    Short TTL so a collection created while the dashboard is open shows up
    without a restart.
    """
    try:
        return list_collections(client())
    except Exception:
        return []


def run_probe(query_text: str, conf: ProbeConfig) -> list[ProbeHit]:
    return probe(client(), query_text, conf)
