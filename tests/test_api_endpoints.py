"""A-04: gli endpoint, e la promessa che A-01 non poteva ancora verificare.

Il criterio di A-01 diceva: *«La stessa richiesta dalla CLI e dall'API produce
lo stesso risultato, verificato da un test che le confronta.»* All'epoca
l'endpoint non esisteva, quindi quel confronto aveva un braccio solo. Qui ha
tutti e due — ed e' la classe `TestStessaRichiesta`.

Nessun indice acceso e nessun modello: i casi d'uso sono sostituiti, perche' cio'
che va verificato di un endpoint e' che **trasporti** — che legga la richiesta
giusta, chiami il caso d'uso giusto e scriva la forma giusta. Se questi test
avessero bisogno di Qdrant, direbbero che l'endpoint contiene ancora della
pipeline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts.query import build_parser, request_from_args
from src.config import RequestConfig
from src.datasets.schema import Chunk
from src.service import AnswerRequest, answer_stream
import src.config as cfg
from qdrant_client.http.exceptions import ResponseHandlingException
from src.service.catalog import DatasetInfo, DocumentInfo, ModelInfo

from src.api import main as api
from tests.test_service_answer import CLAIM, HIGH, LOW, fake_retrieve, fake_verify
from tests.test_service_stream import fake_stream

ROOT = Path(__file__).parent.parent


@pytest.fixture
def client() -> TestClient:
    return TestClient(api.app)


def risposta_finta(pezzi=("Risposta ", "[1]."), scores=None, **config_kwargs):
    """Un `Answer` vero, prodotto dalla pipeline vera, con i bordi finti."""
    eventi = list(answer_stream(
        AnswerRequest(query="domanda", config=RequestConfig.from_defaults(**config_kwargs)),
        client=object(),
        retrieve=fake_retrieve(HIGH if scores is None else scores),
        generate=fake_stream(*pezzi),
        verify=fake_verify(),
    ))
    return eventi[-1].answer, eventi


@pytest.fixture
def registra_answer(monkeypatch):
    """Sostituisce il caso d'uso e conserva la richiesta che ha ricevuto."""
    ricevute: list[AnswerRequest] = []
    risultato, _ = risposta_finta()

    def _answer(request):
        ricevute.append(request)
        return risultato

    monkeypatch.setattr(api, "answer", _answer)
    return ricevute


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_risponde_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    def test_non_interroga_qdrant(self, client, monkeypatch):
        """U-09 usa questo endpoint per `depends_on: service_healthy`. Se
        rispondesse solo con l'indice acceso, un avvio in cui Qdrant parte dopo
        si bloccherebbe a vicenda.

        Il finto client solleva: se `/health` lo toccasse, il test fallirebbe.
        """
        def esplode(*a, **kw):
            raise AssertionError("/health ha interrogato Qdrant")

        monkeypatch.setattr("src.service.catalog.get_client", esplode)
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# /datasets — U-01
# ---------------------------------------------------------------------------


def _llm_spento(url, timeout):
    raise RuntimeError(f"LLM irraggiungibile su {url}")


