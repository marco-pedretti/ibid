"""A-01: i due casi d'uso di lettura — cosa si puo' chiedere, e a quale fonte.

Con un finto client Qdrant. Non e' un compromesso: cio' che va verificato qui e'
che l'elenco venga dal registro e non da una lista scritta a mano, e che uno
stato assente non venga confuso con uno vuoto. Nessuna delle due cose ha bisogno
di un indice acceso.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
import src.config as cfg
from src.datasets import registry
from src.index.demo import MARCATORE
from src.service import (
    DocumentInfo,
    chunk,
    dataset_of,
    datasets,
    document_chunks,
    documents,
    models,
)


@dataclass
class FakeInfo:
    points_count: int | None


class _Punto:
    def __init__(self, payload):
        self.payload = payload


class FakeClient:
    """Un Qdrant che sa solo quello che il test gli ha messo dentro."""

    def __init__(
        self,
        collections: dict[str, int | None],
        payloads: dict | None = None,
        manifesto: dict | None = None,
    ):
        self._collections = dict(collections)
        self._payloads = payloads or {}
        self._manifesto = manifesto
        self.scrolled: list[tuple[str, str]] = []
        # Il cartellino di U-08 e' una collection come le altre: un server che
        # ha un manifesto ce l'ha, uno normale no.
        if manifesto is not None:
            self._collections[MARCATORE] = 1

    def collection_exists(self, name: str) -> bool:
        return name in self._collections

    def get_collection(self, name: str) -> FakeInfo:
        return FakeInfo(points_count=self._collections[name])

    def scroll(
        self,
        collection_name,
        scroll_filter=None,
        limit=10,
        with_payload=True,
        with_vectors=False,
        **kw,
    ):
        if collection_name == MARCATORE:
            return [_Punto(self._manifesto)], None
        cond = scroll_filter.must[0]
        chunk_id = cond.match.value
        self.scrolled.append((collection_name, chunk_id))
        payload = self._payloads.get((collection_name, chunk_id))
        if payload is None:
            return [], None

        return [_Punto(payload)], None


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

    def test_senza_cartellino_nessun_dataset_e_ridotto(self):
        """Il caso normale, ed e' quello che non deve costare niente: senza la
        collection di U-08 la domanda ha comunque una risposta, ed e' «no»."""
        client = FakeClient({d: 100 for d in registry.dataset_ids()})
        assert all(not d.ridotto for d in datasets(client))

    def test_il_cartellino_marca_solo_i_dataset_che_nomina(self):
        """U-08. L'indice ridotto si chiama come quello vero: senza questo campo
        658 punti e 18.840 sono distinguibili solo da chi sa gia' quale dei due
        e' quello giusto."""
        primo, secondo = registry.dataset_ids()[0], registry.dataset_ids()[1]
        client = FakeClient(
            {primo: 658, secondo: 47110},
            manifesto={"datasets": [{"dataset_id": primo, "chunk": 658}]},
        )
        info = {d.dataset_id: d for d in datasets(client)}
        assert info[primo].ridotto
        assert not info[secondo].ridotto


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


class TestModelli:
    """A-07: il menu dei modelli viene dal backend, non dal frontend.

    Le due proprieta' che contano sono l'ordine (stabile) e la degradazione
    (una lista vuota invece di un guasto): la prima perche' un menu che si
    riordina fa saltare la selezione, la seconda perche' `/datasets` serve
    anche i dataset, che con l'LLM non c'entrano niente.
    """

    @staticmethod
    def _finto(*ids: str):
        return lambda url, timeout: {"data": [{"id": i} for i in ids]}

    def test_l_ordine_e_alfabetico_non_quello_di_arrivo(self):
        """`/v1/models` di Ollama ordina per data di download, che cambia sotto
        i piedi di chi ha appena scaricato qualcosa."""
        fetch = self._finto("qwen3.5:latest", "gemma4:12b", "gemma4:e2b")
        assert models("http://x/v1", fetch=fetch) == [
            "gemma4:12b", "gemma4:e2b", "qwen3.5:latest",
        ]

    def test_un_endpoint_spento_da_una_lista_vuota_non_un_errore(self):
        """Se sollevasse, `/datasets` fallirebbe per intero — dataset compresi.
        E' lo stesso motivo per cui `/health` non interroga Qdrant."""
        def esplode(url, timeout):
            raise RuntimeError("LLM irraggiungibile")

        assert models("http://x/v1", fetch=esplode) == []

    def test_la_lista_vuota_resta_vuota(self):
        """Non si aggiunge il modello configurato per non tornare mai vuoti:
        affermerebbe che esiste, che e' cio' che non si e' potuto verificare."""
        assert models("http://x/v1", fetch=self._finto()) == []
        assert cfg.LLM_MODEL not in models("http://x/v1", fetch=self._finto())

    def test_le_voci_senza_id_non_entrano(self):
        fetch = lambda url, timeout: {  # noqa: E731
            "data": [{"id": "a"}, {"object": "model"}, {"id": ""}, "non un dict"]
        }
        assert models("http://x/v1", fetch=fetch) == ["a"]

    def test_usa_l_indirizzo_di_deployment_quando_non_gliene_danno_uno(self):
        visti: list[str] = []

        def spia(url, timeout):
            visti.append(url)
            return {"data": []}

        models(fetch=spia)
        assert visti == [f"{cfg.LLM_BASE_URL.rstrip('/')}/models"]

    def test_l_endpoint_e_quello_openai_compatibile(self):
        """Non `/api/tags`: STACK.md impone il contratto OpenAI, cosi' la stessa
        funzione vale con vLLM o llama.cpp server al posto di Ollama."""
        visti: list[str] = []

        def spia(url, timeout):
            visti.append(url)
            return {"data": []}

        models("http://altrove:8000/v1/", fetch=spia)
        assert visti == ["http://altrove:8000/v1/models"]


