"""Structured description of a retrieval evaluation configuration.

Why this exists: before this module, every retrieval flag (rerank, query rewrite,
metadata filter, doc aggregation, collection override) was squashed into the
`EvalRun.pipeline_mode` string — producing values like "generic_filtered_text"
and "routed_docagg".  That broke the ROADMAP §3.3 contract, which defines
`pipeline_mode` as the binary routing axis ("generic" | "routed"), and made it
impossible to answer "show me every routed run" or "which two runs differ by
exactly one flag" (ROADMAP §15: never measure two changes at once).

`build_config()` returns the flags as data.  `EvalRun.config` carries it.

`config_hash` is deliberately NOT computed from this dict — see `_config_hash`
in `harness.py`.  Changing the hash function would make already-measured runs
non-comparable, which ROADMAP §3 forbids after Fase 2.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import src.config as cfg
from src.datasets.schema import EvalRun

def reasoning_enabled() -> bool:
    """Il modello sta ragionando? Dedotto dalla configurazione, mai asserito.

    Scritto a mano come `False` questo campo era una **dichiarazione che nessuno
    verificava**, e per un periodo e' stata falsa in ogni run: il modello
    ragionava attraverso l'intero budget di token mentre il risultato diceva di
    no (C-01). La deduzione stava poi in quattro copie identiche, che e' il modo
    in cui una quinta copia nasce sbagliata.
    """
    return cfg.REASONING_EFFORT not in ("none", "", None)


def finestra_registrata(llm: str) -> int:
    """La finestra con cui la run ha **davvero** girato (A-09).

    Era `cfg.CONTEXT_WINDOW`, cioe' la costante 32768, e D-14 aveva registrato
    il difetto: *«oggi il numero e' vero perche' il default di questo modello
    coincide, ma e' una coincidenza, non una misura»*. Il contratto OpenAI non
    ha un campo per la finestra ne' in richiesta ne' in risposta (A-08), quindi
    l'unico posto dove quel numero esiste e' `/api/ps` -- e da li' si legge.

    **E' la stessa classe di difetto di `reasoning_enabled`**, un campo piu' in
    su: una dichiarazione che nessuno verificava, e per un periodo falsa in ogni
    run. Qui il rischio era peggiore che cosmetico: senza
    `OLLAMA_CONTEXT_LENGTH` Ollama sceglie da se' fra 4k, 32k e 256k in base
    alla memoria, quindi su un'altra macchina cinque chunk non entrerebbero nel
    contesto mentre il risultato continuerebbe a dichiarare 32768.

    **La chiama chi ha appena fatto girare il modello**, e non la fabbrica:
    `/api/ps` sa rispondere solo di un modello **caricato**, quindi il momento
    giusto e' subito dopo la generazione. Ed e' anche l'unico modo di tenere la
    fabbrica una funzione totale: interrogare la rete dentro `make_eval_run`
    faceva una chiamata HTTP per ogni `EvalRun` costruito -- misurato,
    `test_generation_baseline` passava da 1,1 a 49,6 secondi -- e legava la
    suite al motore acceso sulla macchina di chi la lancia.

    **Quando il motore non lo dice si registra il valore dichiarato e lo si
    dice a voce.** Resta l'unica meta' non chiusa: il JSON non distingue «32768
    misurato» da «32768 creduto», e distinguerli vorrebbe dire aggiungere un
    campo a `EvalRun`, cioe' toccare il contratto del §3. E' scritto in D-14.
    """
    try:
        from src.service.catalog import finestra_attiva

        attiva = finestra_attiva(llm)
    except Exception:
        attiva = None

    return attiva if attiva is not None else _dichiarata(llm)


def _dichiarata(llm: str) -> int:
    """Il valore dichiarato, detto a voce. **Non e' un default silenzioso.**

    Ci si arriva in due modi -- il motore non sa rispondere, o chi ha costruito
    l'`EvalRun` non ha misurato -- e in tutti e due il numero che finisce nel
    JSON e' una credenza. Dirlo su `stderr` e' il minimo che distingua questo
    caso da una misura, finche' il §3 non avra' un campo per distinguerli nel
    file (D-14).
    """
    print(
        f"! non ho potuto verificare la finestra di {llm}: registro "
        f"{cfg.CONTEXT_WINDOW}, che e' il valore dichiarato e non una misura.",
        file=sys.stderr,
    )
    return cfg.CONTEXT_WINDOW


def make_eval_run(
    *,
    git_commit: str,
    config_hash: str,
    dataset_id: str,
    pipeline_mode: str,
    config: dict[str, Any],
    metrics: dict[str, float],
    llm: str | None,
    context_window: int | None = None,
) -> EvalRun:
    """Costruisce un `EvalRun`. **L'unico posto che lo fa.**

    Erano cinque siti con lo stesso preambolo copiato: `run_id`, `timestamp`,
    `git_commit`, e i cinque campi che descrivono il modello. Quattro deducevano
    `reasoning_enabled`, il quinto lo scriveva `False` a mano -- ed e' la forma
    che prende una duplicazione quando invecchia: non tutte le copie ricevono la
    correzione.

    `llm` e' il punto della firma. **`None` significa "in questa run non ha
    girato nessun modello"**, e solo allora ha senso dire `model="retrieval_only"`,
    finestra 0 e ragionamento spento. Chiederlo a chi chiama, invece di
    dedurlo dal tipo di harness, e' cio' che corregge il difetto vero: l'harness
    del retrieval **usa** l'LLM quando `--query-rewrite` e' attivo (R-03), e
    dichiarava lo stesso di non usarlo. Su disco ne resta una prova --
    `20260806_093334_open_ragbench_generic_dense-rewrite.json` registra
    `model: retrieval_only` e `reasoning_enabled: false` per una run in cui il
    modello aveva riscritto ogni query.

    **`git_commit` arriva da fuori e non viene calcolato qui**, anche se
    sarebbe comodo. Gli harness lo catturano *prima* di partire, di proposito:
    una run lunga puo' finire dopo un commit, e il valore che serve e' quello
    del codice che ha girato, non quello dell'albero a fine corsa. Chiamare
    `git_commit()` dentro questa funzione avrebbe cambiato quella semantica in
    silenzio, che e' il modo in cui un refactor rompe qualcosa senza che nessun
    test se ne accorga.
    """
    if llm is None:
        return EvalRun(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            git_commit=git_commit,
            config_hash=config_hash,
            dataset_id=dataset_id,
            model="retrieval_only",
            quantization="none",
            context_window=0,
            temperature=0.0,
            reasoning_enabled=False,
            pipeline_mode=pipeline_mode,
            config=config,
            metrics=metrics,
        )
    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=git_commit,
        config_hash=config_hash,
        dataset_id=dataset_id,
        model=llm,
        quantization=cfg.LLM_QUANTIZATION,
        context_window=context_window if context_window is not None else _dichiarata(llm),
        temperature=cfg.TEMPERATURE,
        reasoning_enabled=reasoning_enabled(),
        pipeline_mode=pipeline_mode,
        config=config,
        metrics=metrics,
    )


#: Keys that are always present in a config dict, in display order.
CONFIG_KEYS: tuple[str, ...] = (
    "retrieval_mode",
    "top_k",
    "eval_depth",
    "rerank",
    "query_rewrite",
    "filter_content_type",
    "doc_aggregate",
    "collection",
    "n_queries",
)


def build_config(
    *,
    top_k: int,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
    collection: str,
    eval_depth: int | None = None,
    n_queries: int | None = None,
) -> dict[str, Any]:
    """Build the descriptive config dict stored in EvalRun.config.

    Every key is always present (unlike the hash input, which omits inactive
    flags) so the dashboard can render runs as a dense flag matrix.

    `n_queries` is the count actually evaluated, not the requested `--limit`.
    Runs before 2026-08-07 recorded neither, which made a 50-query smoke test
    indistinguishable from a 3045-query full run in the result file — the R-07
    numbers came from smoke tests and nothing said so.
    """
    return {
        "retrieval_mode": retrieval_mode,
        "top_k": top_k,
        "eval_depth": eval_depth,
        "rerank": rerank,
        "query_rewrite": query_rewrite,
        "filter_content_type": filter_content_type,
        "doc_aggregate": doc_aggregate,
        "collection": collection,
        "n_queries": n_queries,
        "embedding_model": cfg.EMBEDDING_MODEL,
        # R-11: sempre presenti, anche spenti. Nell'hash compaiono solo se
        # accesi (per non spostare le identita' gia' misurate), ma qui servono
        # sempre: un run che non dice come ha cercato non e' interpretabile, e
        # R-10 ha mostrato che su questo corpus la differenza vale 8 punti.
        "search_exact": cfg.SEARCH_EXACT,
        "hnsw_ef": cfg.HNSW_EF,
        "reranker_model": cfg.RERANKER_MODEL if rerank else None,
        "query_rewrite_model": (
            (cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL) if query_rewrite else None
        ),
    }


def config_slug(config: dict[str, Any]) -> str:
    """Compact human-readable label for a config, e.g. "hybrid-rerank-docagg".

    Used in result filenames and dashboard legends.  Only active flags appear,
    so the baseline config collapses to just its retrieval mode ("dense").
    """
    if not config:
        return "unknown"
    parts = [str(config.get("retrieval_mode", "dense"))]
    if config.get("query_rewrite"):
        parts.append("rewrite")
    if config.get("rerank"):
        parts.append("rerank")
    if config.get("filter_content_type"):
        parts.append(f"filter_{config['filter_content_type']}")
    if config.get("doc_aggregate"):
        parts.append("docagg")
    return "-".join(parts)


def differing_keys(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Config keys whose values differ between two runs.

    The dashboard uses this to enforce ROADMAP §15: a delta between two runs is
    only attributable to a single change when exactly one key differs.
    """
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))
