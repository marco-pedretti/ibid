"""Qdrant operations: create collection, upsert, search.

Collections use named vectors:
  - "dense"  : cosine similarity, size from EMBEDDING_MODEL (1024 for multilingual-e5-large)
  - "sparse" : Qdrant sparse index, BM25 weights (Qdrant/bm25)

This layout matches R-01 hybrid RRF: query both vectors, fuse results.
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    QueryRequest,
    QueryResponse,
    SearchParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from src.datasets.schema import Chunk

#: Quante ricerche per richiesta HTTP. Batch piu' grandi evitano l'esaurimento
#: dei socket su Windows (WinError 10048) quando si valutano migliaia di query.
_SEARCH_BATCH = 256
_UPSERT_BATCH = 256


def get_client(url: str) -> QdrantClient:
    return QdrantClient(url=url, timeout=60)


def ensure_collection(client: QdrantClient, name: str, dense_size: int) -> None:
    """Create the collection if absent; repair the IDF modifier if present.

    R-08. `modifier=IDF` is not decoration: fastembed's BM25 leaves the IDF
    component out of the vectors *on purpose*, because it depends on corpus
    statistics the client does not have. Qdrant supplies it at query time — but
    only if the sparse index is told to. Without it the score is term frequency
    alone, and a common word weighs as much as a rare one.

    Existing collections are repaired in place rather than recreated, because
    the sparse *vectors* were never wrong: the missing half lives in the index
    configuration. See `ensure_idf_modifier`.
    """
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config={"dense": VectorParams(size=dense_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )
        ensure_payload_indexes(client, name)
        return
    ensure_idf_modifier(client, name)
    ensure_payload_indexes(client, name)


def ensure_idf_modifier(client: QdrantClient, name: str) -> bool:
    """Set `modifier=IDF` on an existing sparse index. Returns True if changed.

    **In place, never delete-and-recreate.** The dense vectors of these
    collections cost hours of GPU (open_ragbench and ledger together are ~66k
    chunks, and the routed variants ~326k); dropping them to change one field of
    the sparse configuration would throw away every measurement that depends on
    them, C-06 included. `update_collection` alters the sparse params and leaves
    the points untouched — verified against the running instance before this was
    written.

    Idempotent: returns False when the modifier is already IDF, so it can be
    called on every ingest without a second thought.
    """
    info = client.get_collection(name)
    sparse = (info.config.params.sparse_vectors or {}).get("sparse")
    if sparse is not None and sparse.modifier == Modifier.IDF:
        return False
    client.update_collection(
        collection_name=name,
        sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
    )
    return True


#: I campi su cui si cerca **per valore** invece che per vettore, e che quindi
#: hanno bisogno di un indice payload. Sono due, e non sono una scelta di
#: performance generica: sono i due percorsi in cui il progetto interroga
#: l'indice senza un embedding in mano.
#:
#: - `chunk_id` — ogni citazione cliccata in U-06 passa da `get_by_chunk_id`,
#:   che senza indice **scandisce i payload** della collection.
#: - `doc_id` — `documents()` e `document_chunks()` di A-07, cioe' l'intero
#:   esploratore del corpus.
PAYLOAD_INDEXED_FIELDS: tuple[str, ...] = ("chunk_id", "doc_id")


def ensure_payload_indexes(client: QdrantClient, name: str) -> list[str]:
    """Crea gli indici payload mancanti. Restituisce quelli aggiunti.

    **Si aggiunge a una collection esistente senza rifare i vettori**, esattamente
    come il modificatore IDF di R-08 — e per la stessa ragione vale la pena
    dirlo: le collection di questo progetto sono ore di GPU, e un rimedio che
    richiedesse di ricostruirle non sarebbe un rimedio.

    Misurato il 2026-08-14 su `ledger` (47.110 punti): la creazione costa 0,77 s
    una volta sola, e la domanda «quali documenti ci sono e con quanti chunk»
    passa da **2,07 s a 0,025 s**. Su `ledger_routed` (228.331 punti) la
    scansione sarebbe dell'ordine dei 10 s, cioe' una pagina inusabile.

    Idempotente: si puo' chiamare a ogni ingestione senza pensarci. Il confronto
    e' con lo schema che Qdrant riporta, non con una lista tenuta da noi — cosi'
    un indice cancellato a mano dalla console viene ricreato invece di essere
    dato per esistente.
    """
    presenti = set(client.get_collection(name).payload_schema or {})
    aggiunti = []
    for campo in PAYLOAD_INDEXED_FIELDS:
        if campo in presenti:
            continue
        client.create_payload_index(
            collection_name=name,
            field_name=campo,
            field_schema=PayloadSchemaType.KEYWORD,
            wait=True,
        )
        aggiunti.append(campo)
    return aggiunti


def delete_collection(client: QdrantClient, name: str) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)


def upsert(
    client: QdrantClient,
    collection: str,
    chunks: list[Chunk],
    dense_vecs: list[list[float]],
    sparse_vecs: list[SparseVector],
    id_offset: int = 0,
) -> None:
    points = [
        PointStruct(
            id=id_offset + i,
            vector={"dense": dv, "sparse": sv},
            payload={
                "chunk_id": c.chunk_id,
                "dataset_id": c.dataset_id,
                "doc_id": c.doc_id,
                "doc_genre": c.doc_genre,
                "pipeline": c.pipeline,
                "section_path": c.section_path,
                "content_type": c.content_type,
                "text": c.text,
                "page": c.page,
                "source_uri": c.source_uri,
            },
        )
        for i, (c, dv, sv) in enumerate(zip(chunks, dense_vecs, sparse_vecs))
    ]
    for start in range(0, len(points), _UPSERT_BATCH):
        client.upsert(
            collection_name=collection,
            points=points[start : start + _UPSERT_BATCH],
        )


def chunk_from_payload(payload: dict) -> Chunk:
    """L'inverso di `upsert`: il payload di Qdrant torna a essere un `Chunk`.

    Sta qui accanto alla funzione che quel payload lo scrive, perche' le due
    devono cambiare insieme: un campo aggiunto sopra e non letto qui sparisce
    silenziosamente al ritorno.

    Ne esistevano due copie identiche -- in `scripts/query.py` e in
    `citation_harness.py` -- entrambe chiamate `_payload_to_chunk` ed entrambe
    private.  Private per modo di dire: tre script la importavano attraverso
    l'underscore, esattamente come `_RETRIEVERS` prima che diventasse
    `RETRIEVERS`.  Una funzione con cinque chiamanti non e' privata, e' solo
    scritta nel posto sbagliato.

    `bbox` e' sempre `None`: nel payload non c'e' (I-06 e' rinviato, nessun
    dataset attuale fornisce PDF con coordinate).  Dichiararlo assente e'
    diverso dal simularlo -- vedi §3.5.
    """
    return Chunk(
        chunk_id=payload["chunk_id"],
        dataset_id=payload["dataset_id"],
        doc_id=payload["doc_id"],
        doc_genre=payload.get("doc_genre", ""),
        pipeline=payload.get("pipeline", ""),
        section_path=payload.get("section_path", ""),
        page=payload.get("page", 0),
        bbox=None,
        content_type=payload.get("content_type", "text"),
        text=payload["text"],
        source_uri=payload["source_uri"],
    )


def get_by_chunk_id(client: QdrantClient, collection: str, chunk_id: str) -> dict | None:
    """Il payload di un chunk dato il suo `chunk_id`, o `None` se non c'e'.

    Non e' `retrieve()`: l'id del punto e' un intero progressivo assegnato
    dall'ingestione, mentre `chunk_id` sta nel payload.  Sono due
    identificatori diversi e solo il secondo e' stabile fra una re-ingestione e
    l'altra, quindi e' il secondo che finisce nelle citazioni e nei link
    profondi (U-06).

    Il filtro scandisce i payload: senza indice il costo cresce con la
    collection.  Accettabile per una lettura singola dietro un link; se
    diventasse un percorso caldo, il rimedio e' `create_payload_index` su
    `chunk_id`, che si aggiunge a una collection esistente senza rifare i
    vettori — come l'IDF di R-08.
    """
    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=Filter(
            must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    return points[0].payload if points else None


def list_documents(client: QdrantClient, collection: str, limit: int = 2000) -> list[tuple[str, int]]:
    """`(doc_id, n_chunk)` per ogni documento della collection, in ordine.

    Usa `facet`, che conta lato server sull'indice payload: su `ledger` sono
    0,025 s contro i 2,07 s di una scansione dei payload (A-07). Richiede
    l'indice su `doc_id` — vedi `ensure_payload_indexes`.

    `exact=True` perche' il numero e' cio' che si mostra: un conteggio
    approssimato in una lista di documenti si legge come esatto e non lo e'.

    L'ordine e' alfabetico, non quello di `facet` (che ordina per conteggio
    decrescente): una lista che si riordina quando cambia l'indicizzazione fa
    perdere il posto a chi la sta sfogliando.
    """
    risposta = client.facet(collection_name=collection, key="doc_id", limit=limit, exact=True)
    return sorted((str(h.value), int(h.count)) for h in risposta.hits)


def payloads_of_document(
    client: QdrantClient, collection: str, doc_id: str, limit: int = 2000
) -> list[dict]:
    """I payload dei chunk di un documento, **in ordine di sequenza**.

    L'ordinamento e' lessicografico sul `chunk_id` e non e' un ripiego: lo
    schema del §3 impone `{dataset_id}:{doc_id}:{seq}` con `seq` a quattro cifre
    zero-riempite, quindi l'ordine dei caratteri e' l'ordine dei numeri. Qdrant
    non puo' ordinare per questo campo (e' keyword, non numerico), e ordinare in
    Python qualche centinaio di chunk costa niente.

    Serve all'esploratore del corpus: mostrare **come** un documento e' stato
    spezzato ha senso solo nell'ordine in cui e' stato spezzato.
    """
    trovati: list[dict] = []
    offset = None
    while True:
        punti, offset = client.scroll(
            collection_name=collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=min(256, limit - len(trovati)),
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        trovati.extend(p.payload for p in punti)
        if offset is None or len(trovati) >= limit:
            break
    return sorted(trovati, key=lambda p: p["chunk_id"])


def search_params(exact: bool, hnsw_ef: int | None) -> SearchParams | None:
    """Come cercare nel grafo HNSW, o se saltarlo del tutto (R-11).

    `None` quando nessuno dei due e' impostato: lascia a Qdrant il suo default,
    che e' lo stato in cui e' stato misurato tutto ciò che precede R-11.  Un
    `SearchParams` vuoto non sarebbe la stessa cosa da leggere, e questa
    funzione esiste perche' la decisione stia in un posto solo invece che
    ripetuta in ogni sito di ricerca.

    **Leggeva `cfg` da sola fino ad A-02.** Ora i due valori arrivano da fuori:
    su un servizio sono configurazione di richiesta -- non toccano l'indice e
    cambiano a ogni chiamata -- e una funzione che li prende da un modulo
    globale li avrebbe condivisi fra richieste concorrenti.
    """
    if exact:
        return SearchParams(exact=True)
    if hnsw_ef is not None:
        return SearchParams(hnsw_ef=hnsw_ef)
    return None


def search(
    client: QdrantClient,
    collection: str,
    vector: list[float] | SparseVector,
    top_k: int,
    using: str = "dense",
    query_filter: Filter | None = None,
    params: SearchParams | None = None,
) -> list[QueryResponse]:
    return client.query_points(
        collection_name=collection,
        query=vector,
        using=using,
        limit=top_k,
        query_filter=query_filter,
        search_params=params,
    ).points


def search_batch(
    client: QdrantClient,
    collection: str,
    vectors: list[list[float]] | list[SparseVector],
    top_k: int,
    using: str = "dense",
    filters: list[Filter | None] | None = None,
    params: SearchParams | None = None,
) -> list[list[QueryResponse]]:
    """Batch search: sends vectors in chunks of _SEARCH_BATCH per HTTP request.

    Avoids Windows socket exhaustion (WinError 10048) when evaluating thousands
    of queries sequentially — each chunk becomes one round-trip instead of N.

    Args:
        filters: optional per-query Filter list (same length as vectors). When
            provided, each query uses its corresponding filter; None entries in
            the list mean no filter for that query.
        params: come cercare nel grafo (R-11). `None` lascia il default di
            Qdrant. Da A-02 arriva da chi chiama e non piu' da `cfg`: chi cerca
            senza dirlo sta accettando il default, e lo sta accettando **per
            iscritto**.
    """
    all_results: list[list[QueryResponse]] = []
    for start in range(0, len(vectors), _SEARCH_BATCH):
        batch = vectors[start : start + _SEARCH_BATCH]
        batch_filters = filters[start : start + _SEARCH_BATCH] if filters else [None] * len(batch)
        requests = [
            QueryRequest(query=vec, using=using, limit=top_k, with_payload=True,
                         filter=f, params=params)
            for vec, f in zip(batch, batch_filters)
        ]
        responses = client.query_batch_points(
            collection_name=collection,
            requests=requests,
        )
        all_results.extend(r.points for r in responses)
    return all_results
