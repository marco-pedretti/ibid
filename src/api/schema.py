"""Il contratto UI ↔ API del §3.5, scritto come tipi (A-03).

Non descrive come l'interfaccia appare: descrive **cosa puo' chiedere e cosa
riceve**. Sta qui e non nella Fase 8 perche' e' un contratto dati, e perche' e'
cio' che la Fase 7 implementa.

**Perche' un secondo insieme di tipi**, quando `src/service/` ne ha gia' uno.
Perche' sono due cose diverse che oggi si somigliano: quelli del servizio sono
la forma in cui la pipeline pensa, questi sono la forma che qualcun altro puo'
leggere fra sei mesi con un client che non abbiamo scritto noi. Se fossero lo
stesso oggetto, rinominare un campo interno cambierebbe il contratto pubblico
senza che nessuno debba deciderlo — e i due `Answer` del §3.2 e i suoi
marcatori mostrano quanto costa cambiare un formato dopo che qualcosa lo ha
gia' prodotto.

Il confine e' anche una difesa. `QueryRequest` accetta **solo** la
configurazione di richiesta della classificazione di A-02: niente modello di
embedding (l'indice e' stato costruito con lui), niente indirizzi (una richiesta
non sposta la macchina), niente soglie calibrate (sono derivate da misure, non
preferenze). Un client non deve poter chiedere una cosa che non ha senso.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator
from src.config import (
    BASELINE_PROMPTS,
    REASONING_EFFORTS,
    RETRIEVAL_MODES,
    RequestConfig,
)
from src.datasets.schema import Chunk
from src.service.answer import (
    Answer,
    AnswerEvent,
    AnswerRequest,
    ChunksEvent,
    Citation,
    CitationsEvent,
    DoneEvent,
    Event,
    RetrievedChunk,
    RetrieveRequest,
    TokenEvent,
)
from src.service.catalog import CollectionInfo, DatasetInfo

# ---------------------------------------------------------------------------
# Cosa si puo' chiedere
# ---------------------------------------------------------------------------


def _fra(valore: str | None, ammessi: tuple[str, ...], campo: str) -> str | None:
    """Il valore, se e' uno di quelli che esistono.

    Gli stessi elenchi che `RequestConfig` fa rispettare, applicati **prima**:
    qui diventano un 422 con il nome del campo sbagliato, mentre piu' in basso
    sarebbero un 500. Un client che manda un valore inventato ha sbagliato lui,
    e un 500 gli direbbe che abbiamo sbagliato noi.

    Non e' duplicazione: le tuple restano una sola: cambia solo dove il rifiuto
    diventa leggibile.
    """
    if valore is not None and valore not in ammessi:
        raise ValueError(f"{campo} sconosciuto: {valore!r} (ammessi: {', '.join(ammessi)})")
    return valore


class QueryRequest(BaseModel):
    """Una domanda, e come rispondervi.

    Ogni campo ha un default tranne `query`: un client minimo manda
    `{"query": "..."}` e ottiene il comportamento del deployment. E' anche il
    motivo per cui i default **non** sono scritti qui ma presi da
    `RequestConfig.from_defaults()`: due elenchi di default divergono, e questo
    diverge verso la parte che l'utente vede.
    """

    query: str = Field(min_length=1)
    dataset_id: str = "open_ragbench"
    #: Collection Qdrant, se diversa dal dataset (`ledger_routed`).
    collection: str | None = None

    # --- recupero ---
    top_k: int | None = Field(default=None, ge=1, le=50)
    retrieval_mode: str | None = None
    rerank: bool | None = None
    query_rewrite: bool | None = None
    #: "" nessun filtro, "auto" dedotto dalla query, altrimenti il tipo (R-04).
    filter_content_type: str | None = None
    search_exact: bool | None = None
    hnsw_ef: int | None = Field(default=None, ge=1)

    # --- generazione ---
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_new_tokens: int | None = Field(default=None, ge=1)
    #: Il toggle «Ragionamento» (A-07). C'era gia' in `ConfigView`, cioe' si
    #: poteva **vedere** quale aveva girato senza poterlo scegliere. E' l'asse
    #: che C-07 misura, e su Gemma 4 e' binario: `"none"` contro il resto.
    reasoning_effort: str | None = None

    # --- il braccio e la verifica ---
    #: `false` risponde senza contesto: l'altro lato del confronto di U-03.
    rag: bool | None = None
    #: Con `rag: false`, quale prompt (U-04): "permissive" | "strict".
    baseline_prompt: str | None = None
    verify: bool | None = None

    @field_validator("retrieval_mode")
    @classmethod
    def _modalita_nota(cls, v: str | None) -> str | None:
        return _fra(v, RETRIEVAL_MODES, "retrieval_mode")

    @field_validator("baseline_prompt")
    @classmethod
    def _prompt_noto(cls, v: str | None) -> str | None:
        return _fra(v, BASELINE_PROMPTS, "baseline_prompt")

    @field_validator("reasoning_effort")
    @classmethod
    def _sforzo_noto(cls, v: str | None) -> str | None:
        """Qui e' un 422 col nome del campo; senza, sarebbe un 400 del modello
        rimbalzato come 500 — cioe' un guasto nostro per un errore altrui."""
        return _fra(v, REASONING_EFFORTS, "reasoning_effort")

    def config(self) -> RequestConfig:
        """I campi valorizzati diventano override; gli altri restano ai default.

        `None` significa «non ho un'opinione», che e' diverso da un valore. Un
        client che manda `{"query": "..."}` non sta chiedendo `top_k=0`.
        """
        override = {
            k: v for k, v in self.model_dump(
                exclude={"query", "dataset_id", "collection"}
            ).items() if v is not None
        }
        return RequestConfig.from_defaults(**override)

    def to_service(self) -> AnswerRequest:
        return AnswerRequest(
            query=self.query,
            dataset_id=self.dataset_id,
            collection=self.collection,
            config=self.config(),
        )


