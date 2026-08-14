"""Il caso d'uso principale: una domanda entra, una risposta citata esce.

E' la sequenza che stava in `scripts/query.py` dalla T-05, spostata qui senza
cambiarla: recupero, gate di astensione sui punteggi, generazione, riparazione
dei marcatori.  Il CLI ora ne e' un consumatore che stampa, non l'unico posto in
cui la pipeline esiste.

**Perche' il gate viene prima della generazione** e non dopo: una risposta che
verra' comunque rifiutata costa ~11 s di GPU per essere prodotta, e un
controllo che gira dopo non e' una garanzia, e' un filtro su qualcosa di gia'
inventato (C-04).

I parametri a `None` significano «prendi il default dalla configurazione», e
sono risolti in un punto solo, all'inizio di `answer()`.  E' la cucitura su cui
lavorera' A-02: quando la configurazione di richiesta smettera' di passare da
`cfg` globale, cambia *come* questi valori vengono risolti, non le firme ne' i
chiamanti.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import src.config as cfg
from src.datasets.schema import Chunk
from src.eval.retrieval_backends import RETRIEVERS
from src.generation.chat import Completion, generate_detailed
from src.generation.citation_format import is_abstention
from src.generation.citations import extract_cited, parse
from src.generation.prompt import ABSTENTION_ANSWER, SYSTEM, build_user_message
from src.index.store import chunk_from_payload, get_client
from src.retrieval.abstention import AbstentionDecision, decide

#: Perche' il sistema si e' astenuto.  Tre stati distinti, non un booleano: il
#: gate che scatta prima di generare e il modello che dichiara di non sapere
#: sono due eventi diversi, e la UI deve poterli distinguere (§3.5).
NO_ABSTENTION = ""
ABSTAINED_BY_GATE = "retrieval"
ABSTAINED_BY_MODEL = "model"


@dataclass(frozen=True)
class AnswerRequest:
    """Cosa si puo' chiedere. Tutto il resto e' configurazione, non richiesta."""

    query: str
    dataset_id: str = "open_ragbench"
    top_k: int | None = None
    retrieval_mode: str = "dense"
    #: Collection Qdrant da interrogare. `None` = `dataset_id`. Serve per le
    #: varianti `_routed` dell'ablation R-07, che sono lo stesso dataset
    #: indicizzato da una pipeline diversa.
    collection: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    """Un chunk recuperato, col numero con cui il modello lo puo' citare.

    `marker` e' 1-based e **e' la posizione nel prompt**: `[2]` nella risposta
    significa questo elemento quando `marker == 2`.  Tenerlo esplicito invece di
    affidarsi all'indice della lista e' cio' che permette a chi consuma il
    risultato di non ricostruire la stessa convenzione per conto suo.
    """

    marker: int
    score: float
    chunk: Chunk


@dataclass(frozen=True)
class Answer:
    """Tutto cio' che una risposta e': il testo, le fonti, e come e' finita.

    `raw_text` e `text` sono **entrambi** qui, e non e' ridondanza.  Il parser di
    C-02 ripara i marcatori (`[1] [2]` -> `[1][2]`) e scarta quelli che puntano a
    chunk non in contesto, quindi il testo che il modello ha prodotto e quello
    che si mostra differiscono.  Il primo e' cio' che C-01 misura e non va perso;
    il secondo e' cio' che si legge.
    """

    query: str
    dataset_id: str
    #: La collection effettivamente interrogata. Di norma e' `dataset_id`, ma
    #: non sempre — e la soglia di astensione e' calibrata *per collection*, non
    #: per dataset. Riportarla e' cio' che rende il risultato ricostruibile.
    collection: str
    chunks: list[RetrievedChunk]
    raw_text: str
    text: str
    #: `text != raw_text`: il parser ha dovuto intervenire.
    repaired: bool
    abstained: bool
    #: NO_ABSTENTION | ABSTAINED_BY_GATE | ABSTAINED_BY_MODEL
    abstention: str
    gate: AbstentionDecision
    #: I marcatori effettivamente citati, in ordine crescente.
    cited: list[int]
    #: La generazione e' stata troncata dal tetto di token. Uno stato che va
    #: mostrato e non nascosto: una risposta tagliata non ha citazioni perche'
    #: non e' arrivata a scriverle, il che non e' un difetto di formato.
    truncated: bool
    completion_tokens: int
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def uncited(self) -> list[int]:
        """Marcatori recuperati ma mai citati — il costo del contesto inutile."""
        return [c.marker for c in self.chunks if c.marker not in self.cited]


def _abstention_answer(
    request: AnswerRequest,
    collection: str,
    chunks: list[RetrievedChunk],
    gate: AbstentionDecision,
    timings: dict[str, float],
) -> Answer:
    """Il risultato quando il gate ferma tutto prima di chiamare il modello.

    Il testo e' `ABSTENTION_ANSWER`, la stessa identica stringa che il prompt
    chiede al modello di produrre: il gate senza modello e il modello devono
    astenersi con lo stesso token, o «astenuto» significa due cose (C-05).
    """
    return Answer(
        query=request.query,
        dataset_id=request.dataset_id,
        collection=collection,
        chunks=chunks,
        raw_text=ABSTENTION_ANSWER,
        text=ABSTENTION_ANSWER,
        repaired=False,
        abstained=True,
        abstention=ABSTAINED_BY_GATE,
        gate=gate,
        cited=[],
        truncated=False,
        completion_tokens=0,
        timings=timings,
    )


def answer(
    request: AnswerRequest,
    *,
    client=None,
    retrieve=None,
    generate=None,
) -> Answer:
    """Recupera, decide se vale la pena rispondere, genera, ripara i marcatori.

    Args:
        request: la domanda e i parametri che la riguardano.
        client: client Qdrant gia' aperto. `None` ne apre uno su `cfg.QDRANT_URL`.
        retrieve: `(client, collection, texts, fetch_k, filters) -> [Candidates]`.
            `None` usa il retriever della modalita' chiesta.  Iniettabile perche'
            il caso d'uso sia verificabile senza un indice acceso — la stessa
            ragione per cui `verify_answer` accetta un verificatore.
        generate: `(...) -> Completion`. `None` chiama `LLM_BASE_URL`.

    Returns:
        Un `Answer` completo in ogni caso, astensione compresa: chi chiama non
        deve mai dedurre uno stato dall'assenza di un campo.
    """
    top_k = cfg.TOP_K if request.top_k is None else request.top_k
    model = request.model or cfg.LLM_MODEL
    collection = request.collection or request.dataset_id
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    if retrieve is None:
        retrieve = RETRIEVERS[request.retrieval_mode]
    if generate is None:
        generate = generate_detailed

    t0 = time.time()
    [candidates] = retrieve(client, collection, [request.query], top_k, None)
    chunks = [
        RetrievedChunk(marker=i, score=score, chunk=chunk_from_payload(payload))
        for i, (score, payload) in enumerate(
            zip(candidates.scores[:top_k], candidates.payloads[:top_k]), 1
        )
    ]
    timings = {"retrieval_s": round(time.time() - t0, 3)}

    # Il gate legge i punteggi del recupero, non la risposta: e' l'unica cosa
    # che esiste prima di spendere la GPU.
    gate = decide(candidates.scores, collection, request.retrieval_mode)
    if gate.abstain:
        timings["total_s"] = timings["retrieval_s"]
        return _abstention_answer(request, collection, chunks, gate, timings)

    t1 = time.time()
    completion: Completion = generate(
        base_url=cfg.LLM_BASE_URL,
        model=model,
        system=SYSTEM,
        user=build_user_message(request.query, [c.chunk for c in chunks]),
        temperature=cfg.TEMPERATURE,
        max_tokens=cfg.MAX_NEW_TOKENS,
        reasoning_effort=cfg.REASONING_EFFORT,
    )
    timings["generation_s"] = round(time.time() - t1, 3)
    timings["total_s"] = round(time.time() - t0, 3)

    raw = completion.content
    text = parse(raw, len(chunks))
    return Answer(
        query=request.query,
        dataset_id=request.dataset_id,
        collection=collection,
        chunks=chunks,
        raw_text=raw,
        text=text,
        repaired=text != raw,
        abstained=is_abstention(text),
        abstention=ABSTAINED_BY_MODEL if is_abstention(text) else NO_ABSTENTION,
        gate=gate,
        cited=extract_cited(text),
        truncated=completion.truncated,
        completion_tokens=completion.completion_tokens,
        timings=timings,
    )
