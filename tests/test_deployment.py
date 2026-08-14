"""A-05: il backend può girare altrove, e il modo di provarlo è un'assenza.

Il criterio del task è *«backend su una macchina, Qdrant e LLM su un'altra,
**senza modifiche al sorgente**»*. Non si verifica con due macchine — si
verifica mostrando che nel sorgente non c'è niente da modificare: nessun
indirizzo cablato, e due variabili d'ambiente che li portano entrambi.

È lo stesso tipo di test di Q-06 e A-02: guarda il repo, non una funzione. Il
valore di questi file non è che funzionino oggi, è che il quindicesimo
`localhost` non entri senza che nessuno se ne accorga.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import src.config as cfg

ROOT = Path(__file__).parent.parent


def sorgenti_di_produzione() -> list[Path]:
    """Tutto `src/`, tranne il modulo che gli indirizzi li dichiara."""
    return [p for p in (ROOT / "src").rglob("*.py") if p.name != "config.py"]


def righe_di_codice(path: Path) -> list[tuple[int, str]]:
    """Le righe che non sono commenti. Un indirizzo dentro una spiegazione è
    documentazione; dentro un'espressione è un vincolo."""
    fuori = []
    for n, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        pulita = riga.strip()
        if pulita and not pulita.startswith("#"):
            fuori.append((n, riga))
    return fuori


class TestNienteIndirizziCablati:
    #: Un indirizzo di rete scritto a mano. `host.docker.internal` compreso: è
    #: un default di deployment, e nel sorgente sarebbe un vincolo.
    INDIRIZZO = re.compile(
        r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|host\.docker\.internal|\d+\.\d+\.\d+\.\d+)"
    )

    def test_nessun_modulo_di_src_nomina_un_host(self):
        """Se un indirizzo entrasse qui, «senza modifiche al sorgente»
        smetterebbe di essere vero e nessun test lo direbbe."""
        colpevoli = []
        for path in sorgenti_di_produzione():
            for n, riga in righe_di_codice(path):
                if self.INDIRIZZO.search(riga):
                    colpevoli.append(f"{path.relative_to(ROOT)}:{n}: {riga.strip()}")
        assert colpevoli == [], "indirizzo cablato nel sorgente:\n" + "\n".join(colpevoli)

    def test_i_due_indirizzi_arrivano_dall_ambiente(self):
        sorgente = (ROOT / "src" / "config.py").read_text(encoding="utf-8")
        for variabile in ("QDRANT_URL", "LLM_BASE_URL"):
            assert re.search(rf'{variabile}.*os\.getenv\("{variabile}"', sorgente), variabile

    def test_il_default_resta_quello_di_sviluppo(self):
        """Un clone appena scaricato deve funzionare senza `.env`: i default
        descrivono la macchina di sviluppo, non il container."""
        assert cfg.QDRANT_URL.startswith("http")
        assert cfg.LLM_BASE_URL.endswith("/v1")


