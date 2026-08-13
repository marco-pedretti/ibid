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
    Filter,
    Modifier,
    PointStruct,
    QueryRequest,
    QueryResponse,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

_SEARCH_BATCH = 256

from src.datasets.schema import Chunk

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
        requests = [
            QueryRequest(query=vec, using=using, limit=top_k, with_payload=True, filter=f)
            for vec, f in zip(batch, batch_filters)
        ]
        responses = client.query_batch_points(
            collection_name=collection,
            requests=requests,
        )
        all_results.extend(r.points for r in responses)
    return all_results
