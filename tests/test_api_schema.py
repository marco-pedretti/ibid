"""A-03: il criterio, preso alla lettera.

> «Ogni stato dell'interfaccia previsto in Fase 8 e' rappresentabile nello
> schema, incluse "attendo i verdetti" e "il modello si e' astenuto".»

Questo file e' l'unico posto in cui i requisiti U-01…U-07 diventano
verificabili prima che il frontend esista. Ogni classe qui sotto porta il nome
del requisito che protegge: se un campo sparisse, il test che si rompe direbbe
**quale promessa** e' stata rotta, non quale attributo manca.

L'ordine e' quello del ROADMAP, non quello del codice: e' il ROADMAP che decide
cosa deve essere rappresentabile.
"""

from __future__ import annotations

import json

import pytest
import src.config as cfg
from src.config import RequestConfig
from src.datasets.schema import Chunk
from src.service import AnswerRequest, answer_stream
from src.service.catalog import DatasetInfo

from src.api.schema import (
    AnswerResponse,
    Capabilities,
    ChunkView,
    DatasetView,
    ErrorEvent,
    QueryRequest,
    RetrieveRequestBody,
    sse,
    to_wire,
)
from tests.test_service_answer import CLAIM, HIGH, LOW, fake_retrieve, fake_verify
from tests.test_service_stream import fake_stream


def risposta(pezzi=("Risposta ", "[1]."), scores=None, verifier=None, **config_kwargs):
    """Una `AnswerResponse` completa, senza indice e senza LLM."""
    eventi = list(answer_stream(
        AnswerRequest(query="domanda", config=RequestConfig.from_defaults(**config_kwargs)),
        client=object(),
        retrieve=fake_retrieve(HIGH if scores is None else scores),
        generate=fake_stream(*pezzi),
        verify=fake_verify() if verifier is None else verifier,
    ))
    return AnswerResponse.of(eventi[-1].answer), eventi


def payload(eventi, nome: str) -> dict:
    for e in eventi:
        n, p = to_wire(e)
        if n == nome:
            return p
    raise AssertionError(f"nessun evento {nome!r} nella sequenza")


# ---------------------------------------------------------------------------
# U-01 — selettore dataset, cambio senza riavvio
# ---------------------------------------------------------------------------


class TestU01SelettoreDataset:
    def test_i_dataset_si_leggono_dall_api(self):
        v = DatasetView.of(DatasetInfo("ledger", "ledger", True, 47110))
        assert v.model_dump() == {
            "dataset_id": "ledger", "collection": "ledger",
            "ready": True, "n_chunks": 47110,
        }

    def test_vuoto_e_assente_restano_distinti(self):
        """Un frontend che li confonde mostra un dataset interrogabile che
        risponde sempre niente."""
        vuoto = DatasetView.of(DatasetInfo("x", "x", True, 0))
        assente = DatasetView.of(DatasetInfo("x", "x", False, 0))
        assert vuoto.ready and not assente.ready

    def test_le_scelte_valide_arrivano_dal_backend(self):
        """Il frontend non deve portare una copia di `retrieval_mode`: sarebbe
        la quindicesima lista scritta a mano che Q-06 ha appena tolto."""
        c = Capabilities()
        assert c.retrieval_modes == ["dense", "sparse", "hybrid"]
        assert c.baseline_prompts == ["permissive", "strict"]
        assert c.reasoning_efforts == ["none", "low", "medium", "high", "max"]
        assert c.models == []


# ---------------------------------------------------------------------------
# U-02 — lista documenti sempre visibile
# ---------------------------------------------------------------------------


class TestU02ListaDocumenti:
    def test_i_chunk_arrivano_sempre_non_solo_il_testo(self):
        r, _ = risposta()
        assert len(r.chunks) == 5
        assert all(c.text for c in r.chunks)

    def test_ci_sono_anche_quando_il_gate_si_astiene(self):
        """«In ogni stato dell'interfaccia» comprende quello in cui non c'e'
        una risposta: astenersi non e' non aver cercato."""
        r, _ = risposta(scores=LOW)
        assert r.abstained and len(r.chunks) == 5

    def test_l_evento_chunks_precede_il_testo(self):
        _, eventi = risposta()
        nomi = [to_wire(e)[0] for e in eventi]
        assert nomi.index("chunks") < nomi.index("token")

    def test_senza_recupero_la_lista_e_vuota_ma_esiste(self):
        r, eventi = risposta(rag=False)
        assert r.chunks == []
        assert payload(eventi, "chunks") == {"chunks": []}


