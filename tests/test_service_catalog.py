"""A-01: i due casi d'uso di lettura — cosa si puo' chiedere, e a quale fonte.

Con un finto client Qdrant. Non e' un compromesso: cio' che va verificato qui e'
che l'elenco venga dal registro e non da una lista scritta a mano, e che uno
stato assente non venga confuso con uno vuoto. Nessuna delle due cose ha bisogno
di un indice acceso.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from src.datasets import registry
from src.service import chunk, dataset_of, datasets


@dataclass
class FakeInfo:
    points_count: int | None


class FakeClient:
    """Un Qdrant che sa solo quello che il test gli ha messo dentro."""

    def __init__(self, collections: dict[str, int | None], payloads: dict | None = None):
        self._collections = collections
        self._payloads = payloads or {}
        self.scrolled: list[tuple[str, str]] = []

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def get_collection(self, name: str) -> FakeInfo:
        return FakeInfo(points_count=self._collections[name])

    def scroll(self, collection_name, scroll_filter, limit, with_payload, with_vectors):
        cond = scroll_filter.must[0]
        chunk_id = cond.match.value
        self.scrolled.append((collection_name, chunk_id))
        payload = self._payloads.get((collection_name, chunk_id))
        if payload is None:
            return [], None

        class _Point:
            def __init__(self, p):
                self.payload = p

        return [_Point(payload)], None


def payload(chunk_id: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "dataset_id": chunk_id.split(":", 1)[0],
        "doc_id": "doc",
        "doc_genre": "table_heavy",
        "pipeline": "pipeline_table_heavy",
        "section_path": "Note 1",
        "content_type": "table",
        "text": "contenuto",
        "page": 7,
        "source_uri": "https://example.org/doc",
    }


# --- datasets() ------------------------------------------------------------


class TestDatasets:
    def test_elenca_esattamente_il_registro(self):
        """Un dataset in piu' nel registro e' un dataset in piu' qui, senza toccare
        niente: e' l'unica forma in cui Q-06 continua a valere fino all'API."""
        client = FakeClient({d: 100 for d in registry.dataset_ids()})
        assert [d.dataset_id for d in datasets(client)] == registry.dataset_ids()

    def test_collection_assente_non_e_pronta(self):
        client = FakeClient({})
        assert all(not d.ready and d.n_chunks == 0 for d in datasets(client))

    def test_collection_vuota_e_diversa_da_assente(self):
        """Fra `ensure_collection` e la fine dell'ingestione questo stato esiste
        davvero, e chi lo confonde con l'assenza mostra un dataset che risponde
        sempre niente."""
        primo = registry.dataset_ids()[0]
        client = FakeClient({primo: 0})
        info = {d.dataset_id: d for d in datasets(client)}
        assert info[primo].ready and info[primo].n_chunks == 0

    def test_points_count_nullo_non_diventa_none(self):
        primo = registry.dataset_ids()[0]
        info = {d.dataset_id: d for d in datasets(FakeClient({primo: None}))}
        assert info[primo].n_chunks == 0


# --- dataset_of() / chunk() ------------------------------------------------


class TestDatasetOf:
    @pytest.mark.parametrize("chunk_id,atteso", [
        ("open_ragbench:2412.20245v4:0007", "open_ragbench"),
        ("ledger:NASDAQ_AAPL_2022:0031", "ledger"),
    ])
    def test_il_dataset_e_gia_dentro_l_id(self, chunk_id, atteso):
        assert dataset_of(chunk_id) == atteso

    def test_lo_schema_del_registro_e_quello_del_paragrafo_3(self):
        """Se un `chunk_id` smettesse di iniziare col dataset, questa funzione
        mentirebbe in silenzio. Il test lega le due convenzioni."""
        for dataset_id in registry.dataset_ids():
            assert dataset_of(f"{dataset_id}:doc:0001") == dataset_id


class TestChunk:
    def test_la_collection_si_deduce_dall_id(self):
        cid = "ledger:NASDAQ_AAPL_2022:0031"
        client = FakeClient({}, {("ledger", cid): payload(cid)})
        result = chunk(cid, client=client)
        assert result is not None
        assert result.chunk_id == cid
        assert client.scrolled == [("ledger", cid)]

    def test_collection_esplicita_vince_sull_id(self):
        cid = "ledger:NASDAQ_AAPL_2022:0031"
        client = FakeClient({}, {("ledger_routed", cid): payload(cid)})
        assert chunk(cid, collection="ledger_routed", client=client) is not None
        assert client.scrolled == [("ledger_routed", cid)]

    def test_id_inesistente_restituisce_none(self):
        """Un link vecchio dopo una re-ingestione e' una domanda legittima con
        una risposta legittima, non un guasto."""
        client = FakeClient({}, {})
        assert chunk("ledger:SPARITO:0001", client=client) is None

    def test_il_payload_torna_a_essere_un_chunk_completo(self):
        cid = "ledger:NASDAQ_AAPL_2022:0031"
        client = FakeClient({}, {("ledger", cid): payload(cid)})
        result = chunk(cid, client=client)
        assert result.doc_genre == "table_heavy"
        assert result.pipeline == "pipeline_table_heavy"
        assert result.page == 7
        # I-06 e' rinviato: nessun dataset attuale porta coordinate. Dichiarato
        # assente, non simulato (§3.5).
        assert result.bbox is None
