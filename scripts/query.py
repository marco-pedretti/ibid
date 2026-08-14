#!/usr/bin/env python3
"""CLI di interrogazione: stampa cio' che `src/service` decide.

Dalla T-05 questo file *era* la pipeline. Da A-01 non lo e' piu': la sequenza
recupero → gate → generazione → riparazione vive in `src.service.answer`, e qui
resta solo la formattazione per un terminale. E' il criterio di A-01 preso alla
lettera — se un endpoint HTTP non deve contenere logica di pipeline, non deve
contenerla nemmeno l'altro consumatore, altrimenti non c'e' niente da
confrontare.

Prerequisiti:
    1. docker compose --profile full up qdrant -d
    2. python scripts/ingest.py --skip-download
    3. Ollama in ascolto con gemma4 caricato

Uso:
    python scripts/query.py "la tua domanda"
    python scripts/query.py --top-k 3 "What is the SD of RMSE for Ridge Regression?"
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets.registry import dataset_ids
from src.service import Answer, AnswerRequest, answer


def render(result: Answer) -> None:
    """Il risultato, letto ad alta voce. Nessuna decisione presa qui."""
    if not result.config.rag:
        # U-03: qui non c'e' stato nessun recupero, e dirlo con "top 0 chunk"
        # lo farebbe sembrare un recupero fallito.
        print(f"\n[senza contesto, prompt {result.config.baseline_prompt}: "
              "e' il braccio nudo del confronto]")
    else:
        print(f"\nTop {len(result.chunks)} chunk recuperati:")
        for item in result.chunks:
            preview = item.chunk.text[:80].replace("\n", " ")
            print(f"  [{item.marker}] {item.chunk.doc_id} (score={item.score:.3f}): {preview}...")

        if result.abstention == "retrieval":
            print(f"\nASTENSIONE (C-04): punteggio massimo {result.gate.score:.4f} sotto la soglia "
                  f"{result.gate.threshold:.4f} per '{result.collection}'.")
            print("=" * 60)
            print(result.text)
            print("=" * 60)
            return

        if not result.gate.active:
            print(f"\n[gate di astensione non calibrato per "
                  f"({result.collection}, {result.config.retrieval_mode}): non applicato]")

    print("\n" + "=" * 60)
    print("RISPOSTA:")
    print("=" * 60)
    print(result.text)
    print("=" * 60)
    if result.truncated:
        coda = (
            "le citazioni mancanti potrebbero non essere mai state scritte"
            if result.config.rag
            else "la risposta e' incompleta"
        )
        print(f"\n[risposta troncata dal tetto di token: {coda}]")

    if result.config.rag:
        print("\nFonti citate:")
        for marker in result.cited:
            chunk = result.chunks[marker - 1].chunk
            print(f"  [{marker}] {chunk.source_uri}  ({chunk.doc_id})")
        if result.uncited:
            print(f"\nChunk recuperati ma non citati: {result.uncited}")

    render_verdicts(result)


def render_verdicts(result: Answer) -> None:
    """Le citazioni con il loro verdetto — tutte, anche quelle bocciate.

    U-07: marcate, non nascoste. Filtrare le non verificate farebbe sembrare il
    sistema perfetto proprio nel punto in cui il progetto vuole essere misurato.
    """
    if not result.verified:
        print("\n[verifica non eseguita: nessun verdetto sulle citazioni]")
        return
    if not result.citations:
        return

    supportate = sum(1 for c in result.citations if c.supported)
    print(f"\nVerifica delle citazioni (C-03): {supportate}/{len(result.citations)} sostenute")
    for c in result.citations:
        segno = "OK  " if c.supported else "NO  "
        # `not_applicable` non e' un verdetto, e' "questa coppia resta all'NLI":
        # stamparlo su ogni riga di prosa sarebbe rumore.
        numerico = f"  [numerico: {c.numeric}]" if c.numeric in ("supported", "unsupported") else ""
        print(f"  {segno}[{c.marker}] p={c.score:.3f}{numerico}  {c.claim[:70]}")
    if result.uncited_claims:
        print(f"\nAffermazioni senza alcuna citazione: {len(result.uncited_claims)}")
        for claim in result.uncited_claims:
            print(f"  --  {claim[:70]}")


def build_parser() -> argparse.ArgumentParser:
    """Le opzioni del CLI. Estratte da `main()` cosi' che un test possa
    costruire una richiesta senza far partire nulla — e' cio' che rende
    verificabile il criterio di A-01, «la stessa richiesta dalla CLI e
    dall'API»."""
    parser = argparse.ArgumentParser(description="Interrogazione da riga di comando")
    parser.add_argument("query", help="Domanda a cui rispondere")
    parser.add_argument("--dataset", default="open_ragbench", choices=dataset_ids())
    parser.add_argument(
        "--collection",
        default=None,
        help="Collection Qdrant, se diversa dal dataset (es. 'ledger_routed')",
    )
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K)
    parser.add_argument("--model", default=cfg.LLM_MODEL)
    parser.add_argument("--retrieval-mode", default="dense", choices=("dense", "sparse", "hybrid"))
    parser.add_argument("--rerank", action="store_true", help="Cross-encoder dopo il recupero (R-02)")
    parser.add_argument(
        "--query-rewrite", action="store_true", help="L'LLM riscrive la query prima di cercare (R-03)"
    )
    parser.add_argument(
        "--filter-content-type",
        default="",
        help="'auto' lo deduce dalla domanda; oppure text|table|mixed (R-04)",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Risponde senza contesto: l'altro braccio del confronto di U-03",
    )
    parser.add_argument(
        "--baseline-prompt",
        default="strict",
        choices=cfg.BASELINE_PROMPTS,
        help="Con --no-rag: permissivo (E-04) o severo (E-05)",
    )
    parser.add_argument("--search-exact", action="store_true", help="Salta HNSW (R-11)")
    parser.add_argument("--hnsw-ef", type=int, default=None)
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Salta la verifica NLI delle citazioni (piu' veloce, nessun verdetto)",
    )
    return parser


def request_from_args(args: argparse.Namespace) -> AnswerRequest:
    """Gli argomenti del CLI diventano una richiesta di servizio.

    E' lo stesso oggetto che `QueryRequest.to_service()` costruisce dal corpo
    della POST. Un solo posto decide cosa significano quei parametri, e due
    strade che ci arrivano — che e' la condizione perche' «stesso risultato»
    sia una proprieta' e non una coincidenza.
    """
    config = cfg.RequestConfig.from_defaults(
        top_k=args.top_k,
        model=args.model,
        retrieval_mode=args.retrieval_mode,
        rerank=args.rerank,
        query_rewrite=args.query_rewrite,
        filter_content_type=args.filter_content_type,
        rag=not args.no_rag,
        baseline_prompt=args.baseline_prompt,
        verify=not args.no_verify,
        **({"search_exact": True} if args.search_exact else {}),
        **({"hnsw_ef": args.hnsw_ef} if args.hnsw_ef is not None else {}),
    )

    return AnswerRequest(
        query=args.query,
        dataset_id=args.dataset,
        collection=args.collection,
        config=config,
    )


def main() -> None:
    args = build_parser().parse_args()
    print(f"Encoding query con {cfg.EMBEDDING_MODEL} ...", flush=True)
    render(answer(request_from_args(args)))


if __name__ == "__main__":
    main()