# ---------------------------------------------------------------------------
# Cosa si riceve
# ---------------------------------------------------------------------------


class RetrieveRequestBody(BaseModel):
    """Cercare senza rispondere, per una o molte query.

    Nato da A-06: la dashboard ha smesso di importare la pipeline e si è visto
    che dall'API mancava la metà che non genera. Un client che vuole ispezionare
    il recupero non deve pagare una generazione per averlo.

    I parametri di generazione non ci sono — non perché siano dimenticati, ma
    perché qui nessun modello viene chiamato. Chiederli renderebbe esprimibile
    una richiesta che il servizio ignorerebbe.
    """

    queries: list[str] = Field(min_length=1, max_length=500)
    dataset_id: str = "open_ragbench"
    collection: str | None = None

    top_k: int | None = Field(default=None, ge=1, le=200)
    retrieval_mode: str | None = None
    rerank: bool | None = None
    query_rewrite: bool | None = None
    filter_content_type: str | None = None
    search_exact: bool | None = None
    hnsw_ef: int | None = Field(default=None, ge=1)

    @field_validator("retrieval_mode")
    @classmethod
    def _modalita_nota(cls, v: str | None) -> str | None:
        return _fra(v, RETRIEVAL_MODES, "retrieval_mode")

    def config(self) -> RequestConfig:
        override = {
            k: v for k, v in self.model_dump(
                exclude={"queries", "dataset_id", "collection"}
            ).items() if v is not None
        }
        return RequestConfig.from_defaults(**override)

    def to_service(self) -> RetrieveRequest:
        return RetrieveRequest(
            queries=self.queries,
            dataset_id=self.dataset_id,
            collection=self.collection,
            config=self.config(),
        )


