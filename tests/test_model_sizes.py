"""La scala delle finestre di U-16: cosa si legge dal motore e cosa no."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_sizes import (  # noqa: E402
    PIOLI,
    PREFISSO,
    da_pulire,
    nome_taglia,
    nome_vecchio,
    scala_per,
)
from src.service.catalog import ModelInfo  # noqa: E402


class TestIlTettoSiLeggeIPioliNo:
    def test_si_ferma_al_massimo_del_modello(self):
        """`gemma4:latest` regge 131.072, `gemma4:12b` 262.144: due scale
        diverse dallo stesso elenco di pioli."""
        assert scala_per(131072) == (8192, 16384, 32768, 65536, 131072)
        assert scala_per(262144) == (8192, 16384, 32768, 65536, 131072, 262144)

    def test_un_massimo_fuori_scala_viene_offerto_lo_stesso(self):
        """Senza questo, un modello il cui massimo non cade su una potenza di
        due non vedrebbe mai la propria finestra piu' grande. Oggi non si
        noterebbe -- i quattro installati hanno massimi che sono pioli -- e
        sarebbe il difetto che si scopre con un modello nuovo e sembra un guasto
        di quel modello."""
        assert scala_per(40960) == (8192, 16384, 32768, 40960)
        assert scala_per(100000)[-1] == 100000

    def test_un_massimo_piccolo_non_produce_una_scala_vuota(self):
        assert scala_per(4096) == (4096,)

    def test_senza_un_massimo_noto_si_prova_tutto(self):
        """Inventare un tetto che nessuno ha dichiarato sarebbe peggio che
        provarci: `crea` fallira' da sola su cio' che il motore non regge."""
        assert scala_per(None) == PIOLI

    def test_i_pioli_sono_crescenti_e_senza_ripetizioni(self):
        assert list(PIOLI) == sorted(set(PIOLI))


class TestIlNomeDiUnaTaglia:
    def test_in_multipli_di_1024(self):
        assert nome_taglia("gemma4:latest", 8192) == "ibid/gemma4-latest:8k"
        assert nome_taglia("gemma4:latest", 131072) == "ibid/gemma4-latest:128k"

    def test_una_taglia_non_tonda_tiene_il_numero(self):
        """Il nome serve a chi legge `ollama list`: `:40960` e' brutto e
        inequivocabile, `:40k` sarebbe sbagliato."""
        assert nome_taglia("m", 40960) == "ibid/m:40k"
        assert nome_taglia("m", 100000) == "ibid/m:100000"

    def test_un_modello_che_ha_gia_un_namespace_lo_perde_nel_nome(self):
        """Un nome ha **un solo** namespace e **un solo** tag: quelli del
        modello di partenza diventano parte del nome, altrimenti `ibid/` non
        avrebbe dove stare."""
        assert nome_taglia("smtek/Qwen3.8-27B:IQ3_XXS", 32768) == "ibid/smtek-Qwen3.8-27B-IQ3_XXS:32k"

    def test_ogni_taglia_sta_sotto_il_prefisso(self):
        """E' la sola cosa che rende l'elenco riconoscibile a chi non ha chiesto
        niente, e cancellabile in blocco."""
        assert all(nome_taglia("m", t).startswith(PREFISSO) for t in PIOLI)

    def test_il_nome_vecchio_resta_leggibile(self):
        """Le taglie create prima di A-09 esistono ancora sulle macchine dove
        sono nate: `--pulisci` deve saperle togliere, anche se non ne crea piu'."""
        assert nome_vecchio("gemma4:e2b", 32768) == "gemma4:e2b-32k"


class TestCosaSiPuoCancellare:
    """`--pulisci` e' l'unico comando del progetto che toglie qualcosa dalla
    macchina di chi lo lancia: cosa **non** tocca conta piu' di cosa tocca."""

    @staticmethod
    def _catalogo(monkeypatch, *voci: ModelInfo):
        monkeypatch.setattr(
            "src.service.catalog.model_catalog", lambda *a, **k: list(voci), raising=True
        )

    def test_prende_le_taglie_nuove_e_quelle_vecchie(self, monkeypatch):
        self._catalogo(
            monkeypatch,
            ModelInfo(name="ibid/gemma4-e2b:32k", parent="gemma4:e2b", context=32768),
            ModelInfo(name="gemma4:e2b-8k", parent="gemma4:e2b", context=8192),
        )
        assert da_pulire() == ["gemma4:e2b-8k", "ibid/gemma4-e2b:32k"]

    def test_non_tocca_i_modelli_base(self, monkeypatch):
        """Senza genitore non e' una taglia, e' un modello: nessun comando di
        pulizia deve poter cancellare dei pesi scaricati."""
        self._catalogo(
            monkeypatch,
            ModelInfo(name="gemma4:e2b", context_max=131072),
            ModelInfo(name="qwen3.5:latest"),
        )
        assert da_pulire() == []

    def test_non_tocca_una_taglia_fatta_a_mano(self, monkeypatch):
        """Il caso vero, su questa macchina: `Qwen3.8-27B-IQ3-32k` e' derivato e
        ha una finestra, ma non porta nessuno dei due nomi che questo script
        usa. Cancellare il lavoro di un altro perche' somiglia al proprio
        sarebbe peggio del disordine che il comando esiste per togliere."""
        self._catalogo(
            monkeypatch,
            ModelInfo(
                name="Qwen3.8-27B-IQ3-32k",
                parent="smtek/Qwen3.8-27B:IQ3_XXS",
                context=32768,
            ),
        )
        assert da_pulire() == []

    def test_una_taglia_senza_finestra_dichiarata_non_si_indovina(self, monkeypatch):
        """`context=None` vuol dire «decide il motore»: senza quel numero il
        nome vecchio non si puo' ricostruire, e un nome che non si ricostruisce
        non e' una prova di paternita'."""
        self._catalogo(
            monkeypatch,
            ModelInfo(name="gemma4:e2b-8k", parent="gemma4:e2b", context=None),
        )
        assert da_pulire() == []

    def test_un_motore_muto_non_propone_di_cancellare_niente(self, monkeypatch):
        def rotto(*a, **k):
            raise RuntimeError("nessun motore")

        monkeypatch.setattr("src.service.catalog.model_catalog", rotto, raising=True)
        assert da_pulire() == []
