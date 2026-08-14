"""Il gate di A-02, catturato prima della prima riga: gli hash non si muovono.

Un `config_hash` e' **il nome di una misura**. Due run che lo condividono sono
dichiarate direttamente confrontabili; due che non lo condividono, no. Se un
refactor lo cambia, ogni run archiviata smette di essere paragonabile a quelle
nuove — e lo fa in silenzio, perche' nessun numero si muove: cambia solo il nome
sotto cui e' registrato.

Questi test non guardano il codice: guardano **i file su disco**. Ogni run
elencata qui viene riletta, i suoi argomenti ricostruiti dalla sua stessa
configurazione registrata, e l'hash ricalcolato. Deve tornare il proprio nome.

Il file nasce con A-02, che sposta la configurazione di richiesta fuori da `cfg`
globale. E' esattamente il tipo di modifica che potrebbe rinominare una misura
senza accorgersene.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.eval.citation_harness import _config_hash as citation_config_hash
from src.eval.citation_harness import prompt_hash, user_template_hash
from src.eval.harness import _config_hash as retrieval_config_hash
from src.generation.prompt import SYSTEM

RESULTS = Path(__file__).parent.parent / "eval" / "results"

#: Run di retrieval le cui identita' devono restare riproducibili. Una per
#: combinazione di flag effettivamente misurata: se ne manca una, quel percorso
#: dell'hash non e' coperto.
ANCORE_RETRIEVAL = (
    "20260807_102619_open_ragbench_generic_dense.json",          # dense
    "20260807_102851_open_ragbench_generic_dense-rerank.json",   # dense + rerank
    "20260813_080631_open_ragbench_generic_sparse.json",         # sparse (R-08/R-09)
    "20260813_080710_open_ragbench_generic_hybrid.json",         # hybrid
    "20260813_081100_open_ragbench_generic_hybrid-rerank.json",  # hybrid + rerank
    "20260807_103632_ledger_routed_dense.json",                  # routed, collection diversa
)

#: Una run di C-01. Separata perche' il suo hash dipende dal prompt, che e'
#: proprio cio' che quel task misura.
ANCORA_CITAZIONI = "20260812_170338_open_ragbench_citations.json"


def load(name: str) -> dict:
    path = RESULTS / name
    if not path.exists():
        pytest.skip(f"run di riferimento assente: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", ANCORE_RETRIEVAL)
def test_una_run_archiviata_hasha_ancora_al_proprio_nome(name):
    """Ricostruito dagli argomenti che la run stessa dichiara di aver usato.

    Non da costanti scritte qui: se il test portasse i propri valori,
    verificherebbe la funzione contro se stessa invece che contro cio' che e'
    stato davvero misurato.
    """
    run = load(name)
    c = run["config"]
    ricalcolato = retrieval_config_hash(
        c["top_k"],
        run["pipeline_mode"],
        c["retrieval_mode"],
        rerank=c["rerank"],
        query_rewrite=c["query_rewrite"],
        filter_content_type=c["filter_content_type"],
        doc_aggregate=c.get("doc_aggregate", False),
        collection=c["collection"],
        dataset_id=run["dataset_id"],
        eval_depth=c["eval_depth"],
    )
    assert ricalcolato == run["config_hash"], (
        f"{name}: registrata come {run['config_hash']}, oggi si chiamerebbe "
        f"{ricalcolato}. Il refactor ha rinominato una misura."
    )


def test_la_run_di_c01_hasha_ancora_al_proprio_nome():
    """Con una condizione: che il prompt sia ancora quello.

    L'hash di C-01 include il prompt, di proposito — riscriverlo e rimisurare
    deve produrre due identita' diverse. Quindi il controllo vale solo finche'
    il prompt non e' cambiato, e quando cambiera' questo test dovra' saltare da
    solo invece di fallire dicendo la cosa sbagliata.
    """
    run = load(ANCORA_CITAZIONI)
    c = run["config"]
    if c.get("prompt_hash") != prompt_hash(SYSTEM):
        pytest.skip("il prompt di sistema e' cambiato: l'hash deve cambiare con lui")
    if c.get("user_template_hash") != user_template_hash():
        pytest.skip("il template del messaggio utente e' cambiato")

    ricalcolato = citation_config_hash(
        c["top_k"], c["retrieval_mode"], c["collection"], run["model"], SYSTEM
    )
    assert ricalcolato == run["config_hash"]


def test_le_ancore_coprono_ogni_ramo_dell_hash():
    """Un elenco di ancore che non tocca un ramo non lo protegge.

    I rami sono: le tre modalita' di retrieval, il reranker, e la collection
    diversa dal dataset. `query_rewrite` e `filter_content_type` non hanno una
    run su disco — dichiarato qui invece di sembrare coperto.
    """
    modalita = set()
    con_rerank = False
    con_collection_diversa = False
    for name in ANCORE_RETRIEVAL:
        run = load(name)
        c = run["config"]
        modalita.add(c["retrieval_mode"])
        con_rerank |= bool(c["rerank"])
        con_collection_diversa |= c["collection"] != run["dataset_id"]

    assert modalita == {"dense", "sparse", "hybrid"}
    assert con_rerank
    assert con_collection_diversa
