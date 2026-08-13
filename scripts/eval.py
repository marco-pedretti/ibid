"""E-03 / E-06 / R-01–R-07: Run retrieval evaluation and write EvalRun JSON to eval/results/.

Usage:
    python scripts/eval.py [--dataset open_ragbench|ledger|all] [--top-k N] [--limit N]
    python scripts/eval.py --retrieval-mode sparse               # E-06 lexical-only baseline
    python scripts/eval.py --retrieval-mode hybrid               # R-01 hybrid RRF
    python scripts/eval.py --rerank                              # R-02 cross-encoder reranker
    python scripts/eval.py --retrieval-mode hybrid --rerank      # hybrid + reranker
    python scripts/eval.py --query-rewrite                       # R-03 query rewriting
    python scripts/eval.py --query-rewrite --rerank              # R-03 + R-02
    python scripts/eval.py --filter-content-type text            # R-04 text-only filter
    python scripts/eval.py --filter-content-type auto            # R-04 keyword-inferred filter
    python scripts/eval.py --doc-aggregate                       # R-05 doc-level file list
    python scripts/eval.py --collection open_ragbench_routed --pipeline-mode routed --doc-aggregate  # R-07
    python scripts/eval.py --limit 50 --no-write                  # calibrazione, non archiviata

Options:
    --dataset              Which dataset(s) to evaluate (default: all)
    --top-k                Retrieval depth (default: cfg.TOP_K = 5)
    --limit                Evaluate only first N answerable queries per dataset (smoke test)
    --retrieval-mode       dense (default) | sparse | hybrid
    --rerank               Apply cross-encoder reranking after initial retrieval (R-02)
    --query-rewrite        Rewrite queries with LLM before embedding (R-03)
    --filter-content-type  text | table | mixed | auto (R-04 metadata filter)
    --doc-aggregate        No-op: doc_R@5/doc_R@10 sono ora sempre riportate (R-05)
    --collection           Override Qdrant collection name (R-07: e.g. open_ragbench_routed)
    --pipeline-mode        Ingestion routing axis: generic | routed (R-07)
    --no-write             Stampa e basta: una calibrazione non e' una misura

Result files are named {ts}_{dataset}_{pipeline_mode}_{config_slug}.json.
The retrieval flags are stored structurally in EvalRun.config — pipeline_mode
stays binary per ROADMAP §3.3.

`--no-write` esiste per la stessa ragione del gemello in `eval_citations.py`:
il 2026-08-13, durante R-08, uno smoke test da 100 query e' finito in
`eval/results/` accanto alle misure vere e ha dovuto essere cancellato a mano.
La numerosita' non entra nel `config_hash` -- e' precisione, non configurazione
-- quindi su disco quel file era indistinguibile da una misura. Il rimedio non
e' rinominare le misure, e' non archiviare cio' che misura non e'.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from src.eval.dump import JsonlWriter
from src.eval.harness import run_retrieval_eval
from src.eval.run_config import build_config, config_slug

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"


def _shown(path: Path) -> str:
    """Percorso relativo alla radice se ci sta, altrimenti assoluto.

    `relative_to` solleva invece di ripiegare, e nei test `RESULTS_DIR` diventa
    una tmp_path fuori dal repo: una riga di stampa non deve far fallire una run.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run_dataset(
    dataset_id: str,
    top_k: int,
    limit: int | None,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
    collection: str | None = None,
    pipeline_mode_override: str | None = None,
    no_write: bool = False,
) -> None:
    golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
    if not golden_path.exists():
        print(f"  ERROR: {golden_path} not found — run build_golden.py first.")
        return

    # pipeline_mode stays binary per ROADMAP §3.3 — the retrieval flags live in
    # EvalRun.config, so two runs differing by one flag stay comparable.
    pipeline_mode = pipeline_mode_override or "generic"

    eff_collection = collection or dataset_id
    slug = config_slug(
        build_config(
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            rerank=rerank,
            query_rewrite=query_rewrite,
            filter_content_type=filter_content_type,
            doc_aggregate=doc_aggregate,
            collection=eff_collection,
        )
    )
    n_desc = f"first {limit}" if limit else "all"
    print(
        f"  Evaluating {n_desc} queries against {dataset_id} "
        f"(collection={eff_collection}, top_k={top_k}, "
        f"pipeline={pipeline_mode}, config={slug})...",
        flush=True,
    )
    t0 = time.time()

    # Q-02: i risultati per query. Il nome si sceglie **prima** della run,
    # perche' e' il file in cui i record vengono scritti mentre gira -- e con
    # `--no-write` non si scrive niente, calibrazione compresa.
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Derivata da RESULTS_DIR **qui** e non come costante di modulo: i test
    # sostituiscono `scripts.eval.RESULTS_DIR` con una tmp_path, e una costante
    # calcolata all'import gli sfuggirebbe -- come mi e' successo, lasciando sei
    # file veri in `eval/results/retrieved/` scritti da una suite di test.
    # Cartella separata dalle metriche: sono file per query e non per run, e
    # mescolarli renderebbe illeggibile un `ls` di `eval/results/`.
    retrieved_dir = RESULTS_DIR / "retrieved"
    writer = None if no_write else JsonlWriter(
        retrieved_dir / f"{ts}_{dataset_id}_{pipeline_mode}_{slug}.jsonl"
    )
    if writer is not None:
        print(f"  risultati per query in {_shown(writer.tmp)}", flush=True)

    eval_run = run_retrieval_eval(
        dataset_id=dataset_id,
        golden_path=golden_path,
        top_k=top_k,
        pipeline_mode=pipeline_mode,
        retrieval_mode=retrieval_mode,
        rerank=rerank,
        query_rewrite=query_rewrite,
        filter_content_type=filter_content_type,
        doc_aggregate=doc_aggregate,
        limit=limit,
        collection=collection,
        writer=writer,
    )

    elapsed = time.time() - t0
    if no_write:
        print(f"  Done in {elapsed:.1f}s -> niente salvato (--no-write)")
    else:
        writer.finish()
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{ts}_{dataset_id}_{eval_run.pipeline_mode}_{slug}.json"
        out.write_text(eval_run.model_dump_json(indent=2), encoding="utf-8")
        print(f"  Done in {elapsed:.1f}s -> {out.name}")
        print(f"         {_shown(writer.path)}  ({writer.n} query)")
    for name, value in sorted(eval_run.metrics.items()):
        print(f"    {name}: {value:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval evaluation (E-03/E-06)")
    parser.add_argument("--dataset", choices=registry.cli_choices(), default="all")
    parser.add_argument("--top-k", type=int, default=cfg.TOP_K)
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate only first N answerable queries (smoke test)")
    parser.add_argument("--retrieval-mode", choices=["dense", "sparse", "hybrid"], default="dense",
                        help="dense=E-03 (default), sparse=E-06 lexical-only BM25, hybrid=R-01 RRF")
    parser.add_argument("--rerank", action="store_true",
                        help="Apply cross-encoder reranking after initial retrieval (R-02)")
    parser.add_argument("--query-rewrite", action="store_true",
                        help="Rewrite queries with LLM before embedding (R-03)")
    parser.add_argument("--filter-content-type",
                        choices=["text", "table", "mixed", "auto"], default=None,
                        help="Apply metadata filter: text|table|mixed=static, auto=keyword-inferred (R-04)")
    parser.add_argument("--doc-aggregate", action="store_true",
                        help="Accettato per compatibilita: le metriche doc_R@5/doc_R@10 "
                             "sono ora sempre calcolate, cosi ogni run e confrontabile (R-05)")
    parser.add_argument("--collection", default=None, metavar="NAME",
                        help=(
                            "Qdrant collection to query instead of dataset_id "
                            "(R-07: e.g. open_ragbench_routed). Use per-dataset when --dataset=all."
                        ))
    parser.add_argument("--pipeline-mode", choices=["generic", "routed"], default=None,
                        help=(
                            "Ingestion routing axis stored in EvalRun.pipeline_mode "
                            "(R-07; default: generic). Retrieval flags are recorded "
                            "separately in EvalRun.config, not in this label."
                        ))
    parser.add_argument("--no-write", action="store_true",
                        help="stampa soltanto, non scrive l'EvalRun: per calibrazioni e "
                             "smoke test, che non vanno archiviati come misure")
    args = parser.parse_args()

    datasets = registry.resolve(args.dataset)
    for ds in datasets:
        print(f"=== {ds} ===")
        run_dataset(
            ds, args.top_k, args.limit, args.retrieval_mode, args.rerank,
            args.query_rewrite, args.filter_content_type, args.doc_aggregate,
            collection=args.collection,
            pipeline_mode_override=args.pipeline_mode,
            no_write=args.no_write,
        )


if __name__ == "__main__":
    main()
