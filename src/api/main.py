"""Gli endpoint HTTP (A-04).

**Questo file non decide niente.** La pipeline sta in `src/service/`, la forma
delle risposte in `src/api/schema.py`; qui resta il trasporto: leggere una
richiesta, chiamare un caso d'uso, scrivere il risultato. E' il criterio di A-01
applicato all'altro consumatore — «nessun endpoint contiene logica di pipeline»
— e la prova che regge e' il test che confronta la stessa richiesta dalla CLI e
da qui.

Il confine, detto una volta: **il backend espone HTTP, il frontend e' un client
come un altro.** Chiunque puo' scriverne un secondo, o nessuno. La demo React
della Fase 8 e' *un* consumatore dell'API, non il suo scopo.
"""

from __future__ import annotations

from collections.abc import Iterator

import src.config as cfg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.api.schema import (
    AnswerResponse,
    Capabilities,
    ChunkView,
    DatasetView,
    ErrorEvent,
    QueryRequest,
    sse,
)
from src.datasets import registry
from src.service import answer, answer_stream, chunk, dataset_of, datasets

app = FastAPI(
    title="ibid",
    summary="RAG con citazioni verificate a livello di frase",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Vivo, e nient'altro.

    **Non interroga Qdrant di proposito.** `depends_on: service_healthy` di U-09
    usa questo endpoint per sapere quando il backend e' pronto ad accettare
    richieste; se rispondesse solo con l'indice acceso, un avvio in cui Qdrant
    parte dopo si bloccherebbe a vicenda. Se il vero interesse e' «i dati ci
    sono», la risposta e' in `/datasets`, dove `ready` lo dice per dataset.
    """
    return {"status": "ok"}


@app.get("/datasets", response_model=Capabilities)
def list_datasets() -> Capabilities:
    """Cosa si puo' chiedere a questo backend (U-01).

    Non solo i dataset: anche le modalita' di retrieval e i prompt del baseline.
    Un frontend che li portasse per conto suo sarebbe la quindicesima copia
    scritta a mano di quella lista, che e' esattamente cio' che Q-06 ha tolto di
    mezzo dal lato Python.
    """
    return Capabilities(datasets=[DatasetView.of(d) for d in datasets()])


@app.get("/chunk/{chunk_id:path}", response_model=ChunkView)
def get_chunk(
    chunk_id: str,
    collection: str | None = Query(default=None),
) -> ChunkView:
    """La fonte dietro una citazione (U-06).

    `:path` nel percorso perche' un `chunk_id` **contiene i due punti** per
    contratto (`{dataset_id}:{doc_id}:{seq}`), e il dataset non e' un secondo
    parametro proprio perche' e' gia' li' dentro.

    404 quando l'id non c'e': un link vecchio dopo una re-ingestione e' una
    domanda legittima con una risposta legittima, e va distinta da un guasto —
    che infatti resta un 500.
    """
    if dataset_of(chunk_id) not in registry.dataset_ids():
        raise HTTPException(status_code=400, detail=f"chunk_id malformato: {chunk_id!r}")
    trovato = chunk(chunk_id, collection=collection)
    if trovato is None:
        raise HTTPException(status_code=404, detail=f"chunk non trovato: {chunk_id!r}")
    return ChunkView.of_chunk(trovato)


@app.post("/query", response_model=AnswerResponse)
def post_query(request: QueryRequest) -> AnswerResponse:
    """Una domanda, una risposta intera.

    Esiste accanto a `/query/stream` perche' non tutti i client streammano — un
    `curl`, uno script, la dashboard di A-06 — e perche' e' la forma su cui il
    test di equivalenza con la CLI e' scritto. Non e' una seconda pipeline:
    `answer()` e' una vista su `answer_stream()`.
    """
    return AnswerResponse.of(answer(request.to_service()))


@app.post("/query/stream")
def post_query_stream(request: QueryRequest) -> StreamingResponse:
    """La stessa domanda, mentre la risposta si forma (§3.5).

    Gli eventi e il loro ordine sono il contratto, non un dettaglio di questo
    file: `chunks` prima dei token e' cio' che rende realizzabile U-02.

    **Gli errori diventano un evento e non uno stato HTTP**, e non e' una
    scelta di stile: quando il primo byte e' partito, lo stato della risposta e'
    gia' 200 e non e' piu' modificabile. Il servizio continua a sollevare — cosi'
    un CLI vede la traccia di stack — ed e' qui che si traduce.
    """

    def eventi() -> Iterator[str]:
        try:
            for evento in answer_stream(request.to_service()):
                yield sse(evento)
        except Exception as e:  # noqa: BLE001 — a stream aperto non c'e' un 500 da mandare
            yield sse(ErrorEvent(message=f"{type(e).__name__}: {e}", stage="pipeline"))

    return StreamingResponse(
        eventi(),
        media_type="text/event-stream",
        headers={
            # Un proxy che bufferizza annulla lo streaming senza rompere niente:
            # il client riceve tutto insieme alla fine e non ha modo di
            # accorgersi che sarebbe dovuto arrivare a pezzi.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/config")
def effective_config() -> dict:
    """I default di **questo** deployment, per chi vuole saperli prima di chiedere.

    Solo la configurazione di richiesta: niente indirizzi, niente soglie
    calibrate, niente modello di embedding. E' la stessa classificazione di A-02
    che `QueryRequest` fa rispettare in entrata, applicata in uscita — un
    endpoint che rivelasse `QDRANT_URL` racconterebbe la topologia della rete a
    chiunque.
    """
    from src.api.schema import ConfigView

    return ConfigView.of(cfg.RequestConfig.from_defaults()).model_dump()
