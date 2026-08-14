"""A-03: la pipeline vista come sequenza di eventi (§3.5).

Il criterio di A-03 e' che **ogni stato dell'interfaccia previsto in Fase 8 sia
rappresentabile**. Rappresentabile non vuol dire "c'e' un campo": vuol dire che
chi consuma lo stream puo' distinguerlo dagli altri senza indovinare. Questi
test controllano proprio quello — che due situazioni diverse producano sequenze
diverse, e che nessuna richieda di dedurre qualcosa dal silenzio.
"""

from __future__ import annotations

import sys

import pytest
from src.config import RequestConfig
from src.generation.chat import Delta
from src.generation.prompt import ABSTENTION_ANSWER
from src.service import (
    AnswerEvent,
    AnswerRequest,
    ChunksEvent,
    CitationsEvent,
    DoneEvent,
    TokenEvent,
    answer,
    answer_stream,
)
from tests.test_service_answer import CLAIM, HIGH, LOW, fake_retrieve, fake_verify


def fake_stream(*pezzi: str, finish_reason: str = "stop", tokens: int = 12):
    """Un generatore che consegna i pezzi che il test decide."""
    calls: list[dict] = []

    def _generate(**kwargs):
        calls.append(kwargs)
        for p in pezzi:
            yield Delta(text=p)
        yield Delta(final=True, finish_reason=finish_reason, completion_tokens=tokens)

    _generate.calls = calls
    return _generate


def eventi(pezzi=("Risposta ", "[1]."), scores=None, verifier=None, **config_kwargs):
    return list(answer_stream(
        AnswerRequest(query="domanda", config=RequestConfig.from_defaults(**config_kwargs)),
        client=object(),
        retrieve=fake_retrieve(HIGH if scores is None else scores),
        generate=fake_stream(*pezzi),
        verify=fake_verify() if verifier is None else verifier,
    ))


def tipi(evs) -> list[str]:
    return [type(e).__name__ for e in evs]


class TestOrdine:
    def test_le_fonti_arrivano_prima_del_testo(self):
        """E' cio' che rende realizzabile U-02: la lista documenti compare
        mentre il modello sta ancora scrivendo. Se arrivasse dopo, la
        'lista sempre visibile' sarebbe visibile solo alla fine."""
        seq = tipi(eventi())
        assert seq.index("ChunksEvent") < seq.index("TokenEvent")
        assert seq.index("TokenEvent") < seq.index("AnswerEvent")

    def test_i_verdetti_arrivano_dopo_il_testo(self):
        """Non e' una scelta: `verify_answer` prende la risposta **completa**.
        E' posteriore alla generazione per costruzione."""
        seq = tipi(eventi(pezzi=(f"{CLAIM} ", "[1].")))
        assert seq.index("AnswerEvent") < seq.index("CitationsEvent")

    def test_finisce_sempre_con_done(self):
        for kwargs in ({}, {"scores": LOW}, {"rag": False}, {"verify": False}):
            assert tipi(eventi(**kwargs))[-1] == "DoneEvent", kwargs

    def test_done_arriva_anche_quando_il_gate_ferma_tutto(self):
        """Chi consuma aspetta `DoneEvent` e non deve dedurre la fine dal
        silenzio: una connessione che tace e una risposta finita si
        assomigliano troppo."""
        seq = tipi(eventi(scores=LOW))
        assert "TokenEvent" not in seq
        assert seq[-1] == "DoneEvent"


class TestStatiDisegnabili:
    """Ogni riga qui e' uno stato che §3.5 nomina come obbligatorio."""

    def test_attendo_i_verdetti(self):
        """Il testo c'e', i marcatori ci sono, i verdetti no.

        Senza questo campo la UI dovrebbe indovinare se aspettare: indovinare
        sbagliato significa o un caricamento eterno, o dichiarare verificata una
        citazione che nessuno ha guardato.
        """
        evs = eventi(pezzi=(f"{CLAIM} ", "[1]."))
        risposta = next(e for e in evs if isinstance(e, AnswerEvent))
        assert risposta.verification_pending
        assert any(isinstance(e, CitationsEvent) for e in evs)

    def test_non_attendo_niente_se_la_verifica_e_spenta(self):
        evs = eventi(pezzi=(f"{CLAIM} ", "[1]."), verify=False)
        risposta = next(e for e in evs if isinstance(e, AnswerEvent))
        assert not risposta.verification_pending
        assert not any(isinstance(e, CitationsEvent) for e in evs)

    def test_il_modello_si_e_astenuto(self):
        evs = eventi(pezzi=(ABSTENTION_ANSWER,))
        risposta = next(e for e in evs if isinstance(e, AnswerEvent))
        assert risposta.abstained and risposta.abstention == "model"
        assert not risposta.verification_pending

    def test_il_gate_si_e_astenuto_e_non_e_la_stessa_cosa(self):
        evs = eventi(scores=LOW)
        risposta = next(e for e in evs if isinstance(e, AnswerEvent))
        assert risposta.abstained and risposta.abstention == "retrieval"

    def test_il_recupero_non_ha_trovato_niente(self):
        """§3.5 lo nomina esplicitamente. `chunks: []` con l'evento presente e'
        diverso dall'evento che non arriva: il primo dice «ho cercato», il
        secondo non dice niente."""
        evs = eventi(scores=[])
        fonti = next(e for e in evs if isinstance(e, ChunksEvent))
        assert fonti.chunks == []
        assert tipi(evs)[-1] == "DoneEvent"

    def test_la_risposta_e_stata_tagliata(self):
        evs = list(answer_stream(
            AnswerRequest(query="q"),
            client=object(),
            retrieve=fake_retrieve(HIGH),
            generate=fake_stream("mezza frase", finish_reason="length"),
            verify=fake_verify(),
        ))
        assert next(e for e in evs if isinstance(e, AnswerEvent)).truncated

    def test_senza_recupero_le_fonti_sono_vuote_ma_l_evento_c_e(self):
        """U-02 vuole la lista documenti in **ogni** stato dell'interfaccia.
        Vuota è uno stato; assente è un buco nel contratto."""
        evs = eventi(rag=False)
        assert isinstance(evs[0], ChunksEvent)
        assert evs[0].chunks == []


