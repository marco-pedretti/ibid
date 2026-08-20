"""A-06: il confine fra la dashboard e il backend, verificato invece che affermato.

Il criterio del ROADMAP era scritto come un `grep`: *«`grep -r "^from src\\." dashboard/`
non trova più niente»*. Applicandolo si è visto che quel `grep` è un **proxy** per
la cosa che interessa, e che cattura anche due cose che non c'entrano. Il
ROADMAP §11 porta ora la versione precisa; questo file la fa rispettare.

**Ciò che il confine vieta**: che la dashboard *esegua* la pipeline. Retrieval,
generazione, verifica, accesso a Qdrant — tutto passa dall'API, o la dashboard
non è un consumatore del sistema, è un secondo sistema.

**Ciò che il confine non vieta**: leggere i propri file locali. `eval/results/`
e `eval/golden/` stanno sul disco della dashboard, non dietro un endpoint, e la
Fase 7 espone il *sistema*, non l'archivio degli esperimenti — la sua lista di
endpoint è dichiarata vincolante in §11. Per leggerli servono i contratti dati
del §3, e un contratto condiviso è il contrario di una duplicazione.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DASHBOARD = ROOT / "dashboard"


def moduli() -> list[Path]:
    return sorted(p for p in DASHBOARD.rglob("*.py") if "__pycache__" not in p.parts)


def import_di_src(path: Path) -> list[tuple[int, str]]:
    """Ogni import da `src.`, ovunque sia — anche dentro una funzione.

    `^from src\\.` non basta: un import annidato è un import, e nasconderlo in
    una funzione era esattamente il modo in cui `state.py` teneva il suo client
    Qdrant fuori dalla vista del grep.
    """
    fuori = []
    for n, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.match(r"\s*(from src[.\s]|import src[.\s])", riga):
            fuori.append((n, riga.strip()))
    return fuori


#: I moduli che *sono* la pipeline. Un import da qui significa che la dashboard
#: ha ricominciato a fare il lavoro del backend.
PIPELINE = (
    "src.index",        # Qdrant e gli embedding
    "src.retrieval",    # recupero, fusione, rerank
    "src.generation",   # prompt, LLM, verifica
    "src.service",      # il servizio si raggiunge via HTTP, non importandolo
    "src.config",       # la configurazione di richiesta arriva dall'API
)

#: Cosa resta lecito, e perché. Ogni voce è una decisione, non un'eccezione
#: concessa a chi non aveva voglia di sistemare.
AMMESSI = {
    "src.datasets.schema": "contratto dati del §3, per leggere eval/results/",
    "src.datasets.golden": "contratto dati del §3, per leggere eval/golden/",
    "src.eval.noise_floor": "formato di un file locale che l'API non serve",
    "src.eval.run_config": "come si legge un EvalRun archiviato",
    "src.ingestion.ocr_tables": "interpretare markup OCR è un formato, non la pipeline",
}


class TestNientePipeline:
    def test_la_dashboard_non_esegue_la_pipeline(self):
        """È il criterio vero di A-06.

        `src.config` è nell'elenco dei vietati e vale la pena dirlo: dopo A-02 la
        configurazione di richiesta non sta più lì, e una dashboard che la
        leggesse da un modulo globale starebbe usando i default del **proprio**
        processo per descrivere quelli di un backend che può girare altrove.
        """
        colpevoli = []
        for path in moduli():
            for n, riga in import_di_src(path):
                if any(m in riga for m in PIPELINE):
                    colpevoli.append(f"{path.relative_to(ROOT)}:{n}: {riga}")
        assert colpevoli == [], (
            "la dashboard ha ricominciato a fare il lavoro del backend:\n"
            + "\n".join(colpevoli)
        )

    def test_ogni_import_rimasto_ha_una_ragione_scritta(self):
        """Un import che nessuno ha deciso è un import che nessuno rivedrà.

        Aggiungerne uno nuovo richiede di scrivere qui perché non è pipeline —
        cioè di prendere la decisione invece di scivolarci dentro.
        """
        senza_ragione = []
        for path in moduli():
            for n, riga in import_di_src(path):
                if not any(modulo in riga for modulo in AMMESSI):
                    senza_ragione.append(f"{path.relative_to(ROOT)}:{n}: {riga}")
        assert senza_ragione == [], (
            "import da `src.` non previsto: se è legittimo, aggiungilo ad "
            "AMMESSI con la ragione.\n" + "\n".join(senza_ragione)
        )

    def test_nessun_client_qdrant(self):
        """Chi sa dove sta Qdrant è il servizio. Era la cosa che rendeva la
        dashboard un secondo backend invece di un client."""
        colpevoli = [
            f"{p.relative_to(ROOT)}"
            for p in moduli()
            if "get_client" in p.read_text(encoding="utf-8")
        ]
        assert colpevoli == []

    @pytest.mark.parametrize("modulo", ["retrieval_probe", "failure_store"])
    def test_i_due_moduli_che_avevano_una_copia_ora_chiedono(self, modulo):
        """Le due copie della pipeline erano qui. Il test le tiene fuori
        nominandole: sono i posti in cui rientrerebbe per primo."""
        testo = (DASHBOARD / f"{modulo}.py").read_text(encoding="utf-8")
        assert "api_client" in testo
        for parola in ("rrf_fuse", "cross_encode", "encode_sparse_query", "search_batch"):
            assert parola not in testo, f"{modulo}.py rifà il retrieval: {parola}"


class TestIlClientNonDipendeDaStreamlit:
    """`api_client.py` è verificabile senza un'app in esecuzione.

    È la stessa regola che `retrieval_probe` e `failure_store` già portavano
    scritta in cima: la logica sta sotto, Streamlit sopra. Un client HTTP che
    importasse `streamlit` non sarebbe riusabile da uno script, e il prossimo
    consumatore lo riscriverebbe.
    """

    def test_niente_streamlit(self):
        testo = (DASHBOARD / "api_client.py").read_text(encoding="utf-8")
        assert "streamlit" not in testo

    def test_l_indirizzo_del_backend_e_una_variabile(self):
        """La dashboard può girare altrove: è la stessa proprietà che A-05 ha
        dato al backend, applicata al suo consumatore."""
        testo = (DASHBOARD / "api_client.py").read_text(encoding="utf-8")
        assert 'os.getenv("IBID_API_URL"' in testo