class TestDatasets:
    @pytest.fixture(autouse=True)
    def _collections_finte(self, monkeypatch):
        """Questi test parlano di `/datasets`, non di Qdrant.

        Senza questo stub `collections()` apre una connessione vera all'indice:
        passavano o fallivano a seconda che Qdrant fosse acceso sulla macchina
        di chi li eseguiva, ed e' cosi' che una suite verde smette di
        significare qualcosa. Scoperto il 2026-08-15, con Qdrant spento dopo un
        riavvio.
        """
        monkeypatch.setattr(api, "collections", list)

    def test_elenca_i_dataset_con_lo_stato_dell_indice(self, client, monkeypatch):
        monkeypatch.setattr(api, "datasets", lambda: [
            DatasetInfo("open_ragbench", "open_ragbench", True, 18840),
            DatasetInfo("ledger", "ledger", False, 0),
        ])
        corpo = client.get("/datasets").json()
        assert [d["dataset_id"] for d in corpo["datasets"]] == ["open_ragbench", "ledger"]
        assert corpo["datasets"][0]["n_chunks"] == 18840
        assert corpo["datasets"][1]["ready"] is False

    def test_dice_anche_cosa_accetta(self, client, monkeypatch):
        """Il frontend non deve portare una copia delle scelte valide."""
        monkeypatch.setattr(api, "datasets", list)
        corpo = client.get("/datasets").json()
        assert corpo["retrieval_modes"] == ["dense", "sparse", "hybrid"]
        assert corpo["baseline_prompts"] == ["permissive", "strict"]

    def test_elenca_i_modelli_installati(self, client, monkeypatch):
        """A-07: il menu dei modelli viene da qui, non da una lista scritta a
        mano nel frontend — che e' la quindicesima copia di Q-06.

        A-08 ha cambiato **da dove** l'elenco viene (ora e' derivato dal
        catalogo) e questo test resta a guardia di cio' che non doveva cambiare:
        `models` e' ancora una lista di nomi, nella stessa forma. Un client
        scritto contro A-04 non deve accorgersi di niente.
        """
        monkeypatch.setattr(api, "datasets", list)
        monkeypatch.setattr(
            api,
            "model_catalog",
            lambda: [ModelInfo(name="gemma4:12b"), ModelInfo(name="gemma4:e4b")],
        )
        assert client.get("/datasets").json()["models"] == ["gemma4:12b", "gemma4:e4b"]

    def test_il_catalogo_porta_finestra_e_quantizzazione(self, client, monkeypatch):
        """A-08: la coppia (modello, finestra) si legge dal server, mai dedotta
        da un nome. Il massimo **non e' uno solo** — misurato: `gemma4:latest`
        131.072, `gemma4:12b` 262.144 — quindi U-16 filtra le taglie sul
        modello scelto."""
        monkeypatch.setattr(api, "datasets", list)
        monkeypatch.setattr(
            api,
            "model_catalog",
            lambda: [
                # A chiave e non per posizione: A-08 ha guadagnato due campi in
                # mezzo poche ore dopo, e un test posizionale li avrebbe letti
                # come gli altri senza dirlo.
                ModelInfo(
                    name="gemma4:12b",
                    family="gemma4",
                    context_max=262144,
                    quantization="Q4_K_M",
                    parameter_size="11.9B",
                ),
                ModelInfo(
                    name="qwen3.5:latest",
                    family="qwen35",
                    context_max=262144,
                    context=32768,
                    quantization="Q4_K_M",
                ),
            ],
        )
        catalogo = client.get("/datasets").json()["model_catalog"]
        assert [m["context_max"] for m in catalogo] == [262144, 262144]
        assert [m["family"] for m in catalogo] == ["gemma4", "qwen35"]
        assert catalogo[0]["quantization"] == "Q4_K_M"
        # `context_max` e `context` sono due cose: cosa l'architettura regge, e
        # cosa girera' davvero. Confonderle offrirebbe 262.144 a un modello
        # fissato a 32.768.
        assert [m["context"] for m in catalogo] == [None, 32768]

    def test_un_motore_muto_da_un_catalogo_di_soli_nomi(self, client, monkeypatch):
        """Su un motore che non e' Ollama i dettagli non arrivano: `context_max`
        resta `None`, e chi riceve il catalogo non offre la scelta della
        finestra invece di offrirne una inventata."""
        monkeypatch.setattr(api, "datasets", list)
        monkeypatch.setattr(api, "model_catalog", lambda: [ModelInfo(name="mistral")])
        catalogo = client.get("/datasets").json()["model_catalog"]
        assert catalogo == [
            {
                "name": "mistral",
                "family": "",
                "context_max": None,
                "context": None,
                "parent": "",
                "quantization": "",
                "parameter_size": "",
            }
        ]

    def test_con_l_indice_spento_risponde_503_e_dice_dove(self, client, monkeypatch):
        """Qdrant spento e' un servizio che manca, non un bug del servizio.

        Senza il gestore, la connessione rifiutata risale fino a uvicorn e
        diventa un 500 con un traceback: un codice che accusa il backend e un
        corpo che chi guarda la demo non puo' usare. 503 dice «riprova quando
        c'e'», e il corpo porta l'indirizzo su cui si stava chiamando -- l'unica
        cosa che serve per rimediare.
        """
        def spento():
            raise ResponseHandlingException(OSError("[WinError 10061] rifiuto"))

        monkeypatch.setattr(api, "datasets", spento)
        r = client.get("/datasets")
        assert r.status_code == 503
        assert cfg.QDRANT_URL in r.json()["detail"]

    def test_health_resta_verde_con_l_indice_spento(self, client, monkeypatch):
        """`/health` non interroga l'indice di proposito: e' cio' che permette a
        `depends_on: service_healthy` (U-09) di funzionare quando Qdrant parte
        dopo il backend. Se un giorno lo interrogasse, i due si aspetterebbero a
        vicenda."""
        def spento():
            raise ResponseHandlingException(OSError("[WinError 10061] rifiuto"))

        monkeypatch.setattr(api, "datasets", spento)
        assert client.get("/health").status_code == 200

    def test_con_l_llm_spento_i_dataset_arrivano_lo_stesso(self, client, monkeypatch):
        """I dataset non dipendono dall'LLM. Se la lista modelli facesse
        fallire tutta la risposta, sarebbe lo stesso difetto per cui `/health`
        non interroga Qdrant."""
        monkeypatch.setattr(api, "datasets", lambda: [
            DatasetInfo("open_ragbench", "open_ragbench", True, 18840),
        ])
        monkeypatch.setattr("src.generation.chat._get_json", _llm_spento)
        risposta = client.get("/datasets")
        assert risposta.status_code == 200
        corpo = risposta.json()
        assert corpo["models"] == []
        assert corpo["datasets"][0]["n_chunks"] == 18840


