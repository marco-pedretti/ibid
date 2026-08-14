"""A-01: il caso d'uso «domanda → risposta citata», senza indice e senza LLM.

I due lati costosi sono iniettati. Non e' una comodita' di test: e' la stessa
scelta di `verify_answer(verifier=...)`, e serve a poter affermare qualcosa sulla
sequenza — gate prima della generazione, marcatori allineati al prompt — senza
che l'affermazione dipenda da cosa un modello ha risposto quel giorno.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import src.config as cfg
from src.retrieval.backends import Candidates
from src.generation.chat import Completion
from src.generation.entailment import Verdict
from src.generation.prompt import ABSTENTION_ANSWER
from src.service import AnswerRequest, answer

ROOT = Path(__file__).parent.parent


def payload(chunk_id: str, text: str = "testo", doc_id: str = "doc") -> dict:
    return {
        "chunk_id": chunk_id,
        "dataset_id": "open_ragbench",
        "doc_id": doc_id,
        "doc_genre": "academic_pdf",
        "pipeline": "continuous_text",
        "section_path": "1. Intro",
        "content_type": "text",
        "text": text,
        "page": 3,
        "source_uri": f"https://example.org/{doc_id}",
    }


def fake_retrieve(scores: list[float], n: int | None = None):
    """Un retriever che restituisce punteggi decisi dal test."""
    n = len(scores) if n is None else n
    calls: list[tuple] = []

    def _retrieve(client, collection, texts, fetch_k, filters):
        calls.append((collection, tuple(texts), fetch_k, filters))
        return [Candidates(
            chunk_ids=[f"c{i}" for i in range(n)],
            scores=scores,
            payloads=[payload(f"c{i}", text=f"testo {i}") for i in range(n)],
        )]

    _retrieve.calls = calls
    return _retrieve


def fake_generate(content: str, finish_reason: str = "stop", tokens: int = 42):
    calls: list[dict] = []

    def _generate(**kwargs):
        calls.append(kwargs)
        return Completion(content=content, finish_reason=finish_reason, completion_tokens=tokens)

    _generate.calls = calls
    return _generate


def fake_verify(supported: bool = True, score: float = 0.9):
    """Un verificatore che non carica niente e decide sempre allo stesso modo."""
    calls: list[tuple[str, str]] = []

    def _verify(premise: str, claim: str) -> Verdict:
        calls.append((premise, claim))
        return Verdict(supported=supported, score=score, n_premises=1)

    _verify.calls = calls
    return _verify


HIGH = [0.95, 0.94, 0.93, 0.92, 0.91]  # sopra la soglia open_ragbench (0.7924)
LOW = [0.10, 0.09, 0.08, 0.07, 0.06]   # sotto

#: Una frase lunga abbastanza da essere verificabile (MIN_CLAIM_CHARS = 30).
CLAIM = "Il valore massimo misurato e' di quattrocento millisecondi"


def run(query="domanda", scores=None, content="Risposta [1].", verifier=None, **request_kwargs):
    gen = fake_generate(content)
    ret = fake_retrieve(HIGH if scores is None else scores)
    ver = fake_verify() if verifier is None else verifier
    result = answer(
        AnswerRequest(query=query, **request_kwargs),
        client=object(),
        retrieve=ret,
        generate=gen,
        verify=ver,
    )
    return result, ret, gen


# --- la sequenza -----------------------------------------------------------


def test_gate_blocca_prima_di_generare():
    """C-04 preso alla lettera: sotto soglia il modello non viene mai chiamato.

    E' la ragione per cui il gate esiste. Se scattasse dopo, risparmierebbe
    zero secondi di GPU e sarebbe un filtro su una risposta gia' inventata.
    """
    result, _, gen = run(scores=LOW)
    assert result.abstained
    assert result.abstention == "retrieval"
    assert gen.calls == []
    assert result.text == ABSTENTION_ANSWER


def test_astensione_del_gate_e_del_modello_sono_stati_distinti():
    """Due eventi diversi, e la UI deve poterli distinguere (§3.5)."""
    da_gate, _, _ = run(scores=LOW)
    da_modello, _, _ = run(content=ABSTENTION_ANSWER)
    assert da_gate.abstained and da_modello.abstained
    assert da_gate.abstention == "retrieval"
    assert da_modello.abstention == "model"


def test_astensione_del_gate_riporta_comunque_i_chunk():
    """Astenersi non e' non aver cercato: U-02 vuole le fonti in ogni caso."""
    result, _, _ = run(scores=LOW)
    assert len(result.chunks) == 5
    assert result.gate.active and result.gate.threshold is not None


