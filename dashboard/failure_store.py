"""Batch retrieval over a golden set, ranked worst-first.

The old Golden Query Browser showed the first 500 queries in file order and made
you click a button per query to see retrieval.  Queries that succeed teach
nothing; this module runs a batch and sorts by failure so the ones that broke
surface first.

Da A-06 **il recupero lo fa il backend**: qui restava una copia della pipeline
-- embedding, fusione RRF, cross-encoder -- che dopo A-02 leggeva ancora `cfg`
globale invece della configurazione di richiesta. Quel che resta e' il
punteggio, che e' la domanda della dashboard e non del servizio.

Both chunk-level and document-level recall are computed.  They answer different
questions and can disagree loudly: a routed collection re-chunks the corpus, so
its chunk_ids never match the qrels and chunk recall is structurally 0 while doc
recall is meaningful.  Reporting only one of them is how that gets misread.

No Streamlit import: testable without a running app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from src.datasets.golden import GoldenQuery

from dashboard import api_client
from dashboard.retrieval_probe import ProbeConfig, doc_of


@dataclass
class QueryOutcome:
    """What one golden query got back, and whether it was right."""

    query: GoldenQuery
    retrieved_ids: list[str]
    payloads: list[dict] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    recall: float = 0.0
    doc_recall: float = 0.0

    @property
    def golden_ids(self) -> set[str]:
        return {qr.chunk_id for qr in self.query.qrels if qr.relevance >= 1}

    @property
    def golden_docs(self) -> set[str]:
        return {doc_of(c) for c in self.golden_ids}

    @property
    def is_failure(self) -> bool:
        """Nothing relevant retrieved, at either granularity."""
        return self.doc_recall == 0.0

    @property
    def top_score(self) -> float:
        return self.scores[0] if self.scores else 0.0


def _recall(relevant: set[str], retrieved: list[str]) -> float:
    if not relevant:
        return 0.0
    return len(relevant & set(retrieved)) / len(relevant)


def score_outcome(outcome: QueryOutcome) -> QueryOutcome:
    """Fill in chunk-level and document-level recall."""
    outcome.recall = _recall(outcome.golden_ids, outcome.retrieved_ids)
    retrieved_docs = [doc_of(c) for c in outcome.retrieved_ids if c]
    outcome.doc_recall = _recall(outcome.golden_docs, retrieved_docs)
    return outcome


def evaluate_queries(
    queries: list[GoldenQuery],
    config: ProbeConfig,
    on_progress: Callable[[int, int], None] | None = None,
    batch: int = 64,
) -> list[QueryOutcome]:
    """Run `queries` against `config.collection` and score each one.

    Da A-06 il recupero lo fa il backend. **Il batch resta**, ed era la ragione
    per cui questa funzione esisteva separata: 200 query in una chiamata sono un
    viaggio di rete e una passata di embedding, 200 chiamate sono 200 di
    entrambi. E' anche la ragione per cui `POST /retrieve` accetta una lista.

    Il batch e' spezzato in blocchi da 64 per due motivi che vanno insieme:
    l'avanzamento diventa visibile mentre gira -- una barra che si muove solo
    alla fine non e' una barra -- e un blocco che fallisce non porta via le
    risposte dei precedenti.

    Il punteggio invece resta qui: e' la domanda della dashboard, non del
    servizio. Recall a livello di chunk e di documento non sono metriche che
    l'API deve conoscere; sono il modo in cui questo strumento legge cio' che
    l'API gli ha dato.
    """
    if not queries:
        return []

    outcomes: list[QueryOutcome] = []
    total = len(queries)
    for start in range(0, total, batch):
        fetta = queries[start : start + batch]
        risultati = api_client.retrieve(
            [q.query_text for q in fetta],
            collection=config.collection,
            top_k=config.top_k,
            retrieval_mode=config.retrieval_mode,
            rerank=config.rerank,
        )
        for query, chunks in zip(fetta, risultati):
            outcomes.append(
                score_outcome(
                    QueryOutcome(
                        query=query,
                        retrieved_ids=[c["chunk_id"] for c in chunks],
                        scores=[c["score"] for c in chunks],
                        payloads=list(chunks),
                    )
                )
            )
        if on_progress:
            on_progress(len(outcomes), total)

    return outcomes


def sort_by_failure(outcomes: list[QueryOutcome]) -> list[QueryOutcome]:
    """Worst first: lowest doc recall, then lowest chunk recall."""
    return sorted(outcomes, key=lambda o: (o.doc_recall, o.recall))


def failure_summary(outcomes: list[QueryOutcome]) -> dict[str, float]:
    """Aggregate over one dataset only — never mix datasets here (§15)."""
    n = len(outcomes)
    if n == 0:
        return {"n": 0, "mean_recall": 0.0, "mean_doc_recall": 0.0,
                "n_failures": 0, "failure_rate": 0.0}
    n_fail = sum(1 for o in outcomes if o.is_failure)
    return {
        "n": n,
        "mean_recall": sum(o.recall for o in outcomes) / n,
        "mean_doc_recall": sum(o.doc_recall for o in outcomes) / n,
        "n_failures": n_fail,
        "failure_rate": n_fail / n,
    }


def chunk_id_mismatch(outcomes: list[QueryOutcome]) -> bool:
    """True when chunk recall is structurally zero but documents are found.

    Signals that the collection was built with a different chunking pipeline
    than the one the qrels were written against — the R-07 situation.  Without
    this check a routed collection just looks catastrophically broken.
    """
    if not outcomes:
        return False
    return (
        all(o.recall == 0.0 for o in outcomes)
        and any(o.doc_recall > 0.0 for o in outcomes)
    )