class TestTestoProvvisorio:
    """La decisione di §3.5 sul testo grezzo contro quello riparato."""

    def test_i_token_sono_quelli_grezzi(self):
        evs = eventi(pezzi=("Valore ", "[1, 2]."))
        assert "".join(e.text for e in evs if isinstance(e, TokenEvent)) == "Valore [1, 2]."

    def test_l_evento_answer_porta_il_testo_riparato_e_lo_dichiara(self):
        """Il contratto dice che il testo va **sostituito**, non integrato. Chi
        consuma deve sapere che ciò che ha mostrato non è definitivo."""
        risposta = next(e for e in eventi(pezzi=("Valore ", "[1, 2].")) if isinstance(e, AnswerEvent))
        assert risposta.raw_text == "Valore [1, 2]."
        assert risposta.text == "Valore [1][2]."
        assert risposta.repaired

    def test_quando_non_ripara_lo_dice_lo_stesso(self):
        risposta = next(e for e in eventi(pezzi=("Valore [1][2].",)) if isinstance(e, AnswerEvent))
        assert not risposta.repaired
        assert risposta.text == risposta.raw_text


class TestUnaSolaPipeline:
    """`answer()` e' una vista sullo stream, non una seconda implementazione.

    E' il difetto che A-01 ha tolto da `scripts/query.py`, e che qui sarebbe
    rientrato dalla finestra: due copie della stessa sequenza partono identiche
    e poi divergono, nel punto in cui nessuno guarda.
    """

    def test_done_porta_la_risposta_intera(self):
        fine = eventi()[-1]
        assert isinstance(fine, DoneEvent)
        assert fine.answer.text == "Risposta [1]."

    def test_le_due_strade_danno_la_stessa_risposta(self):
        pezzi = ("Il valore ", "massimo e' 400ms ", "[1, 2].")
        da_stream = eventi(pezzi=pezzi)[-1].answer

        # La stessa richiesta dalla strada non-streaming: `generate` restituisce
        # una Completion invece dei Delta, ed e' l'unica differenza.
        from src.generation.chat import Completion

        def generate_intero(**kwargs):
            return Completion(content="".join(pezzi), finish_reason="stop", completion_tokens=12)

        da_intero = answer(
            AnswerRequest(query="domanda"),
            client=object(),
            retrieve=fake_retrieve(HIGH),
            generate=generate_intero,
            verify=fake_verify(),
        )
        for campo in ("text", "raw_text", "repaired", "cited", "abstained", "truncated"):
            assert getattr(da_stream, campo) == getattr(da_intero, campo), campo

    def test_i_token_ricomposti_sono_il_testo_grezzo(self):
        """Se questi due divergessero, la verifica girerebbe su una risposta
        diversa da quella che l'utente ha letto."""
        evs = eventi(pezzi=("Uno ", "due ", "tre [1]."))
        ricomposto = "".join(e.text for e in evs if isinstance(e, TokenEvent))
        assert ricomposto.strip() == evs[-1].answer.raw_text


def test_uno_stream_senza_done_e_un_errore_di_programmazione(monkeypatch):
    """`answer()` non deve poter restituire `None` in silenzio.

    Il modulo si raggiunge da `sys.modules` e non con `import`: il pacchetto
    riesporta la funzione `answer`, quindi `src.service.answer` come *attributo*
    e' la funzione e non il modulo omonimo.
    """
    def stream_monco(*a, **kw):
        yield ChunksEvent(chunks=[])

    modulo = sys.modules["src.service.answer"]
    monkeypatch.setattr(modulo, "answer_stream", stream_monco)
    with pytest.raises(RuntimeError, match="DoneEvent"):
        modulo.answer(AnswerRequest(query="q"), client=object())
