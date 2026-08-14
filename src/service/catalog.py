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

`models()` e' arrivata con A-07, per la stessa ragione di `datasets()`: e' il
backend a sapere cosa c'e', e il browser non deve parlare con Ollama.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import src.config as cfg
from src.datasets import registry
from src.datasets.schema import Chunk
from src.generation import chat
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


@dataclass(frozen=True)
class CollectionInfo:
    """Una collection e la forma del suo indice.

    I tre campi oltre al nome non sono statistica per curiosità: sono ciò che
    dice se l'indice è quello che si crede. `dense_size` diverso da quello del
    modello di embedding significa che l'indice è stato costruito da un altro,
    e da lì ogni risultato è plausibile e privo di senso — **senza errore**.
    `has_sparse` distingue una collection su cui `hybrid` funziona da una su
    cui restituirebbe solo il ramo denso.
    """

    name: str
    points: int
    dense_size: int
    has_sparse: bool


def collections(client=None) -> list[CollectionInfo]:
    """Le collection che esistono davvero su Qdrant, in ordine.

    **Non è la stessa cosa di `datasets()`**, e la differenza è il motivo per
    cui esistono entrambe. Il registro dice quali dataset il progetto conosce;
    questa dice cosa c'è nel server — comprese le varianti `_routed` di R-07 e
    le collection nate da un esperimento, che nessun registro conterrà mai.

    Serve a chi ispeziona invece di interrogare: una collection che il registro
    non nomina è comunque interrogabile passando `collection`, e uno strumento
    di debug che non la vede non può metterla a confronto con l'originale.
    Prima di A-06 la dashboard le elencava chiedendole a Qdrant per conto suo.
    """
    if client is None:
        client = get_client(cfg.QDRANT_URL)
    fuori: list[CollectionInfo] = []
    for c in sorted(client.get_collections().collections, key=lambda x: x.name):
        info = client.get_collection(c.name)
        vettori = info.config.params.vectors
        dense = vettori.get("dense") if isinstance(vettori, dict) else vettori
        fuori.append(CollectionInfo(
            name=c.name,
            points=info.points_count or 0,
            dense_size=getattr(dense, "size", 0) or 0,
            has_sparse=bool(info.config.params.sparse_vectors),
        ))
    return fuori


def models(
    base_url: str | None = None,
    *,
    fetch: Callable[[str, int], dict] | None = None,
) -> list[str]:
    """I modelli che l'endpoint di inferenza dichiara di avere (A-07).

    **La lista vuota non e' un errore, ed e' una scelta.** `/datasets` la
    include, e un frontend la chiede all'avvio: se questa funzione sollevasse
    quando l'LLM e' spento, tutta la risposta fallirebbe — compresi i dataset,
    che con l'LLM non c'entrano niente. E' lo stesso difetto per cui `/health`
    non interroga Qdrant.

    Chi la riceve vuota mostra il modello dei default (`/config`), che e'
    l'unico di cui si sappia il nome con certezza, e dice che l'elenco non e'
    disponibile. **Dichiarare l'assenza, non simularla**: aggiungere qui il
    modello configurato per non restituire mai una lista vuota affermerebbe
    che esiste, che e' precisamente cio' che non si e' potuto verificare.
    """
    try:
        return chat.list_models(base_url or cfg.LLM_BASE_URL, fetch=fetch)
    except RuntimeError:
        return []


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