class TestDocumenti:
    """A-07: sfogliare il corpus, non solo cercarlo.

    `/chunk/{id}` sa rispondere su **uno**, `/retrieve` su una query. Nessuno
    dei due sa dire cosa c'e' dentro una collection — e senza, l'esploratore
    puo' solo cercare, mai mostrare come un documento e' stato spezzato.
    """

    class FakeQdrant:
        """Un Qdrant che conosce `facet` e `scroll`, e ricorda a chi ha chiesto."""

        def __init__(self, conteggi: dict[str, int], payloads: list[dict] | None = None):
            self._conteggi = conteggi
            self._payloads = payloads or []
            self.collections_viste: list[str] = []

        def facet(self, collection_name, key, limit, exact):
            self.collections_viste.append(collection_name)
            hits = [
                SimpleNamespace(value=v, count=n) for v, n in self._conteggi.items()
            ]
            return SimpleNamespace(hits=hits)

        def scroll(self, collection_name, scroll_filter, limit, offset,
                   with_payload, with_vectors):
            self.collections_viste.append(collection_name)
            atteso = scroll_filter.must[0].match.value
            punti = [
                SimpleNamespace(payload=p)
                for p in self._payloads if p["doc_id"] == atteso
            ]
            return punti, None

    @staticmethod
    def _payload(doc_id: str, seq: str) -> dict:
        return {**payload(f"ledger:{doc_id}:{seq}"), "doc_id": doc_id}

    def test_elenca_i_documenti_col_numero_di_chunk(self):
        client = self.FakeQdrant({"NYSE_SHW_2017": 83, "AMEX_BRN_2017": 118})
        out = documents("ledger", client=client)
        assert [(d.doc_id, d.n_chunks) for d in out] == [
            ("AMEX_BRN_2017", 118), ("NYSE_SHW_2017", 83),
        ]

    def test_il_genere_non_sta_sul_documento(self):
        """Sarebbe un'aggregazione che il dato non garantisce: una collection
        `_routed` puo' mescolare pipeline dentro lo stesso documento, ed e'
        esattamente il caso che l'esploratore deve poter mostrare."""
        campi = set(DocumentInfo.__dataclass_fields__)
        assert campi == {"doc_id", "n_chunks"}

    def test_una_collection_diversa_dal_dataset(self):
        """`ledger_routed` non e' nel registro ma e' navigabile: la stessa
        ragione per cui `collections()` esiste accanto a `datasets()`."""
        client = self.FakeQdrant({"X": 1})
        documents("ledger", collection="ledger_routed", client=client)
        assert client.collections_viste == ["ledger_routed"]

    def test_i_chunk_di_un_documento_tornano_come_Chunk(self):
        client = self.FakeQdrant({}, [
            self._payload("NYSE_SHW_2017", "0001"),
            self._payload("NYSE_SHW_2017", "0000"),
            self._payload("ALTRO", "0000"),
        ])
        out = document_chunks("NYSE_SHW_2017", "ledger", client=client)
        assert [c.chunk_id for c in out] == [
            "ledger:NYSE_SHW_2017:0000", "ledger:NYSE_SHW_2017:0001",
        ]
        assert out[0].pipeline and out[0].doc_genre

    def test_un_documento_assente_da_una_lista_vuota_non_un_errore(self):
        """Come `chunk()`: un `doc_id` copiato da una citazione vecchia e' una
        domanda legittima, e va distinta da un guasto."""
        client = self.FakeQdrant({}, [self._payload("ALTRO", "0000")])
        assert document_chunks("NON_ESISTE", "ledger", client=client) == []
