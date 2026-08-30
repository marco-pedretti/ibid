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


def blocco_del_servizio(nome: str) -> str:
    """Le righe di un servizio di `compose.yml`, dalla sua intestazione al
    servizio successivo.

    **Serve perché cercare una stringa nel file intero non prova niente.** Il
    controllo sull'healthcheck di Qdrant era scritto come `TESTO.split("qdrant:")`
    e cadeva sulla prima occorrenza, che è dentro `${QDRANT_URL:-http://qdrant:6333}`
    dell'API: leggeva un pezzo di ambiente e trovava, correttamente, nessun
    `curl`. Passava per la ragione sbagliata, e avrebbe continuato a passare
    anche con un healthcheck rotto.
    """
    testo = (ROOT / "compose.yml").read_text(encoding="utf-8")
    righe = testo.splitlines()
    for i, riga in enumerate(righe):
        if riga == f"  {nome}:":
            fine = next(
                (j for j in range(i + 1, len(righe)) if re.match(r"^  \S", righe[j])),
                len(righe),
            )
            return "\n".join(righe[i:fine])
    raise AssertionError(f"compose.yml non ha un servizio «{nome}»")


def codice_del_servizio(nome: str) -> str:
    """Come sopra, ma senza i commenti: la stessa trappola un livello piu' in
    la'. Un commento che **nomina** una direttiva per spiegare perche' non c'e'
    la fa trovare a chi cerca nel testo, e la decisione si legge al rovescio."""
    righe = blocco_del_servizio(nome).splitlines()
    return "\n".join(r for r in righe if not r.strip().startswith("#"))


TESTO_COMPOSE = (ROOT / "compose.yml").read_text(encoding="utf-8")


class TestCompose:
    TESTO = TESTO_COMPOSE

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
        # `demo` non c'è più: da U-08 ha un Qdrant suo, con un volume suo.
        assert 'profiles: ["full", "eval"]' in blocco_del_servizio("qdrant")

    def test_qdrant_e_pinnato(self):
        """`:latest` significa che due macchine possono avere due Qdrant
        diversi, e un indice è un formato su disco."""
        assert re.search(r"image: qdrant/qdrant:v\d+\.\d+", self.TESTO)

    def test_l_healthcheck_di_qdrant_non_usa_strumenti_che_non_ha(self):
        """L'immagine di Qdrant non ha né curl né wget. Un healthcheck che non
        può girare lascia il servizio `starting` per sempre, e
        `depends_on: service_healthy` non parte mai."""
        definizione = self.TESTO.split("x-qdrant-salute:", 1)[1].split("\nservices:")[0]
        # Il comando, non il blocco: il commento accanto **nomina** curl e wget
        # per dire che non ci sono, e cercarli nel testo li troverebbe li'.
        comando = next(r for r in definizione.splitlines() if r.strip().startswith("test:"))
        assert "curl" not in comando and "wget" not in comando
        assert "/qdrant/qdrant" in comando
        # E che tutti e due i Qdrant la usino: una definizione giusta che un
        # servizio non riferisce non controlla quel servizio.
        for nome in ("qdrant", "qdrant-demo"):
            assert "healthcheck: *qdrant-salute" in blocco_del_servizio(nome), nome

    def test_host_docker_internal_funziona_anche_su_linux(self):
        """Su Linux non esiste da solo: senza `extra_hosts` il default
        funzionerebbe su due sistemi su tre."""
        assert "host.docker.internal:host-gateway" in self.TESTO

    def test_i_pesi_dei_modelli_stanno_su_un_volume(self):
        """~2,5 GB. Nell'immagine sarebbero layer, senza volume un download a
        ogni avvio prima della prima risposta."""
        assert "model_cache:/cache" in self.TESTO


