"""A-08 — il catalogo dei modelli, e cosa fa quando il motore non parla.

Il punto del task non e' elencare modelli: `models()` lo faceva gia'. E' che la
coppia (modello, finestra) **non si puo' dedurre da un nome**, e che i tre campi
che il progetto dichiarava a mano -- finestra, quantizzazione, famiglia -- sono
leggibili dal motore. Questi test fissano le tre condizioni in cui quella lettura
non deve rompersi.
"""

from __future__ import annotations

import pytest

from src.service.catalog import ModelInfo, _come_info, _nativo, model_catalog


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