def test_gate_non_calibrato_non_e_gate_superato():
    """Su una collection senza soglia il gate e' inattivo, non permissivo."""
    result, _, gen = run(scores=LOW, dataset_id="open_ragbench", collection="ledger_routed")
    assert not result.gate.active
    assert not result.abstained
    assert len(gen.calls) == 1


# --- i marcatori -----------------------------------------------------------


def test_i_marcatori_sono_1_based_e_seguono_l_ordine_del_prompt():
    result, _, gen = run()
    assert [c.marker for c in result.chunks] == [1, 2, 3, 4, 5]
    prompt = gen.calls[0]["user"]
    # Il chunk marcato [2] e' il secondo che compare nel messaggio utente.
    ordine = [m.group(1) for m in re.finditer(r"testo (\d)", prompt)]
    assert ordine == ["0", "1", "2", "3", "4"]
    assert result.chunks[1].chunk.text == "testo 1"


def test_citati_e_non_citati_partizionano_i_chunk():
    result, _, _ = run(content="Prima [1]. Seconda [3].")
    assert result.cited == [1, 3]
    assert result.uncited == [2, 4, 5]


def test_marcatore_fuori_contesto_scartato_e_dichiarato_riparato():
    """`[9]` non esiste fra 5 chunk: sparisce, e `repaired` lo dice."""
    result, _, _ = run(content="Affermazione [9].")
    assert "[9]" not in result.text
    assert result.repaired
    assert result.cited == []


def test_il_testo_grezzo_non_va_perso():
    """E' cio' che C-01 misura: la riparazione non deve cancellare la prova."""
    result, _, _ = run(content="Valore [1, 2].")
    assert result.raw_text == "Valore [1, 2]."
    assert result.text == "Valore [1][2]."
    assert result.repaired


def test_risposta_gia_conforme_non_risulta_riparata():
    result, _, _ = run(content="Valore [1][2].")
    assert not result.repaired
    assert result.raw_text == result.text


# --- parametri della richiesta ---------------------------------------------


def test_collection_default_al_dataset():
    result, ret, _ = run(dataset_id="ledger")
    assert result.collection == "ledger"
    assert ret.calls[0][0] == "ledger"


def test_collection_esplicita_vince():
    result, ret, _ = run(dataset_id="ledger", collection="ledger_routed")
    assert result.collection == "ledger_routed"
    assert ret.calls[0][0] == "ledger_routed"


def test_top_k_taglia_il_contesto():
    result, ret, _ = run(top_k=2)
    assert len(result.chunks) == 2
    assert ret.calls[0][2] == 2


def test_top_k_assente_prende_il_default_di_config():
    _, ret, _ = run()
    assert ret.calls[0][2] == cfg.TOP_K


def test_modello_esplicito_arriva_alla_generazione():
    _, _, gen = run(model="gemma4:12b")
    assert gen.calls[0]["model"] == "gemma4:12b"


def test_modalita_di_retrieval_sconosciuta_fallisce_subito():
    with pytest.raises(KeyError):
        answer(AnswerRequest(query="q", retrieval_mode="magica"), client=object())


# --- stati che la UI deve poter disegnare (§3.5) ---------------------------


def test_troncamento_riportato():
    gen = fake_generate("Risposta senza fine", finish_reason="length")
    result = answer(
        AnswerRequest(query="q"), client=object(), retrieve=fake_retrieve(HIGH), generate=gen
    )
    assert result.truncated


def test_i_tempi_sono_sempre_presenti():
    completa, _, _ = run(content=f"{CLAIM} [1].")
    astenuta, _, _ = run(scores=LOW)
    assert {"retrieval_s", "generation_s", "verification_s", "total_s"} <= set(completa.timings)
    # Nell'astensione non c'e' generazione: il campo manca invece di valere 0,
    # che si leggerebbe come "istantanea".
    assert "generation_s" not in astenuta.timings
    assert "total_s" in astenuta.timings