class TestLaDemoNonSopravviveAlRiavvio:
    """Trovato su Arch il 2026-08-28, dopo un riavvio: `localhost:8000`
    rispondeva **senza che nessuno avesse avviato niente**.

    `restart: unless-stopped` dice al demone di rimettere in piedi il container
    quando riparte, ed e' esattamente cio' che si vuole da un servizio. Da una
    demo no: chi la prova una volta se la ritrova accesa a ogni avvio, con la
    porta 8000 occupata, senza ricordarsi di averlo chiesto. La differenza fra i
    due profili e' una decisione, quindi ha un test invece di un commento.
    """

    @pytest.mark.parametrize("servizio", ["api-demo", "seed-demo", "qdrant-demo"])
    def test_il_profilo_demo_non_torna_su_da_solo(self, servizio):
        # **Senza i commenti**, che nominano `unless-stopped` proprio per dire
        # che li' non lo si vuole: cercarlo nel testo intero ritroverebbe la
        # spiegazione e leggerebbe la decisione al contrario.
        blocco = codice_del_servizio(servizio)
        assert "unless-stopped" not in blocco, (
            f"«{servizio}» tornerebbe su a ogni riavvio della macchina"
        )
        assert 'restart: "no"' in blocco, (
            f"«{servizio}» eredita la politica dall'ancora: va sovrascritta"
        )

    def test_il_servizio_vero_invece_torna_su(self):
        """Il rovescio, senza il quale il test sopra si soddisferebbe togliendo
        `unless-stopped` da tutto il file.

        `api` non ce l'ha scritto: lo eredita dall'ancora `x-api`, ed e' proprio
        per questo che `api-demo` deve sovrascriverlo invece di ometterlo.
        """
        assert "unless-stopped" in codice_del_servizio("qdrant")
        pezzo = TESTO_COMPOSE.split("x-api: &api", 1)[1]
        ancora = pezzo.split("x-api-env")[0]
        assert "restart: unless-stopped" in ancora