# ---------------------------------------------------------------------------
# /chunk/{chunk_id} — U-06
# ---------------------------------------------------------------------------


def un_chunk(chunk_id="ledger:NASDAQ_AAPL_2022:0031") -> Chunk:
    return Chunk(
        chunk_id=chunk_id, dataset_id="ledger", doc_id="NASDAQ_AAPL_2022",
        doc_genre="table_heavy", pipeline="pipeline_table_heavy",
        section_path="Note 1", page=7, bbox=None, content_type="table",
        text="contenuto", source_uri="https://example.org/doc",
    )


class TestChunk:
    def test_restituisce_la_fonte(self, client, monkeypatch):
        monkeypatch.setattr(api, "chunk", lambda cid, collection=None: un_chunk(cid))
        r = client.get("/chunk/ledger:NASDAQ_AAPL_2022:0031")
        assert r.status_code == 200
        assert r.json()["chunk_id"] == "ledger:NASDAQ_AAPL_2022:0031"
        assert r.json()["page"] == 7

    def test_i_due_punti_nel_percorso_non_lo_spezzano(self, client, monkeypatch):
        """Un `chunk_id` **contiene** i due punti per contratto (§3): senza
        `:path` il routing lo taglierebbe al primo."""
        visti: list[str] = []
        monkeypatch.setattr(api, "chunk", lambda cid, collection=None: visti.append(cid) or un_chunk(cid))
        client.get("/chunk/ledger:NASDAQ_AAPL_2022:0031")
        assert visti == ["ledger:NASDAQ_AAPL_2022:0031"]

    def test_un_id_che_non_c_e_e_404_non_500(self, client, monkeypatch):
        """Un link vecchio dopo una re-ingestione e' una domanda legittima con
        una risposta legittima, e va distinta da un guasto."""
        monkeypatch.setattr(api, "chunk", lambda cid, collection=None: None)
        assert client.get("/chunk/ledger:SPARITO:0001").status_code == 404

    def test_un_id_malformato_e_400(self, client):
        """Il dataset e' dentro l'id: se il prefisso non e' un dataset noto, la
        richiesta e' sbagliata — e dirlo costa zero interrogazioni all'indice."""
        assert client.get("/chunk/inventato:doc:1").status_code == 400

    def test_la_collection_si_puo_forzare(self, client, monkeypatch):
        visti: list = []
        monkeypatch.setattr(
            api, "chunk",
            lambda cid, collection=None: visti.append(collection) or un_chunk(cid),
        )
        client.get("/chunk/ledger:X:1?collection=ledger_routed")
        assert visti == ["ledger_routed"]


