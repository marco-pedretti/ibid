"""Qdrant operations: create collection, upsert, search.

Collections use named vectors:
  - "dense"  : cosine similarity, size from EMBEDDING_MODEL (1024 for multilingual-e5-large)
  - "sparse" : Qdrant sparse index, BM25 weights (Qdrant/bm25)

This layout matches R-01 hybrid RRF: query both vectors, fuse results.
"""

from __future__ import annotations

import src.config as cfg
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    Modifier,
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
        return
    ensure_idf_modifier(client, name)


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


def search_params() -> SearchParams | None:
    """Come cercare nel grafo HNSW, o se saltarlo del tutto (R-11).

    `None` quando nessuno dei due parametri e' impostato: lascia a Qdrant il suo
    default, che e' lo stato in cui e' stato misurato tutto ciò che precede
    R-11.  Un `SearchParams` vuoto non sarebbe la stessa cosa da leggere, e
    questa funzione esiste perche' la decisione stia in un posto solo invece che
    ripetuta in ogni sito di ricerca.
    """
    if cfg.SEARCH_EXACT:
        return SearchParams(exact=True)
    if cfg.HNSW_EF is not None:
        return SearchParams(hnsw_ef=cfg.HNSW_EF)
    return None


def search(
    client: QdrantClient,
    collection: str,
    vector: list[float] | SparseVector,
    top_k: int,
    using: str = "dense",
    query_filter: Filter | None = None,
) -> list[QueryResponse]:
    return client.query_points(
        collection_name=collection,
        query=vector,
        using=using,
        limit=top_k,
        query_filter=query_filter,
        search_params=search_params(),
    ).points


def search_batch(
    client: QdrantClient,
    collection: str,
    vectors: list[list[float]] | list[SparseVector],
    top_k: int,
    using: str = "dense",
    filters: list[Filter | None] | None = None,
) -> list[list[QueryResponse]]:
    """Batch search: sends vectors in chunks of _SEARCH_BATCH per HTTP request.

    Avoids Windows socket exhaustion (WinError 10048) when evaluating thousands
    of queries sequentially — each chunk becomes one round-trip instead of N.

    Args:
        filters: optional per-query Filter list (same length as vectors). When
            provided, each query uses its corresponding filter; None entries in
            the list mean no filter for that query.
    """
    all_results: list[list[QueryResponse]] = []
    for start in range(0, len(vectors), _SEARCH_BATCH):
        batch = vectors[start : start + _SEARCH_BATCH]
        batch_filters = filters[start : start + _SEARCH_BATCH] if filters else [None] * len(batch)
        params = search_params()
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