class TestProfiloDemo:
    """U-08: `docker compose --profile demo up`, e i modi in cui potrebbe nuocere.

    Il criterio del task è «in meno di due minuti senza download», e quello si
    verifica avviandolo. Qui si verifica l'altra metà, che avviarlo non prova:
    che non distrugga niente, e che non si scontri con la macchina di chi
    sviluppa.
    """

    TESTO = (ROOT / "compose.yml").read_text(encoding="utf-8")

    def test_ha_un_qdrant_suo_con_un_volume_suo(self):
        """**La difesa che conta.** L'indice di `full` sono ore di GPU: un
        profilo che ci scrivesse sopra i 1.758 chunk della demo li
        distruggerebbe con un comando che sembra innocuo."""
        assert "qdrant_demo_data:/qdrant/storage" in blocco_del_servizio("qdrant-demo")
        assert "qdrant_data:/qdrant/storage" in blocco_del_servizio("qdrant")

    def test_il_qdrant_della_demo_non_pubblica_la_porta(self):
        """Nessuno ci parla da fuori, e pubblicarla la farebbe scontrare con il
        Qdrant di sviluppo sulla 6333: un guasto al primo avvio, proprio sulla
        macchina di chi sviluppa."""
        assert "ports:" not in blocco_del_servizio("qdrant-demo")

    def test_la_demo_non_eredita_un_qdrant_url_esportato(self):
        """Chi sviluppa ce l'ha esportata verso il proprio indice, e la demo non
        deve finirci dentro per una riga rimasta in una shell."""
        for nome in ("api-demo", "seed-demo"):
            assert "${DEMO_QDRANT_URL:-" in blocco_del_servizio(nome), nome
            assert "${QDRANT_URL:-" not in blocco_del_servizio(nome), nome

    def test_l_api_aspetta_che_l_indice_sia_carico(self):
        """Non `service_healthy`: il caricamento **finisce**. Aprire la porta
        prima mostrerebbe un dataset vuoto al primo colpo d'occhio."""
        assert "condition: service_completed_successfully" in blocco_del_servizio("api-demo")

    def test_il_caricamento_e_un_lavoro_non_un_servizio(self):
        """`unless-stopped` lo rimetterebbe in piedi per sempre a ogni uscita
        riuscita."""
        assert 'restart: "no"' in blocco_del_servizio("seed-demo")

    def test_l_indice_sta_nell_immagine_e_non_e_montato(self):
        """**Il difetto per cui l'immagine pubblicata non serviva a niente.**

        Montato da `compose.yml`, `data/demo/` obbligava chi avvia la demo ad
        avere una copia del repository, immagine scaricata compresa: senza il
        mount `seed-demo` non trova i file e la demo parte vuota. Il `curl`
        dell'immagine toglie di mezzo il clone solo se l'indice viaggia dentro.

        Le due meta' si controllano insieme perche' e' il *paio* a essere
        giusto: copiarlo lasciando il mount lo lascerebbe dipendere lo stesso.
        """
        assert "/app/data/demo" not in codice_del_servizio("seed-demo")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "COPY data/demo ./data/demo" in dockerfile

    def test_l_indice_entra_nel_contesto_di_build(self):
        """`.dockerignore` esclude `data/`, quindi senza l'eccezione la `COPY`
        qui sopra fallisce alla costruzione: il guasto e' rumoroso, ma arriva in
        CI invece che qui."""
        ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        assert "!data/demo/" in ignore
        elenco = ignore.splitlines()
        assert elenco.index("data/") < elenco.index("!data/demo/")

    def test_la_demo_cerca_in_esatta(self):
        """L'unico punto in cui la demo non è configurata come la valutazione, e
        la pagina «Che cos'è» lo dice **per nome**: senza questa riga quella
        frase sarebbe una dichiarazione non verificata. La ragione è OQ-09,
        l'ANN di `ledger` che ha reso dodici punti in meno a configurazione
        identica, da solo."""
        assert 'SEARCH_EXACT: "1"' in blocco_del_servizio("api-demo")

    def test_i_tre_servizi_condividono_una_build_sola(self):
        """Senza un nome d'immagine esplicito, compose costruirebbe la stessa
        immagine tre volte."""
        assert "image: ${IBID_IMAGE:-ibid:local}" in self.TESTO.split("services:", 1)[0]
        for nome in ("api", "api-demo", "seed-demo"):
            assert "<<: *api" in blocco_del_servizio(nome), nome

    def test_il_default_resta_la_costruzione_locale(self):
        """**La strada provata su una macchina vergine e' quella che non cambia.**
        `IBID_IMAGE` aggiunge l'immagine pubblicata come alternativa; se il
        default diventasse il registro, `docker compose --profile demo up` su un
        clone senza rete smetterebbe di funzionare, e quello e' il criterio di
        U-09."""
        assert ":-ibid:local}" in self.TESTO, "il default non e' piu' la build locale"

    def test_scaricare_invece_di_costruire_e_esplicito(self):
        """`--no-build` e `--pull always` scritti a mano: con una sezione `build`
        accanto a `image`, quale delle due vinca dipende da default che cambiano
        fra versioni di compose. Il bersaglio non e' compose, e' il lettore."""
        righe = (ROOT / "Makefile").read_text(encoding="utf-8").splitlines()
        i = righe.index("demo-pull:")
        ricetta = [r for r in righe[i + 1 :] if r.startswith("\t")]
        assert ricetta, "il bersaglio demo-pull non ha una ricetta"
        assert "--no-build" in ricetta[0] and "--pull always" in ricetta[0]
        phony = righe[: righe.index("")]  # il blocco .PHONY, fino alla riga vuota
        assert any("demo-pull" in r for r in phony), "manca da .PHONY"


class TestImmagine:
    DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    DOCKERIGNORE = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    def test_il_dockerfile_non_cabla_indirizzi(self):
        for n, riga in righe_di_codice(ROOT / "Dockerfile"):
            assert not TestNienteIndirizziCablati.INDIRIZZO.search(riga.replace("localhost:8000", "")), \
                f"Dockerfile:{n}"

    def test_nessun_acceleratore_nell_immagine_di_default(self):
        """Gli extra ONNX si escludono a vicenda e dipendono dalla piattaforma
        (Q-05): un'immagine che ne cablasse uno girerebbe su una macchina sola.

        Resta **raggiungibile senza toccare il file**, che è tutto ciò che una
        cucitura deve fare — la stessa forma di `PREFERRED_ACCELERATORS`.
        """
        assert re.search(r'^ARG GPU_EXTRA=""', self.DOCKERFILE, re.M)
        istruzioni = [riga for _, riga in righe_di_codice(ROOT / "Dockerfile")]
        assert not [r for r in istruzioni if "onnxruntime" in r or "gpu-" in r]

    def test_l_extra_non_installa_anche_il_progetto(self):
        """`.[extra]` installerebbe `src` in site-packages accanto a quello in
        `/app`, con la garanzia che prima o poi si importi quello sbagliato."""
        assert '".[' not in self.DOCKERFILE
        assert "--extra" in self.DOCKERFILE

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
