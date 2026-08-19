"""La scala delle finestre di U-16: cosa si legge dal motore e cosa no."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.model_sizes import PIOLI, nome_taglia, scala_per  # noqa: E402


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
        assert nome_taglia("gemma4:latest", 8192) == "gemma4:latest-8k"
        assert nome_taglia("gemma4:latest", 131072) == "gemma4:latest-128k"

    def test_una_taglia_non_tonda_tiene_il_numero(self):
        """Il suffisso serve a chi legge `ollama list`: `-40960` e' brutto e
        inequivocabile, `-40k` sarebbe sbagliato."""
        assert nome_taglia("m", 40960) == "m-40k"
        assert nome_taglia("m", 100000) == "m-100000"