# --- verifica delle citazioni (C-03, U-07) ---------------------------------


def test_ogni_citazione_porta_il_proprio_verdetto():
    result, _, _ = run(content=f"{CLAIM} [1]. {CLAIM} ancora [2].")
    assert result.verified
    assert [c.marker for c in result.citations] == [1, 2]
    assert [c.chunk_id for c in result.citations] == ["c0", "c1"]
    assert all(c.supported for c in result.citations)


def test_le_citazioni_bocciate_non_vengono_filtrate():
    """U-07 alla lettera: marcate, non nascoste.

    Toglierle farebbe salire la precisione apparente al 100% per costruzione,
    nascondendo esattamente cio' che il progetto esiste per misurare.
    """
    result, _, _ = run(content=f"{CLAIM} [1].", verifier=fake_verify(supported=False, score=0.02))
    assert len(result.citations) == 1
    assert not result.citations[0].supported
    assert result.citations[0].score == pytest.approx(0.02)


def test_il_verificatore_riceve_il_chunk_citato_e_la_frase_senza_marcatori():
    ver = fake_verify()
    run(content=f"{CLAIM} [2].", verifier=ver)
    (premessa, claim), = ver.calls
    assert premessa == "testo 1"        # il chunk con marker 2
    assert "[2]" not in claim


def test_le_affermazioni_senza_citazione_sono_riportate():
    """Il denominatore nascosto: la precisione si alza citando di meno."""
    result, _, _ = run(content=f"{CLAIM} [1]. {CLAIM} senza fonte.")
    assert len(result.citations) == 1
    assert len(result.uncited_claims) == 1
    assert "senza fonte" in result.uncited_claims[0]


def test_verifica_spenta_non_e_verifica_vuota():
    """Due stati diversi: «nessun verdetto» e «verificata, zero citazioni»."""
    spenta, _, _ = run(content=f"{CLAIM} [1].", verify=False)
    assert not spenta.verified
    assert spenta.citations == []

    accesa, _, _ = run(content="Risposta senza citazioni ne' frasi lunghe.")
    assert accesa.verified
    assert accesa.citations == []


def test_verifica_saltata_quando_il_modello_si_astiene():
    """Non c'e' niente da verificare, e la risposta e' comunque definitiva."""
    ver = fake_verify()
    result, _, _ = run(content=ABSTENTION_ANSWER, verifier=ver)
    assert ver.calls == []
    assert result.verified
    assert "verification_s" not in result.timings


def test_verifica_saltata_quando_il_gate_ferma_tutto():
    ver = fake_verify()
    result, _, _ = run(scores=LOW, verifier=ver)
    assert ver.calls == []
    assert result.verified and result.citations == []


# --- il confine (criterio di A-01) -----------------------------------------


PIPELINE_MODULES = (
    "src.index.embed",
    "src.index.store",
    "src.retrieval",
    "src.generation",
    "src.retrieval.backends",
)


def test_il_cli_non_contiene_piu_logica_di_pipeline():
    """Il criterio di A-01, applicato al consumatore che esisteva gia'.

    «Nessun endpoint contiene logica di pipeline» non significa niente se
    l'altro consumatore la contiene: non ci sarebbe niente da confrontare. Il
    CLI puo' importare `src.service` e la configurazione, non i pezzi.
    """
    source = (ROOT / "scripts" / "query.py").read_text(encoding="utf-8")
    trovati = [m for m in PIPELINE_MODULES if re.search(rf"^from {re.escape(m)}", source, re.M)]
    assert trovati == [], f"scripts/query.py importa di nuovo la pipeline: {trovati}"


def test_il_servizio_non_stampa():
    """Un caso d'uso che stampa non e' riusabile da un server.

    Il retrieval condiviso con gli harness stampa ancora il suo avanzamento —
    quello e' rumore di log e va tolto da A-04 — ma il servizio no.
    """
    source = (ROOT / "src" / "service" / "answer.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s+print\(", source, re.M)
