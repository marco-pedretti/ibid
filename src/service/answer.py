"""Il caso d'uso principale: una domanda entra, una risposta citata esce.

E' la sequenza che stava in `scripts/query.py` dalla T-05, spostata qui senza
cambiarla: recupero, gate di astensione sui punteggi, generazione, riparazione
dei marcatori.  Il CLI ora ne e' un consumatore che stampa, non l'unico posto in
cui la pipeline esiste.

**Perche' il gate viene prima della generazione** e non dopo: una risposta che
verra' comunque rifiutata costa ~11 s di GPU per essere prodotta, e un
controllo che gira dopo non e' una garanzia, e' un filtro su qualcosa di gia'
inventato (C-04).

Da A-02 il «come rispondere» viaggia in un `RequestConfig` immutabile, risolto
una volta sola all'inizio di `answer()`: e' cio' che permette a due richieste
concorrenti di volere profondita' diverse senza contendersi un modulo.

Da A-03 la stessa funzione risponde **anche senza contesto** (`rag=False`), che
e' l'altra meta' del confronto affiancato di U-03.  Un parametro e non un
secondo percorso di codice: con due percorsi ci sarebbero due modi di astenersi,
due modi di contare i token e due modi di sbagliare.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import src.config as cfg
from src.datasets.schema import Chunk
from src.eval.citation_metrics import verify_answer
from src.generation.baseline_prompts import BASELINE_A_SYSTEM, BASELINE_B_SYSTEM
from src.generation.chat import Completion, generate_detailed
from src.generation.citation_format import is_abstention
from src.generation.citations import extract_cited, parse
from src.generation.prompt import ABSTENTION_ANSWER, SYSTEM, build_user_message
from src.index.store import chunk_from_payload, get_client
from src.retrieval.abstention import AbstentionDecision, decide
from src.retrieval.backends import RETRIEVERS
from src.retrieval.metadata_filter import build_content_type_filter, infer_content_type
from src.retrieval.query_rewrite import rewrite_batch
from src.retrieval.reranker import rerank as cross_encode

#: Perche' il sistema si e' astenuto.  Tre stati distinti, non un booleano: il
#: gate che scatta prima di generare e il modello che dichiara di non sapere
#: sono due eventi diversi, e la UI deve poterli distinguere (§3.5).
NO_ABSTENTION = ""
ABSTAINED_BY_GATE = "retrieval"
ABSTAINED_BY_MODEL = "model"

#: Il gate quando non c'e' niente da giudicare (U-03, risposta senza contesto).
#: `active=False` dice «non ha girato», che e' diverso da «ha girato e ha
#: lasciato passare» — la stessa distinzione che `threshold_for` fa quando una
#: coppia (collection, modalita') non e' calibrata.
_NO_GATE = AbstentionDecision(abstain=False, active=False, score=0.0, threshold=None)


def system_prompt(config: cfg.RequestConfig) -> str:
    """Il prompt di sistema del braccio chiesto (U-03, U-04).

    Con il recupero acceso non e' una scelta dell'utente: il prompt e' quello
    che impone il formato delle citazioni, ed e' cio' che C-01 misura. Spento,
    i due prompt sono i bracci di E-04 ed E-05 — permissivo contro severo — e la
    differenza fra loro e' il 45%→17% di invenzione che U-04 deve mostrare.
    """
    if config.rag:
        return SYSTEM
    return BASELINE_B_SYSTEM if config.baseline_prompt == "strict" else BASELINE_A_SYSTEM


@dataclass(frozen=True)
class AnswerRequest:
    """Cosa si chiede, e come rispondere.

    I due lati sono separati di proposito. **Sopra** c'e' la domanda: il testo e
    dove cercarlo. **Sotto**, in `config`, c'e' come rispondere: profondita',
    modalita', modello, se verificare. La distinzione non e' estetica — `query` e
    `dataset_id` non hanno un default sensato, `config` sì, e sono i secondi che
    due richieste concorrenti possono volere diversi senza contendersi niente.

    `config` a `None` significa «i default del deployment», risolti una volta
    all'inizio di `answer()`. Non e' una scorciatoia: e' l'unico posto sul
    percorso di servizio in cui le costanti globali vengono ancora sfiorate, e
    ci arrivano attraverso `RequestConfig.from_defaults()`.
    """

    query: str
    dataset_id: str = "open_ragbench"
    #: Collection Qdrant da interrogare. `None` = `dataset_id`. Serve per le
    #: varianti `_routed` dell'ablation R-07, che sono lo stesso dataset
    #: indicizzato da una pipeline diversa.
    collection: str | None = None
    config: cfg.RequestConfig | None = None


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
class Citation:
    """Una citazione prodotta dal modello, col verdetto su di essa.

    E' l'affermazione 1 del §0 resa un oggetto: la coppia (frase, chunk citato)
    passata al modello NLI, con l'esito.  `supported=False` non e' un errore da
    nascondere -- U-07 chiede che le citazioni non verificate siano **marcate,
    non filtrate**, ed e' per questo che `answer()` non ne toglie nessuna.

    `score` sta accanto a `supported` perche' la soglia e' una decisione presa
    altrove: un verdetto negativo a 0,49 e uno a 0,01 dicono cose diverse, e la
    differenza sparisce dopo il confronto con la soglia.
    """

    marker: int
    chunk_id: str
    claim: str
    supported: bool
    score: float
    #: L'esito del verificatore numerico di C-09, o "" se non interrogato.
    #: Additivo: non sostituisce `supported`, che resta il verdetto dell'NLI.
    numeric: str = ""


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
    #: La configurazione che ha davvero girato, risolta. Non quella chiesta: se
    #: la richiesta non ne portava una, qui c'e' cosa il servizio ha deciso al
    #: posto suo. Senza, due risposte diverse alla stessa domanda non sono
    #: distinguibili da due risposte instabili.
    config: cfg.RequestConfig
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
    #: Un verdetto per ogni coppia (frase, chunk citato). Vuota quando la
    #: verifica non e' stata chiesta — distinguibile da "verificata e nessuna
    #: citazione" guardando `verified`.
    citations: list[Citation]
    #: Le frasi verificabili che non citano niente. Il costo nascosto della
    #: precisione: si alza citando di meno, e questa lista e' cio' che lo mostra.
    uncited_claims: list[str]
    #: La verifica ha girato. `False` significa "verdetti non ancora disponibili",
    #: che per §3.5 e' uno stato che la UI deve poter disegnare — non un sinonimo
    #: di "tutto verificato".
    verified: bool
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
    config: cfg.RequestConfig,
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
        config=config,
        chunks=chunks,
        raw_text=ABSTENTION_ANSWER,
        text=ABSTENTION_ANSWER,
        repaired=False,
        abstained=True,
        abstention=ABSTAINED_BY_GATE,
        gate=gate,
        cited=[],
        # Non c'e' niente da verificare, ma la verifica *ha* girato: la risposta
        # e' definitiva. `verified=False` significherebbe "aspetta i verdetti",
        # e qui non ne arriveranno altri.
        citations=[],
        uncited_claims=[],
        verified=True,
        truncated=False,
        completion_tokens=0,
        timings=timings,
    )


def _verify(
    text: str,
    chunks: list[RetrievedChunk],
    verifier,
) -> tuple[list[Citation], list[str]]:
    """I verdetti su una risposta, piu' le frasi che non citano niente.

    `verify_answer` vive in `src/eval/` perche' e' nata come metrica di C-03.
    Non e' solo una metrica: e' la funzionalita' dell'affermazione 1 del §0, e
    il percorso di servizio ne ha bisogno quanto l'harness.  Spostarla e'
    giusto e non si fa qui — sarebbe un refactor mescolato a un cambio di
    comportamento, che §15 vieta esplicitamente.
    """
    claims, verdicts = verify_answer(
        text,
        [{"chunk_id": c.chunk.chunk_id, "text": c.chunk.text} for c in chunks],
        verifier=verifier,
    )
    citations = [
        Citation(
            marker=v.marker,
            chunk_id=v.chunk_id,
            claim=v.claim,
            supported=v.supported,
            score=v.score,
            numeric=v.numeric,
        )
        for v in verdicts
    ]
    uncited = [c.text for c in claims if c.is_verifiable and not c.is_cited]
    return citations, uncited


def answer(
    request: AnswerRequest,
    *,
    client=None,
    retrieve=None,
    generate=None,
    verify=None,
) -> Answer:
    """Recupera, decide se vale la pena rispondere, genera, ripara i marcatori.

    Args:
        request: la domanda e i parametri che la riguardano.
        client: client Qdrant gia' aperto. `None` ne apre uno su `cfg.QDRANT_URL`.
        retrieve: `(client, collection, texts, fetch_k, filters, config)
            -> [Candidates]`. `None` usa il retriever della modalita' chiesta.
            Iniettabile perche'
            il caso d'uso sia verificabile senza un indice acceso — la stessa
            ragione per cui `verify_answer` accetta un verificatore.
        generate: `(...) -> Completion`. `None` chiama `LLM_BASE_URL`.
        verify: `(testo_chunk, claim) -> Verdict`. `None` carica il modello NLI
            di `cfg.ENTAILMENT_MODEL`.

    Returns:
        Un `Answer` completo in ogni caso, astensione compresa: chi chiama non
        deve mai dedurre uno stato dall'assenza di un campo.
    """
    # L'unico punto del percorso di servizio che sfiora ancora le costanti
    # globali, e ci arriva attraverso `from_defaults()`. Da qui in giu' esiste
    # solo `config`: quello che due richieste concorrenti non si scambiano.
    config = request.config or cfg.RequestConfig.from_defaults()
    collection = request.collection or request.dataset_id
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    if retrieve is None:
        retrieve = RETRIEVERS[config.retrieval_mode]
    if generate is None:
        generate = generate_detailed

    t0 = time.time()
    chunks: list[RetrievedChunk] = []
    scores: list[float] = []
    if config.rag:
        text_query = request.query
        if config.query_rewrite:
            [text_query] = rewrite_batch(
                [request.query], base_url=cfg.LLM_BASE_URL, model=config.rewrite_model
            )

        # R-04: il filtro sul tipo di contenuto, dedotto dalla query o imposto.
        query_filter = None
        if config.filter_content_type == "auto":
            if (ct := infer_content_type(text_query)):
                query_filter = build_content_type_filter(ct)
        elif config.filter_content_type:
            query_filter = build_content_type_filter(config.filter_content_type)

        # Col reranker si pesca da un bacino piu' largo di quello che finira' nel
        # prompt: il cross-encoder deve avere qualcosa fra cui scegliere.
        fetch_k = max(config.rerank_fetch_k, config.top_k) if config.rerank else config.top_k
        [candidates] = retrieve(
            client, collection, [text_query], fetch_k,
            [query_filter] if query_filter is not None else None, config,
        )

        scores, payloads = candidates.scores, candidates.payloads
        if config.rerank:
            ranked = cross_encode(text_query, payloads, config.reranker_model, top_n=config.top_k)
            scores = [r.score for r in ranked]
            payloads = [r.payload for r in ranked]

        chunks = [
            RetrievedChunk(marker=i, score=score, chunk=chunk_from_payload(payload))
            for i, (score, payload) in enumerate(
                zip(scores[: config.top_k], payloads[: config.top_k]), 1
            )
        ]
    timings = {"retrieval_s": round(time.time() - t0, 3)}

    # Il gate legge i punteggi del recupero, non la risposta: e' l'unica cosa
    # che esiste prima di spendere la GPU. Sui punteggi **effettivi**, quindi
    # dopo il reranker — ed e' anche il motivo per cui la soglia e' calibrata
    # per modalita': i punteggi di un cross-encoder non vivono nella stessa
    # scala di quelli del coseno, e `threshold_for` restituisce None fuori dalla
    # modalita' calibrata invece di applicare una soglia che non significa nulla.
    #
    # Senza recupero (U-03) non ci sono punteggi da leggere, quindi il gate non
    # e' "superato": e' **inattivo**, ed e' quello che `decide([])` dice.
    gate = decide(scores, collection, config.retrieval_mode) if config.rag else _NO_GATE
    if gate.abstain:
        timings["total_s"] = timings["retrieval_s"]
        return _abstention_answer(request, config, collection, chunks, gate, timings)

    t1 = time.time()
    completion: Completion = generate(
        base_url=cfg.LLM_BASE_URL,
        model=config.model,
        system=system_prompt(config),
        user=build_user_message(request.query, [c.chunk for c in chunks])
        if config.rag else request.query,
        temperature=config.temperature,
        max_tokens=config.max_new_tokens,
        reasoning_effort=config.reasoning_effort,
    )
    timings["generation_s"] = round(time.time() - t1, 3)

    raw = completion.content
    # Senza contesto nessun marcatore e' valido, e `parse` li toglierebbe tutti:
    # il testo mostrato non sarebbe piu' quello che il modello ha scritto, che e'
    # esattamente cio' che U-03 vuole far vedere.
    text = parse(raw, len(chunks)) if config.rag else raw
    abstained = is_abstention(text)

    citations: list[Citation] = []
    uncited_claims: list[str] = []
    if config.verify and not abstained:
        t2 = time.time()
        citations, uncited_claims = _verify(text, chunks, verify)
        timings["verification_s"] = round(time.time() - t2, 3)
    timings["total_s"] = round(time.time() - t0, 3)

    return Answer(
        query=request.query,
        dataset_id=request.dataset_id,
        collection=collection,
        config=config,
        chunks=chunks,
        raw_text=raw,
        text=text,
        repaired=text != raw,
        abstained=abstained,
        abstention=ABSTAINED_BY_MODEL if abstained else NO_ABSTENTION,
        gate=gate,
        cited=extract_cited(text),
        citations=citations,
        uncited_claims=uncited_claims,
        verified=config.verify,
        truncated=completion.truncated,
        completion_tokens=completion.completion_tokens,
        timings=timings,
    )
