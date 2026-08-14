"""Cosa si puo' interrogare, e come rileggere una fonte citata.

Due casi d'uso piccoli, e nessuno dei due e' accessorio.

`datasets()` esiste per U-01: cambiare dataset senza riavviare, e senza che il
frontend porti una lista scritta a mano — la stessa lezione di Q-06, dove
quattordici `choices=[...]` copiate a mano dicevano cose diverse fra loro.  Il
registro e' l'unico posto in cui i dataset sono elencati; qui viene solo
chiesto a Qdrant se sono stati indicizzati davvero.

`chunk()` esiste per U-06: una citazione porta un `chunk_id`, e un link deve
poter riportare al testo esatto che l'ha sostenuta.  Senza, la verifica e'
un'affermazione che il lettore deve accettare sulla fiducia.
"""

from __future__ import annotations

from dataclasses import dataclass

import src.config as cfg
from src.datasets import registry
from src.datasets.schema import Chunk
from src.index.store import chunk_from_payload, get_by_chunk_id, get_client


@dataclass(frozen=True)
class DatasetInfo:
    """Un dataset e lo stato del suo indice.

    `ready` e `n_chunks` sono separati di proposito: una collection che esiste
    ed e' vuota e' uno stato reale — succede fra `ensure_collection` e la fine
    dell'ingestione — e va distinta da una che non c'e'.  Un frontend che le
    confonde mostra un dataset interrogabile che restituisce sempre niente.
    """

    dataset_id: str
    collection: str
    ready: bool
    n_chunks: int


def datasets(client=None) -> list[DatasetInfo]:
    """I dataset del registro, con lo stato del loro indice.

    Nell'ordine di dichiarazione del registro, che e' stabile: un elenco che
    cambia ordine a ogni chiamata fa saltare la selezione a chi lo mostra.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)

    out: list[DatasetInfo] = []
    for dataset_id in registry.dataset_ids():
        collection = dataset_id
        if client.collection_exists(collection):
            info = client.get_collection(collection)
            out.append(DatasetInfo(
                dataset_id=dataset_id,
                collection=collection,
                ready=True,
                n_chunks=info.points_count or 0,
            ))
        else:
            out.append(DatasetInfo(
                dataset_id=dataset_id, collection=collection, ready=False, n_chunks=0
            ))
    return out


def dataset_of(chunk_id: str) -> str:
    """Il dataset a cui un `chunk_id` appartiene.

    Lo schema del §3 impone `{dataset_id}:{doc_id}:{seq}`, quindi il dataset e'
    gia' dentro l'identificativo.  E' per questo che `/chunk/{chunk_id}` non ha
    bisogno di un secondo parametro: chiederlo permetterebbe di passarne uno
    incoerente con l'id, cioe' di sbagliare.
    """
    return chunk_id.split(":", 1)[0]


def chunk(chunk_id: str, collection: str | None = None, client=None) -> Chunk | None:
    """Il chunk citato, o `None` se quell'id non e' nell'indice.

    `None` e non un'eccezione: un id che non c'e' e' una risposta legittima a
    una domanda legittima — un link vecchio dopo una re-ingestione — e chi
    chiama deve poterlo distinguere da un guasto.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    payload = get_by_chunk_id(client, collection or dataset_of(chunk_id), chunk_id)
    return chunk_from_payload(payload) if payload else None
