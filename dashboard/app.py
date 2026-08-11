"""D-01: Internal Streamlit dashboard — entrypoint and page dispatch.

Four pages, one module each under `dashboard/views/`:
  1. EvalRun Comparator   — compare EvalRun JSONs within a single dataset, with
                            the E-07 noise floor drawn as ±σ whiskers and deltas
                            below it refused the colour green (ROADMAP §14)
  2. Retrieval Playground — free-form query against any Qdrant collection, in
                            dense / sparse / hybrid, with or without reranking;
                            A/B tab compares two configs on the same query
  3. Failure Explorer     — batch a slice of the golden set, rank worst-first,
                            and put the expected chunk next to what came back
  4. Collection Stats     — Qdrant point counts and vector config

The pages are ordered by how the tool is actually used: measure, then probe,
then explain.

Layers:
  *_store.py / retrieval_probe.py  pure logic, no Streamlit, unit-tested
  state.py                         cached loaders and the shared Qdrant client
  components.py                    render helpers used by more than one view
  views/*.py                       one page each, exposing render()

Usage:
    make dashboard
    # or:  python -m streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402  (must follow the sys.path bootstrap above)

# Must be the first Streamlit call in the script, so it precedes the view
# imports rather than sitting with them.
st.set_page_config(page_title="ibid — dashboard interna", layout="wide")

from dashboard.state import PAGES  # noqa: E402  (needs sys.path above)
from dashboard.views import collections, comparator, failures, playground  # noqa: E402

RENDERERS = {
    "EvalRun Comparator": comparator.render,
    "Retrieval Playground": playground.render,
    "Failure Explorer": failures.render,
    "Collection Stats": collections.render,
}

st.sidebar.title("ibid")
page = st.sidebar.selectbox("Pagina", PAGES)

if st.sidebar.button("↻ Ricarica risultati", width="stretch"):
    # Without this, a run written while the dashboard is open stays invisible
    # until the process is restarted.
    st.cache_data.clear()
    st.rerun()

RENDERERS[page]()
