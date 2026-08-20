"""Single-query retrieval, for interactive debugging.

Da A-06 **non esegue più il recupero**: lo chiede al backend. Quel che resta qui
è ciò che il backend non fa e non deve fare — mettere due risultati uno accanto
all'altro e dire in cosa differiscono.

Prima c'era una copia della pipeline: embedding, fusione RRF, cross-encoder,
tutto riscritto. Il commento in cima diceva che i parametri venivano da
`src.config` «così che quello che vedi qui sia quello che l'eval ha misurato»,
e la buona intenzione non bastava — dopo A-02 la configurazione di richiesta ha
smesso di stare in `cfg`, e questa copia continuava a leggerla da lì. Aveva già
smesso di misurare la stessa cosa, e nessun test poteva accorgersene perché
verificava la copia contro sé stessa.

`ProbeConfig` sopravvive perché è la *domanda* — quale collection, quale
modalità, quanto in profondità — e la domanda resta della dashboard.

No Streamlit import: testable without a running app.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dashboard import api_client

#: Le modalità che il backend accetta. Il default esiste perché la dashboard
#: deve poter disegnare i suoi controlli **prima** di aver parlato col backend;
#: `capabilities().retrieval_modes` è la risposta vera, e `views/playground.py`
#: la usa quando ce l'ha.
RETRIEVAL_MODES = ("dense", "sparse", "hybrid")


@dataclass(frozen=True)
class ProbeConfig:
    """One retrieval configuration to run a query against."""

    collection: str
    retrieval_mode: str = "dense"
    rerank: bool = False
    top_k: int = 5

    def label(self) -> str:
        parts = [self.collection, self.retrieval_mode]
        if self.rerank:
            parts.append("rerank")
        return " · ".join(parts)


@dataclass
class ProbeHit:
    rank: int  # 1-based
    chunk_id: str
    score: float
    payload: dict[str, Any]


def list_collections() -> list[str]:
    """Le collection presenti sul server, ordinate.

    La dashboard aveva `["open_ragbench", "ledger"]` scritto a mano, il che
    rendeva irraggiungibili le collection `*_routed` di R-07 proprio dall'unico
    strumento costruito per ispezionarle. Poi lo chiedeva a Qdrant per conto
    suo; ora lo chiede al backend, che è l'unico che deve sapere dove sta
    Qdrant.
    """
    return api_client.capabilities().collections


def dataset_of_collection(collection: str, known_datasets: tuple[str, ...]) -> str:
    """Map a collection name back to the dataset whose golden set describes it.

    "ledger_routed" -> "ledger".  Longest match wins so a hypothetical
    "ledger_v2" dataset would not be swallowed by "ledger".
    """
    for ds in sorted(known_datasets, key=len, reverse=True):
        if collection == ds or collection.startswith(ds + "_"):
            return ds
    return collection


def fetch_chunks_by_id(collection: str, chunk_ids: list[str]) -> dict[str, dict]:
    """I payload dei chunk d'oro, per id.

    Serve a mostrare cosa i qrels indicano davvero. Mostrare solo l'id — come
    faceva il vecchio browser del golden set — rende impossibile distinguere un
    retrieval sbagliato da un'etichetta sbagliata, e le due chiedono correzioni
    opposte.

    Gli id assenti mancano dal risultato, il che è **esso stesso la risposta**
    quando un `chunk_id` d'oro non esiste nella collection interrogata.
    """
    return api_client.chunks(chunk_ids, collection)


def _hits_from(risultato: list[dict]) -> list[ProbeHit]:
    """La risposta dell'API nella forma che le viste già disegnano.

    Il rango non arriva dal filo: è la posizione nella lista. L'API restituisce
    i chunk **in ordine**, e numerarli qui evita di dover credere a un campo che
    potrebbe contraddire l'ordine in cui sono arrivati.
    """
    return [
        ProbeHit(rank=i, chunk_id=c["chunk_id"], score=c["score"], payload=c)
        for i, c in enumerate(risultato, 1)
    ]


def probe(query_text: str, config: ProbeConfig) -> list[ProbeHit]:
    """Una query contro una collection, dal backend.

    Non c'è più un `client` fra i parametri: chi interroga Qdrant è il servizio,
    e questa è la differenza fra uno strumento che *usa* il sistema e uno che lo
    **reimplementa**.
    """
    [risultato] = api_client.retrieve(
        [query_text],
        collection=config.collection,
        top_k=config.top_k,
        retrieval_mode=config.retrieval_mode,
        rerank=config.rerank,
    )
    return _hits_from(risultato)


@dataclass
class ProbeComparison:
    """How two result lists differ — the actual question in an A/B."""

    shared: list[str]
    only_a: list[str]
    only_b: list[str]
    shared_docs: list[str]
    jaccard: float
    doc_jaccard: float


def doc_of(chunk_id: str) -> str:
    """Il documento da cui un chunk viene, letto dal suo id.

    Lo schema del §3 impone `{dataset_id}:{doc_id}:{seq}`, quindi il documento è
    già dentro l'identificativo. `split(":", 2)` e non `split(":")` perché un
    `doc_id` può contenere i due punti — è la stessa cautela di
    `doc_id_from_chunk_id` in `src/retrieval/`, e le due devono restare
    d'accordo: un test lega le due implementazioni.

    Perché non importare quella: sarebbe l'unica riga di pipeline rimasta in
    questo file, per una funzione che è **il contratto degli identificativi** e
    non una decisione di recupero. Vedi la nota su A-06 in ROADMAP §11.
    """
    parti = chunk_id.split(":", 2)
    return parti[1] if len(parti) >= 2 else chunk_id


def compare_hits(a: list[ProbeHit], b: list[ProbeHit]) -> ProbeComparison:
    """Overlap between two probes, at chunk level and at document level.

    Document level matters because a routed collection re-chunks everything:
    chunk_ids never match across the two, so chunk overlap is always 0 and only
    doc overlap says whether the same source was found.  This is the same reason
    R-07 had to be read on doc_R@5.
    """
    ids_a = [h.chunk_id for h in a]
    ids_b = [h.chunk_id for h in b]
    set_a, set_b = set(ids_a), set(ids_b)
    docs_a = {doc_of(c) for c in ids_a if c}
    docs_b = {doc_of(c) for c in ids_b if c}

    def _jac(x: set, y: set) -> float:
        union = x | y
        return len(x & y) / len(union) if union else 0.0

    return ProbeComparison(
        shared=[c for c in ids_a if c in set_b],
        only_a=[c for c in ids_a if c not in set_b],
        only_b=[c for c in ids_b if c not in set_a],
        shared_docs=sorted(docs_a & docs_b),
        jaccard=_jac(set_a, set_b),
        doc_jaccard=_jac(docs_a, docs_b),
    )