# ---------------------------------------------------------------------------
# U-03 / U-04 — i due bracci affiancati
# ---------------------------------------------------------------------------


class TestU03U04Bracci:
    def test_la_richiesta_accetta_il_toggle(self):
        assert QueryRequest(query="q", rag=False).config().rag is False
        assert QueryRequest(query="q").config().rag is True

    def test_la_richiesta_accetta_il_prompt_del_baseline(self):
        c = QueryRequest(query="q", rag=False, baseline_prompt="permissive").config()
        assert c.baseline_prompt == "permissive"

    def test_un_prompt_inesistente_e_rifiutato(self):
        with pytest.raises(ValueError, match="baseline_prompt"):
            QueryRequest(query="q", baseline_prompt="severo").config()

    def test_le_due_risposte_dichiarano_quale_braccio_sono(self):
        """Affiancarle senza poterle etichettare renderebbe il confronto una
        didascalia invece di un dato."""
        nuda, _ = risposta(rag=False, baseline_prompt="permissive")
        citata, _ = risposta()
        assert nuda.config.rag is False and nuda.config.baseline_prompt == "permissive"
        assert citata.config.rag is True


# ---------------------------------------------------------------------------
# U-05 — indicatore della pipeline
# ---------------------------------------------------------------------------


class TestU05Pipeline:
    def test_ogni_chunk_dice_da_quale_pipeline_viene(self):
        """E' cio' che rende **visibile** il routing, cioe' la seconda
        affermazione del §0."""
        r, _ = risposta()
        assert all(c.pipeline and c.doc_genre for c in r.chunks)

    def test_l_indicatore_c_e_anche_sullo_stream(self):
        _, eventi = risposta()
        primo = payload(eventi, "chunks")["chunks"][0]
        assert primo["pipeline"] == "continuous_text"
        assert primo["doc_genre"] == "academic_pdf"


# ---------------------------------------------------------------------------
# U-06 — link profondi
# ---------------------------------------------------------------------------


class TestU06LinkProfondi:
    def test_ogni_chunk_porta_la_fonte_e_la_pagina(self):
        r, _ = risposta()
        assert all(c.source_uri and c.page for c in r.chunks)

    def test_il_bbox_c_e_e_vale_null(self):
        """Dichiararlo assente e' diverso dal simularlo: I-06 e' rinviato e
        nessun dataset attuale porta coordinate."""
        r, _ = risposta()
        assert all(c.bbox is None for c in r.chunks)
        assert "bbox" in ChunkView.model_fields

    def test_un_chunk_letto_per_id_dice_di_non_venire_da_un_recupero(self):
        v = ChunkView.of_chunk(Chunk(
            chunk_id="ledger:X:1", dataset_id="ledger", doc_id="X", doc_genre="table_heavy",
            pipeline="pipeline_table_heavy", section_path="Note 1", page=7, bbox=None,
            content_type="table", text="t", source_uri="u",
        ))
        assert (v.marker, v.score) == (0, 0.0)


# ---------------------------------------------------------------------------
# U-07 — le non verificate marcate, non nascoste
# ---------------------------------------------------------------------------


class TestU07Verdetti:
    def test_ogni_citazione_porta_il_proprio_verdetto(self):
        r, _ = risposta(pezzi=(f"{CLAIM} ", "[1]."))
        assert len(r.citations) == 1
        assert r.citations[0].supported is True

    def test_le_bocciate_non_spariscono(self):
        """Toglierle porterebbe la precisione apparente al 100% per
        costruzione, nel punto in cui il progetto vuole essere misurato."""
        r, _ = risposta(pezzi=(f"{CLAIM} ", "[1]."),
                        verifier=fake_verify(supported=False, score=0.02))
        assert len(r.citations) == 1 and not r.citations[0].supported

    def test_una_citazione_si_lega_al_suo_chunk(self):
        """Marcare visivamente richiede di sapere **quale** riquadro marcare."""
        r, _ = risposta(pezzi=(f"{CLAIM} ", "[1]."))
        chunk_ids = {c.chunk_id for c in r.chunks}
        assert r.citations[0].chunk_id in chunk_ids


