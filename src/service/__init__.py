"""Lo strato di servizio: un caso d'uso, una funzione (A-01).

Esiste per una ragione sola, e vale la pena scriverla prima del codice: **la
pipeline non deve stare dentro un endpoint**.  Finora l'unico percorso di
servizio era `scripts/query.py`, che faceva retrieval, gate di astensione,
generazione e riparazione dei marcatori *e poi* stampava.  Un secondo
consumatore -- l'API della Fase 7 -- avrebbe dovuto riscrivere quella sequenza,
e da quel momento due copie avrebbero potuto divergere senza che nessun test se
ne accorgesse.

Qui dentro non si stampa e non si serializza.  Una funzione prende una richiesta
e restituisce un risultato; chi chiama decide se diventa testo su un terminale
(`scripts/query.py`) o JSON su una socket (`src/api/`).  E' l'unico modo in cui
il criterio di A-01 -- «la stessa richiesta dalla CLI e dall'API produce lo
stesso risultato» -- puo' essere verificato invece che sperato.
"""

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
    answer,
    answer_stream,
    retrieve_chunks,
)
from src.service.catalog import DatasetInfo, chunk, dataset_of, datasets

__all__ = [
    "Answer",
    "AnswerEvent",
    "AnswerRequest",
    "ChunksEvent",
    "Citation",
    "CitationsEvent",
    "DatasetInfo",
    "DoneEvent",
    "Event",
    "RetrieveRequest",
    "RetrievedChunk",
    "TokenEvent",
    "answer",
    "answer_stream",
    "chunk",
    "dataset_of",
    "datasets",
    "retrieve_chunks",
]
