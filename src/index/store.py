"""Qdrant operations: create collection, upsert, search."""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, QueryResponse, VectorParams

from src.datasets.schema import Chunk

_UPSERT_BATCH = 256


def get_client(url: str) -> QdrantClient:
    return QdrantClient(url=url, timeout=60)


def ensure_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def upsert(
    client: QdrantClient,
    collection: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> None:
    points = [
        PointStruct(
            id=i,
            vector=v,
            payload={
                "chunk_id": c.chunk_id,
                "dataset_id": c.dataset_id,
                "doc_id": c.doc_id,
                "doc_genre": c.doc_genre,
                "content_type": c.content_type,
                "text": c.text,
                "page": c.page,
                "source_uri": c.source_uri,
            },
        )
        for i, (c, v) in enumerate(zip(chunks, vectors))
    ]
    for start in range(0, len(points), _UPSERT_BATCH):
        client.upsert(collection_name=collection, points=points[start : start + _UPSERT_BATCH])


def search(
    client: QdrantClient,
    collection: str,
    vector: list[float],
    top_k: int,
) -> list[QueryResponse]:
    return client.query_points(
        collection_name=collection,
        query=vector,
        limit=top_k,
    ).points