# ---------------------------------------------------------------------------
# Gli stati che §3.5 nomina esplicitamente
# ---------------------------------------------------------------------------


class TestStatiObbligatori:
    def test_attendo_i_verdetti(self):
        _, eventi = risposta(pezzi=(f"{CLAIM} ", "[1]."))
        assert payload(eventi, "answer")["verification_pending"] is True

    def test_non_aspetto_niente_se_la_verifica_e_spenta(self):
        _, eventi = risposta(pezzi=(f"{CLAIM} ", "[1]."), verify=False)
        assert payload(eventi, "answer")["verification_pending"] is False
        with pytest.raises(AssertionError):
            payload(eventi, "citations")

    def test_il_modello_si_e_astenuto(self):
        r, _ = risposta(pezzi=("I cannot answer without more information.",))
        assert r.abstained and r.abstention == "model"

    def test_il_gate_si_e_astenuto_ed_e_un_altro_stato(self):
        r, _ = risposta(scores=LOW)
        assert r.abstained and r.abstention == "retrieval"
        assert r.gate.active and r.gate.threshold is not None

    def test_il_gate_non_ha_girato_non_e_il_gate_superato(self):
        r, _ = risposta(rag=False)
        assert not r.gate.active and not r.gate.abstain

    def test_il_retrieval_non_ha_trovato_niente(self):
        r, _ = risposta(scores=[])
        assert r.chunks == []

    def test_la_risposta_e_stata_tagliata(self):
        eventi = list(answer_stream(
            AnswerRequest(query="q"), client=object(), retrieve=fake_retrieve(HIGH),
            generate=fake_stream("mezza", finish_reason="length"), verify=fake_verify(),
        ))
        assert payload(eventi, "answer")["truncated"] is True

    def test_il_testo_verra_sostituito_e_il_contratto_lo_dice(self):
        """La decisione del §3.5: i token scorrono grezzi, `answer` li
        sostituisce. Senza `repaired`, la UI non saprebbe se ha appena mostrato
        qualcosa di diverso da quello che restera'."""
        _, eventi = risposta(pezzi=("Valore ", "[1, 2]."))
        a = payload(eventi, "answer")
        assert a["raw_text"] == "Valore [1, 2]."
        assert a["text"] == "Valore [1][2]."
        assert a["repaired"] is True

    def test_il_guasto_e_uno_stato(self):
        """Quando lo stream e' cominciato, un 500 non e' piu' spedibile: gli
        header sono partiti. Un errore a meta' risposta puo' solo essere un
        evento."""
        nome, p = to_wire(ErrorEvent(message="Qdrant irraggiungibile", stage="retrieval"))
        assert nome == "error" and p["stage"] == "retrieval"


# ---------------------------------------------------------------------------
# Il confine: cosa un client NON puo' chiedere
# ---------------------------------------------------------------------------


class TestConfine:
    """La classificazione di A-02, difesa all'orlo HTTP.

    Un client non deve poter chiedere una cosa che non ha senso — e questi tre
    gruppi non hanno senso per ragioni diverse.
    """

    NOMI = set(QueryRequest.model_fields)

    def test_non_si_puo_cambiare_il_modello_di_embedding(self):
        """L'indice e' stato costruito con lui: un altro restituisce spazzatura
        **senza errore**."""
        assert not {"embedding_model", "sparse_embedding_model"} & self.NOMI

    def test_non_si_possono_spostare_i_servizi(self):
        assert not {"qdrant_url", "llm_base_url"} & self.NOMI

    def test_non_si_possono_toccare_le_soglie_calibrate(self):
        """Derivate da misure, non preferenze: chi chiama non deve poter tarare
        la soglia sulla stessa risposta che quella soglia deve giudicare."""
        assert not {
            "entailment_threshold", "abstention_thresholds", "abstention_budget",
        } & self.NOMI

    def test_i_campi_non_dati_restano_ai_default(self):
        """`None` significa «non ho un'opinione», che e' diverso da un valore:
        un client che manda solo la domanda non sta chiedendo `top_k=0`."""
        c = QueryRequest(query="q").config()
        assert c == RequestConfig.from_defaults()

    def test_una_domanda_vuota_e_rifiutata(self):
        with pytest.raises(ValueError):
            QueryRequest(query="")

    def test_una_profondita_assurda_e_rifiutata(self):
        with pytest.raises(ValueError):
            QueryRequest(query="q", top_k=0)