class ConfigView(BaseModel):
    """La configurazione che ha davvero girato, rimandata indietro.

    Non quella chiesta: se la richiesta non portava un `top_k`, qui c'e' quello
    che il servizio ha deciso al posto suo. Senza, due risposte diverse alla
    stessa domanda non si distinguono da due risposte instabili.
    """

    top_k: int
    retrieval_mode: str
    rerank: bool
    query_rewrite: bool
    filter_content_type: str
    search_exact: bool
    hnsw_ef: int | None
    model: str
    temperature: float
    max_new_tokens: int
    reasoning_effort: str
    rag: bool
    baseline_prompt: str
    verify: bool

    @classmethod
    def of(cls, config: RequestConfig) -> "ConfigView":
        return cls(**{campo: getattr(config, campo) for campo in cls.model_fields})


class ChunkView(BaseModel):
    """Un chunk recuperato, con tutto cio' che serve per mostrarlo e aprirlo.

    `pipeline` e `doc_genre` ci sono perche' U-05 chiede l'indicatore della
    pipeline usata: e' cio' che rende **visibile** il routing, che e' la seconda
    affermazione del §0.

    `bbox` e' sempre `null` finche' I-06 e' rinviato — nessun dataset attuale
    fornisce PDF con coordinate. Il campo c'e' e vale `null`: dichiarato assente,
    non simulato (U-06).
    """

    marker: int
    score: float
    chunk_id: str
    dataset_id: str
    doc_id: str
    doc_genre: str
    pipeline: str
    section_path: str
    page: int
    bbox: tuple[float, float, float, float] | None
    content_type: str
    text: str
    source_uri: str

    @classmethod
    def of(cls, item: RetrievedChunk) -> "ChunkView":
        c = item.chunk
        return cls(
            marker=item.marker, score=item.score,
            chunk_id=c.chunk_id, dataset_id=c.dataset_id, doc_id=c.doc_id,
            doc_genre=c.doc_genre, pipeline=c.pipeline, section_path=c.section_path,
            page=c.page, bbox=c.bbox, content_type=c.content_type,
            text=c.text, source_uri=c.source_uri,
        )

    @classmethod
    def of_chunk(cls, c: Chunk) -> "ChunkView":
        """Un chunk letto per id (`/chunk/{chunk_id}`): nessun ordinamento, nessun
        punteggio. `marker=0` e `score=0.0` dicono «non viene da un recupero»."""
        return cls(
            marker=0, score=0.0,
            chunk_id=c.chunk_id, dataset_id=c.dataset_id, doc_id=c.doc_id,
            doc_genre=c.doc_genre, pipeline=c.pipeline, section_path=c.section_path,
            page=c.page, bbox=c.bbox, content_type=c.content_type,
            text=c.text, source_uri=c.source_uri,
        )


class CitationView(BaseModel):
    """Una citazione col suo verdetto. **Nessuna viene filtrata** (U-07).

    `supported=false` non e' un errore da nascondere: e' il dato. Toglierle
    porterebbe la precisione apparente al 100% per costruzione, proprio nel
    punto in cui il progetto vuole essere misurato.
    """

    marker: int
    chunk_id: str
    claim: str
    supported: bool
    score: float
    #: Esito del verificatore numerico di C-09, o "" se non interrogato.
    #: Additivo: non sostituisce `supported`, che resta il verdetto dell'NLI.
    numeric: str

    @classmethod
    def of(cls, c: Citation) -> "CitationView":
        return cls(marker=c.marker, chunk_id=c.chunk_id, claim=c.claim,
                   supported=c.supported, score=c.score, numeric=c.numeric)


class GateView(BaseModel):
    """Il gate di astensione (C-04), e se ha girato.

    `active=false` significa «non c'era una soglia calibrata per questa
    collection e questa modalita'», che non e' «i punteggi erano alti
    abbastanza». Confonderle farebbe leggere come garanzia una cosa che non e'
    avvenuta.
    """

    active: bool
    abstain: bool
    score: float
    threshold: float | None


