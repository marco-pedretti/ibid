"""Unit tests for src/index/store.py — collection management and upsert logic.

Qdrant is not available in CI, so these tests mock the client and verify
that the correct API calls are made with the right arguments.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from qdrant_client.models import Distance, SparseVector

from src.datasets.schema import Chunk
from src.index.store import delete_collection, ensure_collection, upsert


def _make_chunk(i: int) -> Chunk:
    return Chunk(
        chunk_id=f"test:doc_{i}:{i}",
        dataset_id="test",
        doc_id=f"doc_{i}",
        doc_genre="continuous_text",
        pipeline="continuous_text",
        section_path="Introduction",
        page=0,
        bbox=None,
        content_type="text",
        text=f"This is chunk number {i}.",
        source_uri="https://example.com",
    )


def _make_dense(dim: int = 4) -> list[float]:
    return [0.1] * dim


def _make_sparse() -> SparseVector:
    return SparseVector(indices=[1, 5, 10], values=[0.8, 0.5, 0.3])


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------

class TestEnsureCollection:
    def test_creates_collection_when_absent(self):
        client = MagicMock()
        client.collection_exists.return_value = False

        ensure_collection(client, "my_col", dense_size=1024)

        client.create_collection.assert_called_once()
        call_kwargs = client.create_collection.call_args.kwargs
        assert call_kwargs["collection_name"] == "my_col"
        assert "dense" in call_kwargs["vectors_config"]
        assert "sparse" in call_kwargs["sparse_vectors_config"]
        dense_cfg = call_kwargs["vectors_config"]["dense"]
        assert dense_cfg.size == 1024
        assert dense_cfg.distance == Distance.COSINE

    def test_does_not_recreate_existing_collection(self):
        client = MagicMock()
        client.collection_exists.return_value = True

        ensure_collection(client, "existing", dense_size=1024)

        client.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# delete_collection
# ---------------------------------------------------------------------------

class TestDeleteCollection:
    def test_deletes_existing_collection(self):
        client = MagicMock()
        client.collection_exists.return_value = True

        delete_collection(client, "to_delete")

        client.delete_collection.assert_called_once_with("to_delete")

    def test_no_op_if_collection_absent(self):
        client = MagicMock()
        client.collection_exists.return_value = False

        delete_collection(client, "ghost")

        client.delete_collection.assert_not_called()


# ---------------------------------------------------------------------------
# upsert
# ---------------------------------------------------------------------------

class TestUpsert:
    def test_calls_upsert_with_correct_collection(self):
        client = MagicMock()
        chunks = [_make_chunk(0)]
        dense = [_make_dense()]
        sparse = [_make_sparse()]

        upsert(client, "my_col", chunks, dense, sparse)

        assert client.upsert.called
        assert client.upsert.call_args.kwargs["collection_name"] == "my_col"

    def test_point_has_dense_and_sparse_vectors(self):
        client = MagicMock()
        chunks = [_make_chunk(0)]
        dense = [_make_dense()]
        sparse = [_make_sparse()]

        upsert(client, "col", chunks, dense, sparse)

        points = client.upsert.call_args.kwargs["points"]
        assert len(points) == 1
        assert "dense" in points[0].vector
        assert "sparse" in points[0].vector

    def test_payload_contains_all_fields(self):
        client = MagicMock()
        chunk = _make_chunk(7)
        upsert(client, "col", [chunk], [_make_dense()], [_make_sparse()])

        payload = client.upsert.call_args.kwargs["points"][0].payload
        assert payload["chunk_id"] == chunk.chunk_id
        assert payload["dataset_id"] == "test"
        assert payload["doc_id"] == "doc_7"
        assert payload["doc_genre"] == "continuous_text"
        assert payload["pipeline"] == "continuous_text"
        assert payload["section_path"] == "Introduction"
        assert payload["content_type"] == "text"
        assert payload["text"] == chunk.text
        assert payload["page"] == 0
        assert payload["source_uri"] == "https://example.com"

    def test_id_offset_applied(self):
        client = MagicMock()
        chunks = [_make_chunk(0), _make_chunk(1)]
        dense = [_make_dense()] * 2
        sparse = [_make_sparse()] * 2

        upsert(client, "col", chunks, dense, sparse, id_offset=100)

        points = client.upsert.call_args.kwargs["points"]
        assert points[0].id == 100
        assert points[1].id == 101

    def test_large_batch_splits_into_multiple_upsert_calls(self):
        """Points exceeding _UPSERT_BATCH=256 must be sent in multiple calls."""
        client = MagicMock()
        n = 300
        chunks = [_make_chunk(i) for i in range(n)]
        dense = [_make_dense()] * n
        sparse = [_make_sparse()] * n

        upsert(client, "col", chunks, dense, sparse)

        assert client.upsert.call_count == 2  # 256 + 44

    def test_empty_input_does_not_call_upsert(self):
        client = MagicMock()
        upsert(client, "col", [], [], [])
        client.upsert.assert_not_called()
