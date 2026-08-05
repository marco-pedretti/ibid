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
    QueryResponse,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

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
    vector: list[float],
    top_k: int,
    using: str = "dense",
) -> list[QueryResponse]:
    return client.query_points(
        collection_name=collection,
        query=vector,
        using=using,
        limit=top_k,
    ).points
