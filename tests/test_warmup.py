"""D-21: il riscaldamento all'avvio non blocca, non cade, e scalda il giusto.

Nessuno di questi test carica un modello vero: caricherebbe ~2,5 GB per provare
tre proprieta' che non dipendono da cosa c'e' dentro il file. Quello che si
prova qui e' **la forma** del riscaldamento, cioe' i tre modi in cui una
versione plausibile di questo codice sarebbe sbagliata.
"""

import threading
import time

import pytest
import src.config as cfg
from src.service import warmup


class TestCosaScalda:
    def test_coi_default_scalda_embedder_e_verificatore(self):
        """Non una lista sua: la stessa configurazione che servira' la prima
        richiesta. Coi default (`dense`, `rerank=False`, `verify=True`) sono due."""
        nomi = [n for n, _ in warmup.da_scaldare()]
        assert nomi == [cfg.EMBEDDING_MODEL, cfg.ENTAILMENT_MODEL]

    def test_il_reranker_spento_non_si_carica(self):
        """~1 GB di VRAM che nessuna richiesta toccherebbe."""
        nomi = [n for n, _ in warmup.da_scaldare(cfg.RequestConfig.from_defaults(rerank=False))]
        assert cfg.RERANKER_MODEL not in nomi

    def test_il_reranker_acceso_si_carica(self):
        config = cfg.RequestConfig.from_defaults(rerank=True)
        assert config.reranker_model in [n for n, _ in warmup.da_scaldare(config)]

    def test_in_sparso_scalda_lo_sparso_e_non_il_denso(self):
        nomi = [
            n for n, _ in warmup.da_scaldare(cfg.RequestConfig.from_defaults(retrieval_mode="sparse"))
        ]
        assert cfg.SPARSE_EMBEDDING_MODEL in nomi
        assert cfg.EMBEDDING_MODEL not in nomi

    def test_in_ibrido_scalda_tutti_e_due(self):
        nomi = [
            n for n, _ in warmup.da_scaldare(cfg.RequestConfig.from_defaults(retrieval_mode="hybrid"))
        ]
        assert nomi[:2] == [cfg.EMBEDDING_MODEL, cfg.SPARSE_EMBEDDING_MODEL]

    def test_l_ordine_e_quello_d_uso(self):
        """L'embedder serve alla prima ricerca, il verificatore alla prima
        citazione: scaldarli al contrario avrebbe pronto il secondo mentre si
        aspetta il primo."""
        nomi = [n for n, _ in warmup.da_scaldare()]
        assert nomi.index(cfg.EMBEDDING_MODEL) < nomi.index(cfg.ENTAILMENT_MODEL)


class TestNonCade:
    def test_un_modello_che_fallisce_non_ferma_gli_altri(self):
        caricati = []

        def rotto():
            raise RuntimeError("niente rete")

        fatti = warmup.scalda(
            [("rotto", rotto), ("buono", lambda: caricati.append("buono"))]
        )
        assert caricati == ["buono"]
        assert [n for n, _ in fatti] == ["buono"]

    def test_misura_quanto_ci_mette(self):
        fatti = warmup.scalda([("lento", lambda: time.sleep(0.02))])
        assert fatti[0][1] >= 0.02


class TestNonBlocca:
    def test_torna_prima_che_il_caricamento_finisca(self, monkeypatch):
        """Il vincolo di D-21 detto in un test: uvicorn deve poter accettare
        richieste mentre i pesi si caricano."""
        monkeypatch.setattr(warmup, "ATTIVO", True)
        partito = threading.Event()
        molla = threading.Event()

        def lento():
            partito.set()
            molla.wait(5)

        t0 = time.perf_counter()
        t = warmup.in_sottofondo([("lento", lento)])
        ritorno = time.perf_counter() - t0

        assert partito.wait(5), "il thread non e' partito"
        assert ritorno < 1.0, f"in_sottofondo ha aspettato {ritorno:.2f} s"
        assert t is not None and t.daemon
        molla.set()
        t.join(5)

    def test_le_righe_escono_dove_escono_quelle_di_uvicorn(self):
        """Senza questo il riscaldamento e' muto proprio dove gira: uvicorn
        lascia la radice senza gestori, e un INFO nostro finisce nel nulla."""
        import logging

        # **Sul genitore, non su `uvicorn.error`**: e' li' che uvicorn mette il
        # gestore, e cercarlo sul figlio e' il difetto che questo test copre.
        padre = logging.getLogger("uvicorn")
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        nostro = logging.getLogger("ibid")
        gestori_prima, livello_prima = list(nostro.handlers), nostro.level
        finto = logging.NullHandler()
        padre.handlers.append(finto)
        nostro.handlers = []
        try:
            warmup._rendi_visibile()
            assert finto in nostro.handlers
            assert nostro.level == logging.INFO
        finally:
            padre.handlers.remove(finto)
            nostro.handlers, nostro.level = gestori_prima, livello_prima

    def test_spento_non_avvia_niente(self, monkeypatch):
        monkeypatch.setattr(warmup, "ATTIVO", False)
        chiamato = []
        assert warmup.in_sottofondo([("x", lambda: chiamato.append("x"))]) is None
        assert chiamato == []


class TestApi:
    def test_l_avvio_dell_app_scalda_in_sottofondo(self, monkeypatch):
        """Che il ciclo di vita di FastAPI lo chiami davvero: senza questo,
        `warmup.py` sarebbe un modulo corretto che nessuno esegue."""
        fastapi_testclient = pytest.importorskip("fastapi.testclient")
        import src.api.main as api

        chiamate = []
        monkeypatch.setattr(api.warmup, "in_sottofondo", lambda: chiamate.append(True))
        with fastapi_testclient.TestClient(api.app) as c:
            assert c.get("/health").json() == {"status": "ok"}
        assert chiamate == [True]