# ---------------------------------------------------------------------------
# /query
# ---------------------------------------------------------------------------


class TestQuery:
    def test_una_domanda_e_basta(self, client, registra_answer):
        """Un client minimo manda `{"query": "..."}`. Se servisse altro, ogni
        client dovrebbe conoscere i default del deployment."""
        r = client.post("/query", json={"query": "domanda"})
        assert r.status_code == 200
        assert registra_answer[0].config == RequestConfig.from_defaults()

    def test_la_risposta_ha_la_forma_del_contratto(self, client, registra_answer):
        corpo = client.post("/query", json={"query": "domanda"}).json()
        assert set(corpo) >= {
            "text", "raw_text", "repaired", "abstained", "abstention", "truncated",
            "chunks", "cited", "citations", "uncited_claims", "verified", "gate",
            "timings", "config",
        }

    def test_i_parametri_arrivano_alla_richiesta(self, client, registra_answer):
        client.post("/query", json={
            "query": "domanda", "dataset_id": "ledger", "top_k": 3,
            "retrieval_mode": "hybrid", "rerank": True, "rag": False,
            "baseline_prompt": "permissive",
        })
        req = registra_answer[0]
        assert req.dataset_id == "ledger"
        assert (req.config.top_k, req.config.retrieval_mode) == (3, "hybrid")
        assert req.config.rerank and not req.config.rag
        assert req.config.baseline_prompt == "permissive"

    def test_una_domanda_vuota_e_rifiutata_dallo_schema(self, client):
        assert client.post("/query", json={"query": ""}).status_code == 422

    @pytest.mark.parametrize("corpo", [
        {"query": "q", "baseline_prompt": "severo"},
        {"query": "q", "retrieval_mode": "magica"},
    ])
    def test_un_valore_che_non_esiste_e_422_non_500(self, client, corpo):
        """Un client che manda un valore inventato ha sbagliato lui; un 500 gli
        direbbe che abbiamo sbagliato noi, e lo manderebbe a cercare nel posto
        sbagliato."""
        r = client.post("/query", json=corpo)
        assert r.status_code == 422
        campo = next(k for k in corpo if k != "query")
        assert campo in json.dumps(r.json())

    def test_un_parametro_che_non_esiste_non_finisce_nella_configurazione(self, client, registra_answer):
        """Pydantic lo ignora; cio' che conta e' che non arrivi al servizio
        travestito da qualcos'altro."""
        client.post("/query", json={"query": "q", "embedding_model": "altro"})
        assert not hasattr(registra_answer[0].config, "embedding_model")


# ---------------------------------------------------------------------------
# /query/stream — §3.5
# ---------------------------------------------------------------------------


def leggi_sse(testo: str) -> list[tuple[str, dict]]:
    """Il formato letto come lo leggerebbe un client."""
    fuori = []
    for blocco in testo.split("\n\n"):
        if not blocco.strip():
            continue
        nome = re.search(r"^event: (.+)$", blocco, re.M).group(1)
        dati = re.search(r"^data: (.+)$", blocco, re.M).group(1)
        fuori.append((nome, json.loads(dati)))
    return fuori


@pytest.fixture
def stream_finto(monkeypatch):
    _, eventi = risposta_finta(pezzi=(f"{CLAIM} ", "[1]."))
    monkeypatch.setattr(api, "answer_stream", lambda request: iter(eventi))
    return eventi