class AnswerResponse(BaseModel):
    """La risposta intera, per chi non streamma.

    Contiene esattamente cio' che lo stream consegna a pezzi. Non e' una
    seconda forma della verita': `answer()` e' una vista su `answer_stream()`,
    e questo oggetto e' costruito dallo stesso `Answer`.
    """

    query: str
    dataset_id: str
    collection: str
    config: ConfigView

    text: str
    #: Il testo come il modello lo ha scritto, prima del parser di C-02. C'e'
    #: perche' e' cio' che C-01 misura, e perche' una UI che vuole mostrare la
    #: riparazione deve poter mostrare da cosa.
    raw_text: str
    repaired: bool

    abstained: bool
    #: "" | "retrieval" | "model" — chi si e' astenuto. Tre stati e non un
    #: booleano: il gate costa 0 s di GPU, il modello ~11.
    abstention: str
    truncated: bool

    chunks: list[ChunkView]
    cited: list[int]
    citations: list[CitationView]
    uncited_claims: list[str]
    #: La verifica ha girato. `false` non significa «tutto verificato».
    verified: bool
    gate: GateView
    timings: dict[str, float]

    @classmethod
    def of(cls, risposta: Answer) -> "AnswerResponse":
        return cls(
            query=risposta.query,
            dataset_id=risposta.dataset_id,
            collection=risposta.collection,
            config=ConfigView.of(risposta.config),
            text=risposta.text,
            raw_text=risposta.raw_text,
            repaired=risposta.repaired,
            abstained=risposta.abstained,
            abstention=risposta.abstention,
            truncated=risposta.truncated,
            chunks=[ChunkView.of(c) for c in risposta.chunks],
            cited=risposta.cited,
            citations=[CitationView.of(c) for c in risposta.citations],
            uncited_claims=risposta.uncited_claims,
            verified=risposta.verified,
            gate=GateView(
                active=risposta.gate.active, abstain=risposta.gate.abstain,
                score=risposta.gate.score, threshold=risposta.gate.threshold,
            ),
            timings=risposta.timings,
        )


class RetrieveResponse(BaseModel):
    """I risultati, **nell'ordine delle query**.

    Una lista di liste anche quando la query è una: chi chiama non deve scrivere
    due strade a seconda di quante ne ha chieste, e un client che ne manda 200
    deve poterle riallineare senza fidarsi di un id che non abbiamo inventato.
    """

    results: list[list[ChunkView]]
    config: ConfigView


class CollectionView(BaseModel):
    """Una collection e la forma del suo indice.

    `dense_size` c'è perché è la sola cosa che smaschera l'errore più silenzioso
    possibile: un indice costruito con un modello di embedding diverso da quello
    che lo interroga restituisce risultati plausibili e privi di senso, senza
    nessun errore. `has_sparse` distingue una collection su cui `hybrid`
    funziona da una su cui userebbe solo il ramo denso.
    """

    name: str
    points: int
    dense_size: int
    has_sparse: bool

    @classmethod
    def of(cls, info: CollectionInfo) -> "CollectionView":
        return cls(name=info.name, points=info.points,
                   dense_size=info.dense_size, has_sparse=info.has_sparse)


class DatasetView(BaseModel):
    """Un dataset interrogabile, e lo stato del suo indice (U-01).

    `ready` e `n_chunks` separati: una collection che esiste ed e' vuota e' uno
    stato reale, e un frontend che lo confonde con l'assenza mostra un dataset
    che risponde sempre niente.
    """

    dataset_id: str
    collection: str
    ready: bool
    n_chunks: int

    @classmethod
    def of(cls, info: DatasetInfo) -> "DatasetView":
        return cls(dataset_id=info.dataset_id, collection=info.collection,
                   ready=info.ready, n_chunks=info.n_chunks)


# ---------------------------------------------------------------------------
# Lo stream
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ErrorEvent:
    """Il guasto, come evento e non come stato HTTP.

    **Nasce qui e non in `src/service/`**, ed e' una conseguenza del trasporto:
    quando lo stream e' cominciato, gli header sono gia' partiti e un 500 non e'
    piu' spedibile. Un errore a meta' risposta puo' solo essere un altro evento.

    Il servizio quindi solleva, come deve: e' l'orlo HTTP che traduce. Cosi' un
    CLI vede la traccia di stack e un browser vede uno stato disegnabile, senza
    che nessuno dei due debba fingere.
    """

    message: str
    #: Dove: "retrieval" | "generation" | "verification". La UI puo' dire «le
    #: fonti ci sono, la risposta no» invece di buttare via tutto.
    stage: str


