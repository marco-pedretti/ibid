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
        print(f"\n[gate di astensione non calibrato per ({result.collection}, dense): "
              "non applicato]")

    print("\n" + "=" * 60)
    print("RISPOSTA:")
    print("=" * 60)
    print(result.text)
    print("=" * 60)
    if result.truncated:
        print("\n[risposta troncata dal tetto di token: le citazioni mancanti "
              "potrebbero non essere mai state scritte]")

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


def main() -> None:
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
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Salta la verifica NLI delle citazioni (piu' veloce, nessun verdetto)",
    )
    args = parser.parse_args()

    print(f"Encoding query con {cfg.EMBEDDING_MODEL} ...", flush=True)
    render(answer(AnswerRequest(
        query=args.query,
        dataset_id=args.dataset,
        collection=args.collection,
        top_k=args.top_k,
        model=args.model,
        verify=not args.no_verify,
    )))


if __name__ == "__main__":
    main()