class TestQueryStream:
    def test_il_tipo_di_contenuto_e_quello_di_sse(self, client, stream_finto):
        r = client.post("/query/stream", json={"query": "domanda"})
        assert r.headers["content-type"].startswith("text/event-stream")

    def test_gli_eventi_arrivano_nell_ordine_del_contratto(self, client, stream_finto):
        eventi = leggi_sse(client.post("/query/stream", json={"query": "q"}).text)
        nomi = [n for n, _ in eventi]
        assert nomi[0] == "chunks"
        assert nomi[-1] == "done"
        assert nomi.index("answer") < nomi.index("citations")

    def test_nessun_buffering_dai_proxy(self, client, stream_finto):
        """Un proxy che bufferizza annulla lo streaming senza rompere niente:
        il client riceve tutto insieme alla fine e non ha modo di accorgersene."""
        r = client.post("/query/stream", json={"query": "q"})
        assert r.headers.get("x-accel-buffering") == "no"
        assert "no-cache" in r.headers.get("cache-control", "")

    def test_un_guasto_diventa_un_evento_non_un_500(self, client, monkeypatch):
        """Quando il primo byte e' partito, lo stato e' gia' 200 e non e' piu'
        modificabile. Un errore a meta' risposta puo' solo essere un evento."""
        def esplode(request):
            yield from ()
            raise RuntimeError("Qdrant irraggiungibile")

        monkeypatch.setattr(api, "answer_stream", esplode)
        r = client.post("/query/stream", json={"query": "q"})
        assert r.status_code == 200
        eventi = leggi_sse(r.text)
        assert eventi[-1][0] == "error"
        assert "Qdrant irraggiungibile" in eventi[-1][1]["message"]

    def test_un_guasto_a_meta_non_butta_via_quello_che_e_arrivato(self, client, monkeypatch):
        """`chunks` era gia' partito: la UI puo' dire «le fonti ci sono, la
        risposta no» invece di mostrare una pagina vuota."""
        _, eventi = risposta_finta()

        def a_meta(request):
            yield eventi[0]
            raise RuntimeError("il modello e' caduto")

        monkeypatch.setattr(api, "answer_stream", a_meta)
        letti = leggi_sse(client.post("/query/stream", json={"query": "q"}).text)
        assert [n for n, _ in letti] == ["chunks", "error"]


# ---------------------------------------------------------------------------
# Il criterio di A-01, finalmente con due bracci
# ---------------------------------------------------------------------------


