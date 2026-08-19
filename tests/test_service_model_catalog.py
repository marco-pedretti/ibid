"""A-08 — il catalogo dei modelli, e cosa fa quando il motore non parla.

Il punto del task non e' elencare modelli: `models()` lo faceva gia'. E' che la
coppia (modello, finestra) **non si puo' dedurre da un nome**, e che i tre campi
che il progetto dichiarava a mano -- finestra, quantizzazione, famiglia -- sono
leggibili dal motore. Questi test fissano le tre condizioni in cui quella lettura
non deve rompersi.
"""

from __future__ import annotations

import pytest

from src.service.catalog import (
    ModelInfo,
    _come_info,
    _nativo,
    dimentica_modelli,
    model_catalog,
)


@pytest.fixture(autouse=True)
def cache_pulita():
    """La cache dei dettagli e' di modulo, quindi due casi che usano lo stesso
    nome del modello si passerebbero il risultato. Azzerarla prima di ognuno e'
    piu' onesto che dare nomi diversi a ogni test per aggirare il problema."""
    dimentica_modelli()
    yield
    dimentica_modelli()


def _elenco(*nomi: str):
    return lambda url, timeout: {"data": [{"id": n} for n in nomi]}


def _mostra(mappa: dict[str, dict]):
    def dettagli(base: str, nome: str, timeout: int) -> dict:
        if nome not in mappa:
            raise RuntimeError("questo modello non risponde")
        return mappa[nome]

    return dettagli


GEMMA = {
    "model_info": {"gemma4.context_length": 131072, "gemma4.block_count": 34},
    "details": {"family": "gemma4", "quantization_level": "Q4_K_M", "parameter_size": "8.0B"},
}
QWEN = {
    "model_info": {"qwen35.context_length": 262144},
    "details": {"family": "qwen35", "quantization_level": "Q4_K_M", "parameter_size": "9.7B"},
}


class TestLaFinestraSiLeggePerPattern:
    def test_due_famiglie_diverse_nella_stessa_chiamata(self):
        """La chiave contiene il nome della famiglia: `gemma4.context_length`,
        `qwen35.context_length`. Cercarla per nome funzionerebbe su un modello
        solo, ed e' precisamente cio' che renderebbe A-08 «solo per gemma4»."""
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("gemma4:latest", "qwen3.5:latest"),
            dettagli=_mostra({"gemma4:latest": GEMMA, "qwen3.5:latest": QWEN}),
        )
        assert [m.context_max for m in c] == [131072, 262144]
        assert [m.family for m in c] == ["gemma4", "qwen35"]

    def test_il_massimo_non_e_uno_solo(self):
        """Misurato: `gemma4:latest` 131.072, `gemma4:12b` 262.144. E' la ragione
        per cui U-16 filtra le taglie sul modello scelto invece di offrirne una
        lista sola."""
        grande = {**GEMMA, "model_info": {"gemma4.context_length": 262144}}
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("gemma4:12b", "gemma4:latest"),
            dettagli=_mostra({"gemma4:12b": grande, "gemma4:latest": GEMMA}),
        )
        assert {m.name: m.context_max for m in c} == {
            "gemma4:12b": 262144,
            "gemma4:latest": 131072,
        }


class TestDegradaInvecediRompersi:
    def test_un_modello_che_non_risponde_entra_col_solo_nome(self):
        """Un fallimento per modello e' isolato: gli altri restano. Un motore
        che non e' Ollama fa fallire tutti, e il catalogo diventa la lista dei
        nomi -- che e' esattamente cio' che c'era prima di A-08."""
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("c'e", "sparito"),
            dettagli=_mostra({"c'e": GEMMA}),
        )
        assert c[0].context_max == 131072
        assert c[1] == ModelInfo(name="sparito")

    def test_senza_nomi_il_catalogo_e_vuoto(self):
        """`models()` restituisce `[]` quando l'endpoint non risponde, e il
        catalogo non inventa una riga: dichiarare l'assenza, non simularla."""

        def rotto(url, timeout):
            raise RuntimeError("LLM irraggiungibile")

        assert model_catalog("http://x/v1", fetch=rotto) == []

    @pytest.mark.parametrize("payload", [None, {}, {"model_info": "non un dizionario"}, 42])
    def test_un_payload_strano_lascia_il_nome(self, payload):
        assert _come_info("m", payload) == ModelInfo(name="m")


