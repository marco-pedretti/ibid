#!/usr/bin/env python3
"""C-01: citation-format evaluation CLI.

Retrieves context, generates a cited answer per golden query, and measures how
often the raw output respects the citation format of ROADMAP §3.2.  Acceptance
criterion: format_compliance >= 0.95.

Two files per run:
    eval/results/<ts>_<dataset>_citations.json          the EvalRun
    eval/results/generations/<ts>_<dataset>.jsonl       the raw generations
    eval/results/generations/<ts>_<dataset>.prompt.txt  the prompt under test

The JSONL is the input to C-02 — the parser has to be built against outputs the
model actually produced.

Prerequisites:
    - eval/golden/{dataset_id}.jsonl built
    - Qdrant up with the dataset ingested
    - LLM server at LLM_BASE_URL

`--no-write` esiste perche' una calibrazione non e' una misura: stampa e basta,
senza lasciare un EvalRun in `eval/results/`.  Il 2026-08-12 uno smoke test da
tre query e' finito accanto alla misura vera da cento, sotto lo **stesso**
`config_hash` -- e giustamente, perche' la numerosita' e' precisione e non
configurazione (vedi il docstring di `_config_hash`).  Il rimedio non e'
rinominare le misure, e' non archiviare cio' che misura non e'.

Usage:
    python scripts/eval_citations.py --dataset open_ragbench --limit 50
    python scripts/eval_citations.py --dataset ledger --model gemma4:12b --limit 50
    python scripts/eval_citations.py --dataset open_ragbench --limit 3 --no-write
    python scripts/eval_citations.py --dataset ledger --limit 200         --system-prompt-file eval/results/generations/20260812_172405_ledger.prompt.txt
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from src.eval.citation_harness import GenerationWriter, prompt_hash, run_citation_eval
from src.generation.citation_format import COMPLIANCE_TARGET, VIOLATION_KINDS
from src.generation.prompt import SYSTEM

GOLDEN_DIR = ROOT / "eval" / "golden"
RESULTS_DIR = ROOT / "eval" / "results"
GENERATIONS_DIR = RESULTS_DIR / "generations"


def main() -> None:
    p = argparse.ArgumentParser(description="C-01 citation format evaluation")
    p.add_argument("--dataset", choices=registry.cli_choices(),
                   default="open_ragbench")
    p.add_argument("--top-k", type=int, default=cfg.TOP_K,
                   help="chunks placed in context")
    p.add_argument("--retrieval-mode", choices=["dense", "sparse", "hybrid"],
                   default="dense")
    p.add_argument("--collection", default=None,
                   help="Qdrant collection (default: dataset name)")
    p.add_argument("--pipeline-mode", choices=["generic", "routed"], default="generic")
    p.add_argument("--limit", type=int, default=None,
                   help="first N answerable queries only")
    p.add_argument("--model", default=None, help=f"LLM (default: {cfg.LLM_MODEL})")
    p.add_argument("--no-write", action="store_true",
                   help="stampa soltanto, non scrive EvalRun ne generazioni: per calibrazioni "
                        "e smoke test, che non vanno archiviati come misure")
    p.add_argument("--system-prompt-file", type=Path, default=None, metavar="FILE",
                   help="prompt di sistema letto da file invece di quello in vigore in "
                        "src/generation/prompt.py: serve a rimisurare col codice di oggi "
                        "un prompt che non e' piu' quello corrente. Ogni run ne lascia "
                        "una copia in eval/results/generations/*.prompt.txt")
    args = p.parse_args()

    # Il prompt sotto misura, deciso una volta per l'intera invocazione.
    #
    # Letto e basta, senza normalizzare niente: il sidecar e' scritto con
    # `write_text`, quindi il file restituisce gli stessi byte e quindi lo stesso
    # `prompt_hash`. Verificato sui due run del 2026-08-12, che dal file tornano
    # a `3a50ef63`, il valore registrato nel loro `config`. Aggiungere o togliere
    # un a-capo qui produrrebbe un hash diverso da quello che si vuole rimisurare
    # -- e `test_differs_on_whitespace` esiste perche' quella differenza conta.
    system_prompt = SYSTEM
    if args.system_prompt_file is not None:
        if not args.system_prompt_file.exists():
            print(f"[ERROR] {args.system_prompt_file} non trovato.")
            sys.exit(1)
        system_prompt = args.system_prompt_file.read_text(encoding="utf-8")

    datasets = registry.resolve(args.dataset)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    for dataset_id in datasets:
        golden_path = GOLDEN_DIR / f"{dataset_id}.jsonl"
        if not golden_path.exists():
            print(f"[ERROR] {golden_path} not found. Run build_golden.py first.")
            sys.exit(1)

        # The timestamp is taken before the run, not after: it names the file
        # the generations are streaming into while the run is still going.
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        gen_path = GENERATIONS_DIR / f"{ts}_{dataset_id}.jsonl"
        # Una calibrazione non lascia niente su disco. Il 2026-08-12 uno smoke
        # test da 3 query e' finito in `eval/results/` accanto alla misura vera
        # da 100, con lo **stesso** `config_hash` -- perche' la numerosita' e'
        # precisione, non configurazione, e giustamente non entra nell'hash.
        # Il rimedio non e' rinominare le misure: e' non archiviare cio' che
        # misura non e'. Stesso `--no-write` di eval_citation_precision.py.
        writer = None if args.no_write else GenerationWriter(gen_path, system_prompt)

        print(f"\n=== C-01 citation format: {dataset_id} ===", flush=True)
        # Il prompt e' cio' che questo script misura: stamparne l'identita' e'
        # l'unico modo perche' due run con numeri diversi si spieghino da sole.
        origine = "" if args.system_prompt_file is None else f" da {args.system_prompt_file}"
        print(f"  prompt {prompt_hash(system_prompt)}{origine}", flush=True)
        if writer is not None:
            print(f"  generazioni in {writer.tmp.relative_to(ROOT)}", flush=True)
        else:
            print("  --no-write: niente su disco, questa non e' una misura", flush=True)
        run, records = run_citation_eval(
            dataset_id=dataset_id,
            golden_path=golden_path,
            top_k=args.top_k,
            retrieval_mode=args.retrieval_mode,
            collection=args.collection,
            limit=args.limit,
            model=args.model,
            pipeline_mode=args.pipeline_mode,
            system_prompt=system_prompt,
            writer=writer,
        )
        if writer is not None:
            writer.finish()
            out_path = RESULTS_DIR / f"{ts}_{dataset_id}_citations.json"
            out_path.write_text(
                json.dumps(run.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        compliance = run.metrics["format_compliance"]
        lower = run.metrics["format_compliance_lower95"]
        # Verdict on the observed rate — see ComplianceSummary.meets_target.
        # The interval is printed beside it as context on the sample size.
        verdict = "PASS" if compliance >= COMPLIANCE_TARGET else "FAIL"
        print(f"\n{dataset_id}: format_compliance = {compliance:.4f} "
              f"(95% CI lower {lower:.4f}) -> {verdict}, target {COMPLIANCE_TARGET}")
        print(f"  answers {len(records)}  abstained {sum(r.abstained for r in records)}"
              f"  markers/answer {run.metrics['markers_per_answer']:.2f}")
        # Printed unconditionally, including at zero: a truncated answer looks
        # like a format failure, so the rate has to be read next to the verdict.
        print(f"  truncated {run.metrics['truncation_rate']:.3f}"
              f"  empty {run.metrics['empty_answer_rate']:.3f}"
              f"  reasoning_effort={run.config['reasoning_effort']}"
              f"  max_new_tokens={run.config['max_new_tokens']}")
        # Cost beside quality: C-07 buys one with the other.
        print(f"  latency p50 {run.metrics['latency_p50_s']:.1f}s"
              f"  p90 {run.metrics['latency_p90_s']:.1f}s"
              f"  completion tokens p50 {run.metrics['completion_tokens_p50']:.0f}")
        offenders = [
            (k, run.metrics[f"violation_{k}"]) for k in VIOLATION_KINDS
            if run.metrics[f"violation_{k}"] > 0
        ]
        if offenders:
            print("  violations (share of scored answers):")
            for kind, rate in sorted(offenders, key=lambda x: -x[1]):
                print(f"    {kind:<16} {rate:.3f}")
        else:
            print("  no violations")
        if writer is None:
            print("Niente salvato (--no-write).")
        else:
            print(f"Saved -> {out_path.relative_to(ROOT)}")
            print(f"         {gen_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
