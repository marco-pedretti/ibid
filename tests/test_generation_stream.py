"""A-03: la generazione a pezzi, e perche' non poteva essere finta.

§3.5 prevede SSE. Senza una generazione che arriva davvero a pezzi, l'unico
streaming possibile sarebbe aspettare la risposta intera e poi spezzettarla:
identico dal lato del browser, e falso — la prima parola arriverebbe **dopo**
l'ultima, cioe' dopo gli ~11 s che il progetto misura come latenza.

Qui non si parla con nessun modello. Si verifica che il formato del flusso sia
letto come si deve, che i casi limite del protocollo non facciano perdere testo,
e che la somma dei pezzi sia la stessa risposta della strada non-streaming.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from src.generation.chat import Completion, Delta, collect, generate_stream


class FakeResponse:
    """Cio' che `urlopen` restituisce: un iterabile di righe di byte."""

    def __init__(self, righe: list[bytes]):
        self._righe = righe

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        return iter(self._righe)


def sse(*eventi: dict, done: bool = True) -> list[bytes]:
    righe = [b"data: " + json.dumps(e).encode() + b"\n" for e in eventi]
    if done:
        righe.append(b"data: [DONE]\n")
    return righe


def delta(text: str) -> dict:
    return {"choices": [{"delta": {"content": text}, "finish_reason": None}]}


def fine(reason: str = "stop") -> dict:
    return {"choices": [{"delta": {}, "finish_reason": reason}]}


def uso(tokens: int) -> dict:
    return {"choices": [], "usage": {"completion_tokens": tokens}}


def stream(righe: list[bytes]) -> list[Delta]:
    with patch("urllib.request.urlopen", return_value=FakeResponse(righe)):
        return list(generate_stream("http://x/v1", "m", "sys", "user"))


class TestFormato:
    def test_i_pezzi_arrivano_nell_ordine(self):
        d = stream(sse(delta("Il "), delta("valore "), delta("sale."), fine(), uso(9)))
        assert [x.text for x in d if not x.final] == ["Il ", "valore ", "sale."]

    def test_l_ultimo_porta_il_verdetto_e_nessun_testo(self):
        d = stream(sse(delta("ciao"), fine("length"), uso(3)))
        ultimo = d[-1]
        assert ultimo.final and ultimo.text == ""
        assert ultimo.finish_reason == "length"
        assert ultimo.completion_tokens == 3

    def test_c_e_sempre_un_finale_anche_se_il_modello_non_dice_niente(self):
        """Chi consuma scorre fino a `final`. Se il finale non arrivasse, un
        consumatore corretto resterebbe in attesa di uno stato che non c'e'."""
        d = stream(sse())
        assert len(d) == 1 and d[0].final

    def test_il_conteggio_assente_resta_zero(self):
        """Dichiarato assente, non stimato: un numero inventato in un campo che
        si chiama `completion_tokens` verrebbe letto come una misura."""
        d = stream(sse(delta("x"), fine()))
        assert d[-1].completion_tokens == 0


class TestCasiLimite:
    def test_le_righe_vuote_non_contano(self):
        """Il formato SSE le usa come separatore fra eventi."""
        righe = sse(delta("a"), delta("b"), fine())
        righe = [r for coppia in ((x, b"\n") for x in righe) for r in coppia]
        d = stream(righe)
        assert [x.text for x in d if not x.final] == ["a", "b"]

    def test_un_delta_senza_contenuto_non_diventa_un_pezzo_vuoto(self):
        """Il primo pacchetto di molti backend porta solo il ruolo. Emetterlo
        come token darebbe alla UI un aggiornamento che non aggiunge niente."""
        vuoto = {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]}
        d = stream(sse(vuoto, delta("a"), fine()))
        assert [x.text for x in d if not x.final] == ["a"]

    def test_niente_si_ferma_su_done(self):
        """Cio' che segue `[DONE]` non e' piu' risposta."""
        righe = sse(delta("a"), fine()) + [b"data: " + json.dumps(delta("b")).encode() + b"\n"]
        d = stream(righe)
        assert [x.text for x in d if not x.final] == ["a"]

    def test_il_json_malformato_non_passa_in_silenzio(self):
        """Un pezzo illeggibile e' testo perso. Passarci sopra darebbe una
        risposta con un buco in mezzo e nessun segnale."""
        with pytest.raises(json.JSONDecodeError):
            stream([b"data: {non json}\n"])


class TestCollect:
    def test_la_somma_dei_pezzi_e_una_completion(self):
        d = stream(sse(delta("Il "), delta("valore.\n"), fine(), uso(4)))
        assert collect(iter(d)) == Completion(
            content="Il valore.", finish_reason="stop", completion_tokens=4
        )

    def test_lo_streaming_e_il_non_streaming_danno_lo_stesso_testo(self):
        """Le due strade devono coincidere, o la risposta che l'utente vede
        dipende da come e' stata chiesta.

        E' l'unico modo per accorgersi che lo streaming perde un pezzo: un
        difetto che dal lato del browser si vede come una frase che comincia a
        meta', e che nessun test sul solo streaming troverebbe.
        """
        testo = "Il valore massimo e' 400ms [2][3]. Il modello supera il baseline [1]."
        pezzi = [testo[i:i + 7] for i in range(0, len(testo), 7)]
        a_pezzi = collect(iter(stream(sse(*[delta(p) for p in pezzi], fine(), uso(21)))))

        risposta = {
            "choices": [{"message": {"content": testo}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 21},
        }
        with patch("urllib.request.urlopen") as fake:
            fake.return_value.__enter__.return_value.read.return_value = json.dumps(risposta)
            from src.generation.chat import generate_detailed
            intera = generate_detailed("http://x/v1", "m", "sys", "user")

        assert a_pezzi == intera

    def test_uno_stream_vuoto_non_e_un_errore(self):
        """Il modello puo' non produrre niente — succede con il budget di token
        speso tutto in ragionamento (C-01). E' una risposta vuota, non un guasto."""
        assert collect(iter(stream(sse(fine("length"))))).content == ""