class TestLUrlNativo:
    def test_toglie_solo_il_v1_finale(self):
        assert _nativo("http://localhost:11434/v1") == "http://localhost:11434"
        assert _nativo("http://localhost:11434/v1/") == "http://localhost:11434"

    def test_un_endpoint_che_non_finisce_per_v1_resta_intero(self):
        """E l'URL che ne esce non rispondera' a `/api/show`: la scoperta
        fallisce da sola, che e' il comportamento voluto su un motore diverso."""
        assert _nativo("http://vllm:8000") == "http://vllm:8000"


DERIVATO = {
    "model_info": {"gemma4.context_length": 131072},
    "parameters": (
        "num_ctx                        8192\n"
        "temperature                    1\n"
        "top_k                          64"
    ),
    "details": {
        "parent_model": "gemma4:e2b",
        "family": "gemma4",
        "quantization_level": "Q4_K_M",
        "parameter_size": "5.1B",
    },
}


class TestLaTagliaConfigurataEIlSuoModello:
    """Cio' che U-16 mette nei due selettori.

    `context_max` dice cosa l'architettura regge, `context` cosa girera'
    davvero: sono due cose, e confonderle farebbe offrire 131.072 a un modello
    fissato a 8192.
    """

    def test_un_modello_derivato_porta_la_sua_finestra_e_il_suo_genitore(self):
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("gemma4-8k"),
            dettagli=_mostra({"gemma4-8k": DERIVATO}),
        )[0]
        assert c.context == 8192
        assert c.context_max == 131072
        assert c.parent == "gemma4:e2b"

    def test_un_modello_base_non_ha_finestra_fissata_ne_genitore(self):
        """Assente significa «decide il motore», che e' un'informazione e non un
        dato mancante: e' la differenza fra «gira a 8192» e «gira a quello che il
        servizio ha deciso»."""
        c = model_catalog(
            "http://x/v1", fetch=_elenco("gemma4:e2b"), dettagli=_mostra({"gemma4:e2b": GEMMA})
        )[0]
        assert c.context is None
        assert c.parent == ""

    @pytest.mark.parametrize(
        "parametri", [None, 42, "", "temperature 1", "num_ctx", "num_ctx non-un-numero"]
    )
    def test_un_blocco_parametri_strano_non_inventa_una_finestra(self, parametri):
        d = {**DERIVATO, "parameters": parametri}
        assert _come_info("m", d).context is None

    def test_raggruppare_non_richiede_di_interpretare_i_nomi(self):
        """`parent_model` viene dal motore. Dedurre `gemma4-8k` -> `gemma4`
        spezzando una stringa sarebbe una convenzione, e le convenzioni si
        rompono il giorno in cui qualcuno chiama un modello diversamente."""
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("gemma4:e2b", "taglia-corta"),
            dettagli=_mostra({"gemma4:e2b": GEMMA, "taglia-corta": DERIVATO}),
        )
        sotto = {m.name for m in c if m.parent == "gemma4:e2b"}
        assert sotto == {"taglia-corta"}


class TestIlCostoDiChiederli:
    """Misurato il 2026-08-19: `/api/show` costa ~2 s e va chiesto per modello.

    Con sedici modelli `/datasets` -- la prima chiamata che il frontend fa --
    passava da 2 a **35 secondi**. Due rimedi, e servono tutti e due: il
    parallelo toglie il costo, la cache lo toglie anche alla seconda volta.
    """

    def test_i_dettagli_si_chiedono_una_volta_sola(self):
        chiamate: list[str] = []

        def conta(base: str, nome: str, timeout: int) -> dict:
            chiamate.append(nome)
            return GEMMA

        for _ in range(3):
            model_catalog("http://x/v1", fetch=_elenco("a", "b"), dettagli=conta)
        assert sorted(chiamate) == ["a", "b"]

    def test_un_motore_che_non_risponde_non_si_ricorda(self):
        """Memorizzare un fallimento lo renderebbe permanente: un motore muto
        adesso puo' rispondere fra un minuto."""
        tentativi: list[str] = []

        def rotto(base: str, nome: str, timeout: int) -> dict:
            tentativi.append(nome)
            raise RuntimeError("muto")

        for _ in range(2):
            model_catalog("http://x/v1", fetch=_elenco("a"), dettagli=rotto)
        assert tentativi == ["a", "a"]

    def test_l_ordine_resta_quello_dei_nomi(self):
        """Il parallelo non deve riordinare: un menu che si riordina da solo fa
        saltare la selezione a chi ha appena scelto."""
        c = model_catalog(
            "http://x/v1",
            fetch=_elenco("a", "b", "c"),
            dettagli=_mostra({"a": GEMMA, "b": QWEN, "c": GEMMA}),
        )
        assert [m.name for m in c] == ["a", "b", "c"]
