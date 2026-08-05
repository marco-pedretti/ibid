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
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config={"dense": VectorParams(size=dense_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )


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
) -> list[QueryResponse]:
    return client.query_points(
        collection_name=collection,
        query=vector,
        using=using,
        limit=top_k,
    ).points


def search_batch(
    client: QdrantClient,
    collection: str,
    vectors: list[list[float]] | list[SparseVector],
    top_k: int,
    using: str = "dense",
) -> list[list[QueryResponse]]:
    """Batch search: sends vectors in chunks of _SEARCH_BATCH per HTTP request.

    Avoids Windows socket exhaustion (WinError 10048) when evaluating thousands
    of queries sequentially — each chunk becomes one round-trip instead of N.
    """
    all_results: list[list[QueryResponse]] = []
    for start in range(0, len(vectors), _SEARCH_BATCH):
        batch = vectors[start : start + _SEARCH_BATCH]
        requests = [
            QueryRequest(query=vec, using=using, limit=top_k, with_payload=True)
            for vec in batch
        ]
        responses = client.query_batch_points(
            collection_name=collection,
            requests=requests,
        )
        all_results.extend(r.points for r in responses)
    return all_results
