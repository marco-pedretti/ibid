"""Cosa vale per tutta la suite.

**Un test non parla col motore acceso su questa macchina.** Ovunque serva un
servizio, i moduli lo prendono per parametro — `fetch`, `dettagli`, un client
Qdrant — e i test ne passano uno finto. C'e' un solo punto in cui quella regola
non poteva valere: da A-09 gli harness chiedono a `/api/ps` con che finestra ha
girato il modello, e lo fanno **dentro** la costruzione del risultato, dove non
passa nessun parametro iniettabile.

Il costo era misurato: 47 s di suite diventavano **184**, perche' su Windows una
connessione a `localhost` che deve ripiegare da IPv6 a IPv4 costa ~2 s, e ogni
harness ne fa una. Peggio del tempo, pero', era la dipendenza: l'esito di
`test_generation_baseline` avrebbe cominciato a dipendere da quale modello era
caricato in quel momento sulla macchina di chi lanciava i test.

Quindi il default e' **«il motore non risponde»**, che e' anche la condizione di
chiunque non usi Ollama. I casi che guardano la lettura della finestra
sovrascrivono questa fixture, e sono in `test_service_model_catalog.py` e
`test_eval_run_factory.py`.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def motore_senza_finestra(monkeypatch):
    monkeypatch.setattr(
        "src.service.catalog.finestra_attiva", lambda *a, **k: None, raising=True
    )
