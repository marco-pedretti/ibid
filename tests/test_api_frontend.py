"""U-08: nella consegna l'API serve anche il frontend, dalla stessa origine.

In sviluppo sono due processi su due porte e Vite fa da proxy; nell'immagine
sono una cosa sola, ed e' cio' che rende vera (invece che aspirazionale) la
scelta di non avere CORS nel backend.

Il difetto contro cui questi test esistono e' **invisibile a occhio**: un
montaggio su `/` dichiarato prima delle rotte se le prende tutte, e l'API
risponde 404 su se stessa. La prova e' interrogare l'applicazione montata.
"""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.main import monta_frontend

ROOT = Path(__file__).parent.parent


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "index.html").write_text("<title>ibid</title>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return tmp_path


class TestMontaggio:
    def test_senza_dist_non_monta_niente(self, tmp_path):
        """Il caso di `make dev`: la cartella non c'e', e l'avvio non deve
        fallire per questo."""
        app = FastAPI()
        assert monta_frontend(app, tmp_path / "non-esiste", attivo=True) is False

    def test_spento_non_monta_neanche_con_la_cartella(self, dist):
        """`make ui-check` lascia una `ui/dist` in ogni clone, ed e' costruita
        per il proxy di Vite: servirla darebbe una pagina che si carica e non
        parla col backend."""
        app = FastAPI()
        assert monta_frontend(app, dist, attivo=False) is False

    def test_serve_la_pagina(self, dist):
        app = FastAPI()
        assert monta_frontend(app, dist, attivo=True) is True
        with TestClient(app) as c:
            assert "<title>ibid</title>" in c.get("/").text
            assert c.get("/assets/app.js").status_code == 200

    def test_un_percorso_sconosciuto_resta_un_404(self, dist):
        """E va bene cosi': l'interfaccia e' **una pagina sola**, senza router e
        senza percorsi propri. Un ripiego su `index.html` per ogni 404
        risponderebbe con l'applicazione anche a un errore di battitura
        nell'API, cioe' nasconderebbe il caso in cui serve di piu' vederlo."""
        app = FastAPI()
        monta_frontend(app, dist, attivo=True)
        with TestClient(app) as c:
            assert c.get("/qualcosa").status_code == 404

    def test_le_rotte_dell_api_vincono_sul_montaggio(self, dist):
        """**Il test che conta.** Starlette prova le rotte nell'ordine in cui
        sono dichiarate: montare `/` prima delle rotte le seppellirebbe tutte, e
        il sintomo sarebbe un'API che risponde con la pagina."""
        app = FastAPI()

        @app.get("/health")
        def _salute() -> dict:
            return {"status": "ok"}

        monta_frontend(app, dist, attivo=True)
        with TestClient(app) as c:
            assert c.get("/health").json() == {"status": "ok"}


class TestImmagine:
    """Che l'immagine accenda l'interruttore, e sia l'unica a farlo.

    Senza questo, il montaggio sarebbe una funzione corretta che nel container
    nessuno chiama, e il sintomo sarebbe un `docker compose --profile demo up`
    che serve un'API senza interfaccia."""

    DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    def test_l_immagine_serve_il_frontend(self):
        assert re.search(r"^ENV SERVE_UI=1", self.DOCKERFILE, re.M)

    def test_il_bundle_e_costruito_per_la_stessa_origine(self):
        """`VITE_API_BASE=""` e' cio' che fa chiamare `/datasets` invece di
        `/api/datasets`: senza, la pagina si caricherebbe e non parlerebbe."""
        assert re.search(r'^ENV VITE_API_BASE=""', self.DOCKERFILE, re.M)

    def test_il_frontend_entra_nel_contesto_ma_non_le_sue_dipendenze(self):
        ignorati = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        assert "ui/" not in ignorati
        assert "ui/node_modules/" in ignorati

    def test_spento_di_default(self):
        """Fuori dall'immagine nessuno lo accende: e' cio' che tiene `make dev`
        e `make api-local` come sono. Il default si legge nel sorgente e non in
        `cfg.SERVE_UI`, che vale quello che dice l'ambiente di chi esegue."""
        sorgente = (ROOT / "src" / "config.py").read_text(encoding="utf-8")
        assert 'SERVE_UI: bool = os.getenv("SERVE_UI", "")' in sorgente