class TestA07Ragionamento:
    """Il toggle «Ragionamento» (A-07): si poteva vedere, non scegliere."""

    def test_la_richiesta_lo_accetta(self):
        assert QueryRequest(query="q", reasoning_effort="none").config().reasoning_effort == "none"
        assert QueryRequest(query="q", reasoning_effort="high").config().reasoning_enabled

    def test_un_livello_inventato_e_rifiutato_qui_non_dal_modello(self):
        """Ollama risponde 400 a un valore fuori elenco: rimbalzato, sarebbe un
        500 — un guasto nostro per un errore di chi chiama."""
        with pytest.raises(ValueError, match="reasoning_effort"):
            QueryRequest(query="q", reasoning_effort="altissimo")

    def test_la_stringa_vuota_non_e_un_valore_del_filo(self):
        """`reasoning_enabled` la tratta come «spento» per ragioni storiche, ma
        sul filo produrrebbe il 400 che l'elenco esiste per evitare."""
        with pytest.raises(ValueError):
            QueryRequest(query="q", reasoning_effort="")

    def test_non_chiederlo_lascia_il_default_del_deployment(self):
        assert QueryRequest(query="q").config().reasoning_effort == cfg.REASONING_EFFORT

    def test_cercare_non_lo_accetta_perche_non_genera(self):
        """Stessa regola che tiene fuori `model` e `temperature` da `/retrieve`:
        un campo che il servizio ignorerebbe non deve essere esprimibile."""
        assert "reasoning_effort" not in set(RetrieveRequestBody.model_fields)


# ---------------------------------------------------------------------------
# Il filo
# ---------------------------------------------------------------------------


class TestFormatoSSE:
    def test_ogni_evento_ha_un_nome_e_un_payload_json(self):
        _, eventi = risposta(pezzi=(f"{CLAIM} ", "[1]."))
        for e in eventi:
            nome, p = to_wire(e)
            assert nome in {"chunks", "token", "answer", "citations", "done"}
            json.dumps(p)  # deve essere serializzabile senza aiuti

    def test_i_nomi_sono_quelli_del_contratto_non_delle_classi(self):
        """Rinominare una classe non deve rompere un client."""
        _, eventi = risposta()
        assert to_wire(eventi[0])[0] == "chunks"

    def test_la_riga_vuota_chiude_l_evento(self):
        """E' il terminatore del formato: senza, il client legge l'evento
        successivo come continuazione di questo e resta in attesa."""
        _, eventi = risposta()
        testo = sse(eventi[0])
        assert testo.startswith("event: chunks\ndata: ")
        assert testo.endswith("\n\n")

    def test_il_done_non_ripete_la_risposta(self):
        """Chi streamma ha gia' ricevuto tutto: ripeterlo raddoppierebbe il
        traffico proprio sull'evento che chiude."""
        _, eventi = risposta()
        p = payload(eventi, "done")
        assert "text" not in p and "chunks" not in p
        assert "timings" in p and "config" in p

    def test_la_configurazione_torna_indietro_intera(self):
        _, eventi = risposta(top_k=2, rerank=False)
        assert payload(eventi, "done")["config"]["top_k"] == 2

    def test_un_evento_sconosciuto_non_finisce_sul_filo_in_silenzio(self):
        with pytest.raises(TypeError):
            to_wire(object())  # type: ignore[arg-type]

    def test_l_accento_non_diventa_una_sequenza_di_escape(self):
        """`ensure_ascii=False`: il payload viaggia in UTF-8, e un client che
        legge `perch\\u00e9` in un log non riesce a leggerlo."""
        _, eventi = risposta(pezzi=("perché ", "[1]."))
        assert "perché" in sse(eventi[1])