class TestStessaRichiesta:
    """«La stessa richiesta dalla CLI e dall'API produce lo stesso risultato.»

    Confrontare le due *risposte* non basterebbe: coinciderebbero anche se le
    due strade costruissero richieste diverse che per caso danno lo stesso
    esito. Cio' che va confrontato e' l'oggetto che arriva al caso d'uso — e
    infatti e' lo stesso tipo, perche' la pipeline e' una sola.
    """

    def da_cli(self, argv: list[str]) -> AnswerRequest:
        return request_from_args(build_parser().parse_args(argv))

    def da_api(self, client, registra_answer, corpo: dict) -> AnswerRequest:
        client.post("/query", json=corpo)
        return registra_answer[0]

    def test_la_richiesta_minima_coincide(self, client, registra_answer):
        assert self.da_cli(["domanda"]) == self.da_api(client, registra_answer, {"query": "domanda"})

    def test_coincide_con_i_parametri_di_retrieval(self, client, registra_answer):
        cli = self.da_cli([
            "--dataset", "ledger", "--top-k", "3", "--retrieval-mode", "hybrid",
            "--rerank", "--query-rewrite", "--filter-content-type", "auto", "domanda",
        ])
        api_ = self.da_api(client, registra_answer, {
            "query": "domanda", "dataset_id": "ledger", "top_k": 3,
            "retrieval_mode": "hybrid", "rerank": True, "query_rewrite": True,
            "filter_content_type": "auto",
        })
        assert cli == api_

    def test_coincide_sul_braccio_nudo(self, client, registra_answer):
        cli = self.da_cli(["--no-rag", "--baseline-prompt", "permissive", "domanda"])
        api_ = self.da_api(client, registra_answer, {
            "query": "domanda", "rag": False, "baseline_prompt": "permissive",
        })
        assert cli == api_

    def test_coincide_sui_parametri_di_ricerca(self, client, registra_answer):
        cli = self.da_cli(["--search-exact", "--no-verify", "--collection", "ledger_routed",
                           "--dataset", "ledger", "domanda"])
        api_ = self.da_api(client, registra_answer, {
            "query": "domanda", "dataset_id": "ledger", "collection": "ledger_routed",
            "search_exact": True, "verify": False,
        })
        assert cli == api_

    def test_le_due_strade_chiamano_la_stessa_funzione(self):
        """La condizione perche' «stesso risultato» sia una proprieta' e non una
        coincidenza: se fossero due pipeline, questi test verificherebbero solo
        che oggi coincidono."""
        cli = (ROOT / "scripts" / "query.py").read_text(encoding="utf-8")
        api_src = (ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        for sorgente in (cli, api_src):
            # L'import puo' essere su una riga o su molte: cio' che conta e' che
            # `answer` venga da `src.service` e non sia ricostruito sul posto.
            blocco = re.search(r"from src\.service import \(?([^)\n]|\n(?!\n))*", sorgente)
            assert blocco and re.search(r"\banswer\b", blocco.group(0))


# ---------------------------------------------------------------------------
# /documents e /document/{doc_id}/chunks — A-07
# ---------------------------------------------------------------------------


class TestDocumenti:
    def test_elenca_i_documenti_della_collection(self, client, monkeypatch):
        monkeypatch.setattr(api, "documents", lambda ds, collection=None: [
            DocumentInfo("AMEX_BRN_2017", 118), DocumentInfo("NYSE_SHW_2017", 83),
        ])
        corpo = client.get("/documents", params={"dataset_id": "ledger"}).json()
        assert corpo["collection"] == "ledger"
        assert [d["doc_id"] for d in corpo["documents"]] == ["AMEX_BRN_2017", "NYSE_SHW_2017"]
        assert corpo["documents"][1]["n_chunks"] == 83

    def test_la_collection_torna_indietro_quando_e_forzata(self, client, monkeypatch):
        """Senza, due elenchi diversi della stessa domanda non si distinguono."""
        visti: list[str | None] = []
        monkeypatch.setattr(
            api, "documents",
            lambda ds, collection=None: visti.append(collection) or [],
        )
        corpo = client.get(
            "/documents", params={"dataset_id": "ledger", "collection": "ledger_routed"}
        ).json()
        assert visti == ["ledger_routed"]
        assert corpo["collection"] == "ledger_routed"

    def test_un_dataset_sconosciuto_e_404(self, client):
        assert client.get("/documents", params={"dataset_id": "inventato"}).status_code == 404

    def test_i_chunk_di_un_documento_arrivano_in_ordine(self, client, monkeypatch):
        """Mostrare **come** un documento e' stato spezzato ha senso solo nella
        sequenza in cui e' stato spezzato."""
        monkeypatch.setattr(api, "document_chunks", lambda doc, ds, collection=None: [
            un_chunk("ledger:NYSE_SHW_2017:0000"),
            un_chunk("ledger:NYSE_SHW_2017:0001"),
        ])
        corpo = client.get(
            "/document/NYSE_SHW_2017/chunks", params={"dataset_id": "ledger"}
        ).json()
        assert corpo["doc_id"] == "NYSE_SHW_2017"
        assert [c["chunk_id"].rsplit(":", 1)[1] for c in corpo["chunks"]] == ["0000", "0001"]

    def test_ogni_chunk_dice_la_sua_pipeline(self, client, monkeypatch):
        """E' cio' che rende visibile il routing (U-05) a chi sfoglia invece di
        interrogare."""
        monkeypatch.setattr(
            api, "document_chunks",
            lambda doc, ds, collection=None: [un_chunk()],
        )
        chunk_view = client.get(
            "/document/NASDAQ_AAPL_2022/chunks", params={"dataset_id": "ledger"}
        ).json()["chunks"][0]
        assert chunk_view["pipeline"] and chunk_view["doc_genre"]

    def test_qui_non_c_e_stato_nessun_recupero_e_si_vede(self, client, monkeypatch):
        """`marker` e `score` a zero: un punteggio inventato farebbe leggere una
        classifica dove c'e' solo una lettura."""
        monkeypatch.setattr(
            api, "document_chunks",
            lambda doc, ds, collection=None: [un_chunk()],
        )
        c = client.get(
            "/document/X/chunks", params={"dataset_id": "ledger"}
        ).json()["chunks"][0]
        assert (c["marker"], c["score"]) == (0, 0.0)

    def test_un_documento_che_non_c_e_e_404_non_una_lista_vuota(self, client, monkeypatch):
        """Come `/chunk/{id}`: un `doc_id` copiato da una citazione vecchia e'
        una domanda legittima, e va distinta da un guasto."""
        monkeypatch.setattr(api, "document_chunks", lambda doc, ds, collection=None: [])
        r = client.get("/document/NON_ESISTE/chunks", params={"dataset_id": "ledger"})
        assert r.status_code == 404


class TestContrattoAdditivo:
    """Il criterio di A-07: un client scritto contro A-04 continua a funzionare.

    Cambiare la forma di cio' che qualcosa ha gia' prodotto e' la regola che ha
    reso caro il §3.2. Qui si aggiunge, e questo test dice che si e' solo
    aggiunto.
    """

    def test_la_richiesta_minima_basta_ancora(self, client, registra_answer):
        """`{"query": "..."}` e niente altro: nessuno dei campi nuovi e'
        obbligatorio."""
        assert client.post("/query", json={"query": "domanda"}).status_code == 200

    def test_gli_endpoint_di_a04_ci_sono_tutti(self, client):
        percorsi = {r.path for r in api.app.routes}
        assert {"/health", "/datasets", "/chunk/{chunk_id:path}",
                "/query", "/query/stream", "/config", "/retrieve"} <= percorsi

    def test_i_campi_di_a04_non_sono_spariti_dalla_risposta(self, client, registra_answer):
        corpo = client.post("/query", json={"query": "domanda"}).json()
        assert {"text", "raw_text", "repaired", "abstained", "abstention", "truncated",
                "chunks", "cited", "citations", "uncited_claims", "verified", "gate",
                "timings", "config"} <= set(corpo)


class TestNienteLogicaNegliEndpoint:
    """Il criterio di A-01 applicato a questo file.

    Un endpoint che importasse il retrieval o la generazione avrebbe ricominciato
    a decidere, e il confronto con la CLI tornerebbe a essere fra due cose
    diverse.
    """

    VIETATI = (
        "src.index",
        "src.retrieval",
        "src.generation",
        "src.eval",
    )

    def test_l_api_non_importa_la_pipeline(self):
        sorgente = (ROOT / "src" / "api" / "main.py").read_text(encoding="utf-8")
        trovati = [m for m in self.VIETATI if re.search(rf"^from {re.escape(m)}", sorgente, re.M)]
        assert trovati == [], f"src/api/main.py importa la pipeline: {trovati}"

    def test_l_api_non_espone_la_topologia_della_rete(self, client):
        """`/config` dice i default di richiesta. Un endpoint che rivelasse
        `QDRANT_URL` racconterebbe la rete a chiunque."""
        corpo = client.get("/config").json()
        assert "top_k" in corpo
        assert not {"qdrant_url", "llm_base_url", "embedding_model"} & set(corpo)


# ---------------------------------------------------------------------------
# Astensione, vista dal filo
# ---------------------------------------------------------------------------


class TestAstensioneSulFilo:
    def test_il_gate_che_si_astiene_arriva_come_risposta_valida(self, client, monkeypatch):
        """Non e' un errore: e' la garanzia di C-04 che ha funzionato. Un 4xx la
        farebbe sembrare un fallimento della richiesta."""
        risultato, _ = risposta_finta(scores=LOW)
        monkeypatch.setattr(api, "answer", lambda request: risultato)
        corpo = client.post("/query", json={"query": "q"}).json()
        assert corpo["abstained"] is True
        assert corpo["abstention"] == "retrieval"
        assert len(corpo["chunks"]) == 5  # U-02: le fonti ci sono lo stesso


# ---------------------------------------------------------------------------
# /retrieve — l'endpoint che A-06 ha scoperto mancare
# ---------------------------------------------------------------------------


class TestRetrieve:
    """Cercare senza rispondere.

    Il ROADMAP prevedeva questo esito: la dashboard è il consumatore più
    esigente che esista già, e *«se non le basta, si scopre ora invece che a
    React scritto»*. Non le bastava — dall'API mancava la metà che non genera.
    """

    @pytest.fixture
    def registra_retrieve(self, monkeypatch):
        ricevute: list = []
        _, eventi = risposta_finta()
        chunks = eventi[0].chunks

        def _retrieve(request):
            ricevute.append(request)
            return [chunks for _ in request.queries]

        monkeypatch.setattr(api, "retrieve_chunks", _retrieve)
        return ricevute

    def test_non_chiama_mai_il_modello(self, client, registra_retrieve, monkeypatch):
        """È tutto il senso dell'endpoint: prima esisteva solo `/query`, cioè
        pagare una generazione per vedere dei chunk."""
        def esplode(*a, **kw):
            raise AssertionError("/retrieve ha generato")

        monkeypatch.setattr(api, "answer", esplode)
        monkeypatch.setattr(api, "answer_stream", esplode)
        r = client.post("/retrieve", json={"queries": ["domanda"]})
        assert r.status_code == 200
        assert len(r.json()["results"]) == 1

    def test_molte_query_in_una_chiamata(self, client, registra_retrieve):
        """L'embedding è batch per natura: 200 query in un viaggio sono una
        passata di GPU, 200 viaggi sono 200 passate."""
        r = client.post("/retrieve", json={"queries": [f"q{i}" for i in range(50)]})
        assert len(r.json()["results"]) == 50
        assert len(registra_retrieve[0].queries) == 50

    def test_i_risultati_seguono_l_ordine_delle_query(self, client, monkeypatch):
        """Un client che ne manda 200 deve poterle riallineare senza fidarsi di
        un id che non abbiamo inventato.

        Una query che non trova niente produce una lista **vuota al suo posto**,
        non una riga in meno: saltarla farebbe scivolare tutto ciò che segue.
        """
        _, eventi = risposta_finta()
        uno = eventi[0].chunks[:1]

        def _retrieve(request):
            return [[] if q.startswith("vuota") else uno for q in request.queries]

        monkeypatch.setattr(api, "retrieve_chunks", _retrieve)
        r = client.post("/retrieve", json={"queries": ["a", "vuota1", "b"]})
        assert [len(x) for x in r.json()["results"]] == [1, 0, 1]

    def test_una_lista_vuota_e_rifiutata(self, client):
        """Zero query non è una domanda: è un errore di chi chiama."""
        assert client.post("/retrieve", json={"queries": []}).status_code == 422

    def test_i_parametri_di_recupero_arrivano(self, client, registra_retrieve):
        client.post("/retrieve", json={
            "queries": ["q"], "dataset_id": "ledger", "collection": "ledger_routed",
            "top_k": 20, "retrieval_mode": "hybrid", "rerank": True,
        })
        req = registra_retrieve[0]
        assert req.collection == "ledger_routed"
        assert (req.config.top_k, req.config.retrieval_mode, req.config.rerank) == (20, "hybrid", True)

    def test_i_parametri_di_generazione_non_esistono(self, client):
        """Qui nessun modello viene chiamato: chiederli renderebbe esprimibile
        una richiesta che il servizio ignorerebbe."""
        campi = set(api.RetrieveRequestBody.model_fields)
        assert not {"model", "temperature", "max_new_tokens", "rag", "verify"} & campi

    def test_la_configurazione_che_ha_girato_torna_indietro(self, client, registra_retrieve):
        corpo = client.post("/retrieve", json={"queries": ["q"], "top_k": 3}).json()
        assert corpo["config"]["top_k"] == 3
