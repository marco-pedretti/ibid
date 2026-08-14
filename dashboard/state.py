"""Percorsi condivisi, caricatori in cache, e il backend.

Tutto ciò che deve esistere una volta sola per sessione sta qui, così le viste
possono importarlo senza che ognuna rilegga `eval/results` a ogni rerun.

**Da A-06 non c'è più un client Qdrant.** C'era, ed era il segno che la
dashboard non era un consumatore del sistema ma un secondo backend: apriva la
connessione al database, embeddava le query, fondeva i risultati. Ora chiede, e
chi sa dove sta Qdrant è il servizio.

Le due categorie di dati che la dashboard maneggia restano **distinte di
proposito**, ed è la ragione per cui `src.` non è sparito del tutto da questo
pacchetto:

- **le misure** — `eval/results/`, `eval/golden/` — sono file locali, letti col
  loro contratto dati. L'API non le serve, e non deve: la Fase 7 espone il
  sistema, non l'archivio degli esperimenti;
- **il sistema** — recupero, chunk, collection — passa dall'API, sempre.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard import api_client
from dashboard.eval_store import load_eval_runs, load_noise_floors
from dashboard.golden_store import load_golden_queries
from dashboard.retrieval_probe import ProbeConfig, ProbeHit, probe

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / "eval" / "results"
GOLDEN_DIR = ROOT / "eval" / "golden"

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


@st.cache_data(show_spinner=False, ttl=30)
def capabilities():
    """Cosa il backend accetta: dataset, collection, modalità.

    TTL breve perché una collection creata mentre la dashboard è aperta compaia
    senza riavviare. `None` quando il backend non risponde — una risposta che le
    viste devono poter disegnare, non un'eccezione che le interrompe.
    """
    try:
        return api_client.capabilities()
    except (api_client.ApiError, api_client.ApiUnreachable):
        return None


def collections() -> list[str]:
    """I nomi delle collection interrogabili; lista vuota se il backend tace."""
    caps = capabilities()
    return [c["name"] for c in caps.collections] if caps else []


def known_datasets() -> tuple[str, ...]:
    """I dataset con un golden set, **chiesti al backend**.

    Erano `("open_ragbench", "ledger")` scritti a mano qui: la quindicesima
    copia di quella lista, in un file che Q-06 non poteva raggiungere perché
    non è uno script.
    """
    caps = capabilities()
    return caps.dataset_ids if caps else ()


def run_probe(query_text: str, conf: ProbeConfig) -> list[ProbeHit]:
    return probe(query_text, conf)
