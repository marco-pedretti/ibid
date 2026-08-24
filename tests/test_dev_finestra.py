"""A-09 — cosa dice l'avvio sulla finestra di contesto, e quando tace.

`scripts/dev.py` creava ventidue modelli derivati a ogni avvio per garantire la
finestra. Adesso la finestra la imposta il motore, e questo e' cio' che resta:
una riga, e solo quando serve. **Un avviso che compare sempre smette di essere
letto**, quindi il caso giusto deve essere silenzioso -- ed e' il caso che questi
test fissano per primo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.config as cfg  # noqa: E402
from scripts.dev import controlla_finestra  # noqa: E402


def _finestra(valore, monkeypatch):
    monkeypatch.setattr(
        "src.service.catalog.finestra_attiva", lambda *a, **k: valore, raising=True
    )


class TestControllaFinestra:
    def test_quando_e_giusta_non_dice_niente(self, monkeypatch, capsys):
        _finestra(cfg.CONTEXT_WINDOW, monkeypatch)
        controlla_finestra()
        letto = capsys.readouterr()
        assert letto.out == "" and letto.err == ""

    def test_quando_e_diversa_dice_quale(self, monkeypatch, capsys):
        """L'unico caso in cui il messaggio e' un **dato** e non un consiglio:
        la run sta girando a 4096 e nessuno lo saprebbe."""
        _finestra(4096, monkeypatch)
        controlla_finestra()
        err = capsys.readouterr().err
        assert "4096" in err
        assert f"OLLAMA_CONTEXT_LENGTH={cfg.CONTEXT_WINDOW}" in err

    def test_quando_non_si_sa_dice_dove_si_imposta(self, monkeypatch, capsys):
        """`/api/ps` elenca i modelli caricati: a un avvio, il caso normale e'
        che non ce ne sia nessuno. Non e' un allarme, e' un'indicazione."""
        _finestra(None, monkeypatch)
        controlla_finestra()
        letto = capsys.readouterr()
        assert "OLLAMA_CONTEXT_LENGTH" in letto.out
        assert letto.err == ""

    @pytest.mark.parametrize("guasto", [RuntimeError("muto"), ImportError("niente catalogo")])
    def test_un_motore_che_esplode_non_ferma_l_avvio(self, monkeypatch, capsys, guasto):
        """Senza indice non funziona niente, senza modello si sfoglia il corpus:
        e' la stessa scelta che dev.py fa gia' per l'LLM spento."""

        def rotto(*a, **k):
            raise guasto

        monkeypatch.setattr("src.service.catalog.finestra_attiva", rotto, raising=True)
        controlla_finestra()
        assert "OLLAMA_CONTEXT_LENGTH" in capsys.readouterr().out