#: Nome dell'evento SSE per ogni tipo. I nomi sono quelli del §3.5 e non i nomi
#: delle classi: il contratto e' verso l'esterno, e rinominare una classe non
#: deve rompere un client.
EVENT_NAMES: dict[type, str] = {
    ChunksEvent: "chunks",
    TokenEvent: "token",
    AnswerEvent: "answer",
    CitationsEvent: "citations",
    DoneEvent: "done",
    ErrorEvent: "error",
}


def to_wire(event: Event | ErrorEvent) -> tuple[str, dict]:
    """Un evento del servizio come (nome, payload) pronti per SSE.

    `done` non rimanda la risposta intera anche se `DoneEvent` la contiene: chi
    streamma ha gia' ricevuto tutto, e ripeterlo raddoppierebbe il traffico
    proprio sull'evento che chiude. Manda cio' che non e' ancora passato — i
    tempi e la configurazione che ha girato.
    """
    match event:
        case ChunksEvent():
            return "chunks", {"chunks": [ChunkView.of(c).model_dump() for c in event.chunks]}
        case TokenEvent():
            return "token", {"text": event.text}
        case AnswerEvent():
            return "answer", {
                "text": event.text,
                "raw_text": event.raw_text,
                "repaired": event.repaired,
                "abstained": event.abstained,
                "abstention": event.abstention,
                "truncated": event.truncated,
                "verification_pending": event.verification_pending,
            }
        case CitationsEvent():
            return "citations", {
                "citations": [CitationView.of(c).model_dump() for c in event.citations],
                "uncited_claims": event.uncited_claims,
            }
        case DoneEvent():
            return "done", {
                "abstained": event.answer.abstained,
                "abstention": event.answer.abstention,
                "verified": event.answer.verified,
                "timings": event.answer.timings,
                "config": ConfigView.of(event.answer.config).model_dump(),
            }
        case ErrorEvent():
            return "error", {"message": event.message, "stage": event.stage}
    raise TypeError(f"evento senza forma sul filo: {type(event).__name__}")


def sse(event: Event | ErrorEvent) -> str:
    """Un evento nel formato `text/event-stream`.

    Due righe e una riga vuota. La riga vuota **e'** il terminatore: senza,
    l'evento successivo viene letto come continuazione di questo, e il client
    resta in attesa di un pacchetto che non arrivera' mai.
    """
    nome, payload = to_wire(event)
    return f"event: {nome}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


#: Rimandati indietro da `/datasets` cosi' che il frontend non porti una copia
#: delle scelte valide. La stessa lezione di Q-06: un elenco scritto a mano in
#: due posti diverge, e il quindicesimo arriva senza che nessuno se ne accorga.
class Capabilities(BaseModel):
    """Cosa questo backend accetta. Letto, non indovinato."""

    retrieval_modes: list[str] = list(RETRIEVAL_MODES)
    baseline_prompts: list[str] = list(BASELINE_PROMPTS)
    reasoning_efforts: list[str] = list(REASONING_EFFORTS)
    #: I modelli che l'endpoint di inferenza dichiara di avere (A-07). **Vuota
    #: quando non e' raggiungibile**, e non e' un errore: i dataset non
    #: dipendono dall'LLM e devono arrivare comunque. Chi la riceve vuota
    #: ripiega sul modello di `/config`, l'unico di cui si sappia il nome.
    models: list[str] = []
    datasets: list[DatasetView] = []
    #: Le collection che esistono sul server, non solo quelle del registro.
    #: Comprende le varianti `_routed` di R-07 e quelle nate da un esperimento:
    #: sono interrogabili passando `collection`, e uno strumento che non le vede
    #: non può metterle a confronto con l'originale.
    collections: list[CollectionView] = []
