"""Unit tests for src/index/store.py — collection management and upsert logic.

Qdrant is not available in CI, so these tests mock the client and verify
that the correct API calls are made with the right arguments.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from qdrant_client.models import Distance, Modifier, SparseVector, SparseVectorParams

from src.datasets.schema import Chunk
from src.index.store import (
    delete_collection,
    ensure_collection,
    ensure_idf_modifier,
    ensure_payload_indexes,
    list_documents,
    payloads_of_document,
    upsert,
)


def _collection_info(modifier: Modifier | None) -> MagicMock:
    info = MagicMock()
    info.config.params.sparse_vectors = {"sparse": SparseVectorParams(modifier=modifier)}
    return info


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

    def test_new_collection_gets_idf_modifier(self):
        """R-08: fastembed omits IDF from the vectors, so the index must add it."""
        client = MagicMock()
        client.collection_exists.return_value = False

        ensure_collection(client, "my_col", dense_size=1024)

        sparse = client.create_collection.call_args.kwargs["sparse_vectors_config"]["sparse"]
        assert sparse.modifier == Modifier.IDF

    def test_does_not_recreate_existing_collection(self):
        client = MagicMock()
        client.collection_exists.return_value = True
        client.get_collection.return_value = _collection_info(Modifier.IDF)

        ensure_collection(client, "existing", dense_size=1024)

        client.create_collection.assert_not_called()

    def test_repairs_existing_collection_without_modifier(self):
        client = MagicMock()
        client.collection_exists.return_value = True
        client.get_collection.return_value = _collection_info(None)

        ensure_collection(client, "existing", dense_size=1024)

        client.create_collection.assert_not_called()
        client.delete_collection.assert_not_called()
        client.update_collection.assert_called_once()


# ---------------------------------------------------------------------------
# ensure_idf_modifier (R-08)
# ---------------------------------------------------------------------------

class TestEnsureIdfModifier:
    def test_sets_modifier_when_missing(self):
        client = MagicMock()
        client.get_collection.return_value = _collection_info(None)

        assert ensure_idf_modifier(client, "col") is True

        kwargs = client.update_collection.call_args.kwargs
        assert kwargs["collection_name"] == "col"
        assert kwargs["sparse_vectors_config"]["sparse"].modifier == Modifier.IDF

    def test_idempotent_when_already_idf(self):
        client = MagicMock()
        client.get_collection.return_value = _collection_info(Modifier.IDF)

        assert ensure_idf_modifier(client, "col") is False

        client.update_collection.assert_not_called()

    def test_never_deletes_the_collection(self):
        """The dense vectors cost hours of GPU; the missing half is one config field."""
        client = MagicMock()
        client.get_collection.return_value = _collection_info(None)

        ensure_idf_modifier(client, "col")

        client.delete_collection.assert_not_called()
        client.create_collection.assert_not_called()

    def test_handles_collection_without_sparse_vectors(self):
        client = MagicMock()
        info = MagicMock()
        info.config.params.sparse_vectors = None
        client.get_collection.return_value = info

        assert ensure_idf_modifier(client, "col") is True


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


# ---------------------------------------------------------------------------
# ensure_payload_indexes (A-07)
# ---------------------------------------------------------------------------

def _info_con_schema(*campi: str) -> MagicMock:
    info = MagicMock()
    info.payload_schema = {c: MagicMock() for c in campi}
    return info


class TestEnsurePayloadIndexes:
    """Gli indici sui due campi su cui si cerca **per valore**.

    Non e' performance generica: sono i due percorsi in cui il progetto
    interroga l'indice senza un embedding in mano — la citazione cliccata
    (U-06) e l'esploratore del corpus (A-07).
    """

    def test_crea_quelli_mancanti(self):
        client = MagicMock()
        client.get_collection.return_value = _info_con_schema()

        assert ensure_payload_indexes(client, "col") == ["chunk_id", "doc_id"]

        creati = [c.kwargs["field_name"] for c in client.create_payload_index.call_args_list]
        assert creati == ["chunk_id", "doc_id"]
        assert all(c.kwargs["collection_name"] == "col"
                   for c in client.create_payload_index.call_args_list)

    def test_non_ricrea_quelli_presenti(self):
        client = MagicMock()
        client.get_collection.return_value = _info_con_schema("chunk_id", "doc_id")

        assert ensure_payload_indexes(client, "col") == []
        client.create_payload_index.assert_not_called()

    def test_completa_quelli_a_meta(self):
        """Lo stato reale di `ledger` prima della migrazione."""
        client = MagicMock()
        client.get_collection.return_value = _info_con_schema("doc_id")

        assert ensure_payload_indexes(client, "col") == ["chunk_id"]

    def test_una_collection_senza_schema_non_esplode(self):
        client = MagicMock()
        info = MagicMock()
        info.payload_schema = None
        client.get_collection.return_value = info

        assert ensure_payload_indexes(client, "col") == ["chunk_id", "doc_id"]

    def test_non_tocca_ne_punti_ne_vettori(self):
        """Il valore dell'indice payload sta tutto qui: si aggiunge a una
        collection viva, come il modificatore IDF di R-08."""
        client = MagicMock()
        client.get_collection.return_value = _info_con_schema()

        ensure_payload_indexes(client, "col")

        client.delete_collection.assert_not_called()
        client.create_collection.assert_not_called()
        client.upsert.assert_not_called()

    def test_l_ingestione_li_crea_da_sola(self):
        """Da A-07 una collection nuova nasce completa: la migrazione serve solo
        a quelle indicizzate prima, e a chi ripristina uno snapshot vecchio."""
        client = MagicMock()
        client.collection_exists.return_value = False
        client.get_collection.return_value = _info_con_schema()

        ensure_collection(client, "col", dense_size=1024)

        creati = [c.kwargs["field_name"] for c in client.create_payload_index.call_args_list]
        assert creati == ["chunk_id", "doc_id"]


# ---------------------------------------------------------------------------
# list_documents / payloads_of_document (A-07)
# ---------------------------------------------------------------------------

class TestListDocuments:
    @staticmethod
    def _client(*coppie: tuple[str, int]) -> MagicMock:
        client = MagicMock()
        risposta = MagicMock()
        risposta.hits = [MagicMock(value=v, count=n) for v, n in coppie]
        client.facet.return_value = risposta
        return client

    def test_ordine_alfabetico_non_per_conteggio(self):
        """`facet` ordina per conteggio decrescente. Una lista di documenti che
        si riordina quando cambia l'indicizzazione fa perdere il posto a chi la
        sta sfogliando."""
        client = self._client(("NYSE_ZZZ_2020", 400), ("AMEX_BRN_2017", 118))
        assert list_documents(client, "ledger") == [
            ("AMEX_BRN_2017", 118), ("NYSE_ZZZ_2020", 400),
        ]

    def test_conta_esattamente(self):
        """Un conteggio approssimato in una lista di documenti si legge come
        esatto e non lo e'."""
        client = self._client(("a", 1))
        list_documents(client, "ledger")
        assert client.facet.call_args.kwargs["exact"] is True
        assert client.facet.call_args.kwargs["key"] == "doc_id"


class TestPayloadsOfDocument:
    @staticmethod
    def _client(*chunk_ids: str) -> MagicMock:
        client = MagicMock()
        punti = [MagicMock(payload={"chunk_id": c}) for c in chunk_ids]
        client.scroll.return_value = (punti, None)
        return client

    def test_ordine_di_sequenza(self):
        """Lessicografico sul `chunk_id`: il §3 impone `seq` a quattro cifre
        zero-riempite, quindi l'ordine dei caratteri e' l'ordine dei numeri."""
        client = self._client("d:X:0010", "d:X:0002", "d:X:0001")
        assert [p["chunk_id"] for p in payloads_of_document(client, "col", "X")] == [
            "d:X:0001", "d:X:0002", "d:X:0010",
        ]

    def test_filtra_sul_documento_chiesto(self):
        client = self._client("d:X:0000")
        payloads_of_document(client, "col", "X")
        cond = client.scroll.call_args.kwargs["scroll_filter"].must[0]
        assert (cond.key, cond.match.value) == ("doc_id", "X")

    def test_un_documento_che_non_c_e_da_una_lista_vuota(self):
        client = self._client()
        assert payloads_of_document(client, "col", "assente") == []