class TestCompose:
    TESTO = (ROOT / "compose.yml").read_text(encoding="utf-8")

    @pytest.mark.parametrize("variabile", ["QDRANT_URL", "LLM_BASE_URL"])
    def test_l_indirizzo_e_interpolato_non_scritto(self, variabile):
        """`${QDRANT_URL:-...}` e non un valore: è ciò che rende «un'altra
        macchina» una variabile invece di una modifica al file."""
        assert re.search(rf"{variabile}: \$\{{{variabile}:-", self.TESTO), variabile

    def test_l_llm_non_e_un_servizio_di_questo_compose(self):
        """E non lo diventerà: gira con la GPU, che il container non ha.
        STACK.md impone che si raggiunga solo da `LLM_BASE_URL`."""
        assert "ollama" not in self.TESTO.lower().split("# ")[0]
        assert not re.search(r"^\s{2}(ollama|llama):", self.TESTO, re.M)

    def test_qdrant_e_opzionale(self):
        """Con `QDRANT_URL` che punta altrove, il profilo non parte — e la
        dipendenza non deve bloccare l'avvio dell'API."""
        assert "required: false" in self.TESTO
        assert 'profiles: ["full", "eval", "demo"]' in self.TESTO

    def test_qdrant_e_pinnato(self):
        """`:latest` significa che due macchine possono avere due Qdrant
        diversi, e un indice è un formato su disco."""
        assert re.search(r"image: qdrant/qdrant:v\d+\.\d+", self.TESTO)

    def test_l_healthcheck_di_qdrant_non_usa_strumenti_che_non_ha(self):
        """L'immagine di Qdrant non ha né curl né wget. Un healthcheck che non
        può girare lascia il servizio `starting` per sempre, e
        `depends_on: service_healthy` non parte mai."""
        blocco = self.TESTO.split("qdrant:", 1)[1]
        assert "curl" not in blocco.split("volumes:")[0]

    def test_host_docker_internal_funziona_anche_su_linux(self):
        """Su Linux non esiste da solo: senza `extra_hosts` il default
        funzionerebbe su due sistemi su tre."""
        assert "host.docker.internal:host-gateway" in self.TESTO

    def test_i_pesi_dei_modelli_stanno_su_un_volume(self):
        """~2,5 GB. Nell'immagine sarebbero layer, senza volume un download a
        ogni avvio prima della prima risposta."""
        assert "model_cache:/cache" in self.TESTO


class TestImmagine:
    DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    def test_il_dockerfile_non_cabla_indirizzi(self):
        for n, riga in righe_di_codice(ROOT / "Dockerfile"):
            assert not TestNienteIndirizziCablati.INDIRIZZO.search(riga.replace("localhost:8000", "")), \
                f"Dockerfile:{n}"

    def test_l_acceleratore_gpu_non_e_nell_immagine(self):
        """Gli extra ONNX si escludono a vicenda e dipendono dalla piattaforma
        (Q-05): un'immagine che ne cablasse uno girerebbe su una macchina sola."""
        assert "gpu-directml" not in self.DOCKERFILE
        assert "onnxruntime-directml" not in self.DOCKERFILE

    def test_non_gira_da_root(self):
        assert re.search(r"^USER \w+", self.DOCKERFILE, re.M)

    @pytest.mark.parametrize("escluso", ["data/", "eval/", ".git/", ".env"])
    def test_il_contesto_di_build_esclude_il_peso_morto(self, escluso):
        """Senza, ogni build spedisce 2,3 GB al demone — e nessuno di quei byte
        serve a un backend che legge da Qdrant."""
        assert escluso in self.DOCKERIGNORE

    def test_le_cache_dei_modelli_hanno_un_percorso_dichiarato(self):
        """Il default di fastembed è `%TEMP%`, che il sistema può svuotare — è
        già successo durante I-10. In un container il default è peggio: sparisce
        a ogni riavvio."""
        assert "FASTEMBED_CACHE_PATH=/cache/fastembed" in self.DOCKERFILE
        assert "HF_HOME=/cache/huggingface" in self.DOCKERFILE


class TestEnvExample:
    TESTO = (ROOT / ".env.example").read_text(encoding="utf-8")

    @pytest.mark.parametrize("variabile", ["QDRANT_URL", "LLM_BASE_URL"])
    def test_documenta_i_due_indirizzi(self, variabile):
        assert re.search(rf"^{variabile}=", self.TESTO, re.M)

    def test_non_contiene_configurazione_di_richiesta(self):
        """Metterla qui la renderebbe di nuovo globale, che è il difetto che
        A-02 ha appena tolto: due richieste concorrenti la condividerebbero."""
        vietate = ("TOP_K", "RETRIEVAL_MODE", "RERANK", "TEMPERATURE", "SEARCH_EXACT")
        presenti = [v for v in vietate if re.search(rf"^{v}=", self.TESTO, re.M)]
        assert presenti == [], f"configurazione di richiesta in .env.example: {presenti}"
