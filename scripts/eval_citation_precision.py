#!/usr/bin/env python3
"""C-03 — citation_precision over stored generations, per dataset.

No regeneration.  The C-01 harness saved every answer with the `chunk_ids` that
were in its context, so the whole of C-03 can be computed from those dumps plus
the chunk texts from Qdrant.  That is not a shortcut: it means the citation
metric and the format metric are measured on **the same answers**, so a change
in one cannot be confused with a different sample in the other.

The answers are passed through `citations.parse` first.  C-01 measures the raw
text on purpose; C-03 measures what a reader would actually be shown, which is
the repaired text — verifying markers the parser would have discarded would
score the model for citations the system never serves.

Reported per `dataset_id`, never pooled (§14).

Usage:
    python scripts/eval_citation_precision.py                      # latest dump per dataset
    python scripts/eval_citation_precision.py --limit 50           # smoke test
    python scripts/eval_citation_precision.py eval/results/generations/X.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg  # noqa: E402
from qdrant_client import models  # noqa: E402
from src.datasets.schema import EvalRun  # noqa: E402
from src.eval.citation_metrics import build_metrics, summarize, verify_answer  # noqa: E402
from src.eval.provenance import git_commit  # noqa: E402
from src.generation.citations import parse  # noqa: E402
from src.generation.entailment import normalize_premise  # noqa: E402
from src.index.store import get_client  # noqa: E402

GENERATIONS = ROOT / "eval" / "results" / "generations"
RESULTS = ROOT / "eval" / "results"


def latest_dumps() -> list[Path]:
    """The most recent dump per dataset.

    Four open_ragbench runs exist with different prompts; pooling them would
    average over a variable C-01 deliberately isolated.  The newest one is the
    prompt currently in the tree.
    """
    by_dataset: dict[str, Path] = {}
    for path in sorted(GENERATIONS.glob("*.jsonl")):
        dataset = path.stem.split("_", 2)[-1]
        by_dataset[dataset] = path
    return list(by_dataset.values())


def _dataset_of(record: dict) -> str:
    ids = record.get("chunk_ids") or []
    return ids[0].split(":")[0] if ids else "unknown"


def fetch_texts(client, collection: str, chunk_ids: list[str]) -> dict[str, str]:
    """Chunk texts by id, in batches Qdrant will accept."""
    out: dict[str, str] = {}
    ids = sorted(set(chunk_ids))
    for i in range(0, len(ids), 64):
        pts = client.scroll(
            collection,
            scroll_filter=models.Filter(must=[models.FieldCondition(
                key="chunk_id", match=models.MatchAny(any=ids[i:i + 64]))]),
            limit=256,
            with_payload=True,
        )[0]
        for p in pts:
            out[p.payload["chunk_id"]] = p.payload["text"]
    return out


def _config_hash(dump: Path, n: int) -> str:
    """Identita' della configurazione di verifica.

    `render_tables` entra solo quando e' attivo, cosi' le run di C-03 del
    2026-08-10 conservano l'identita' con cui sono state registrate. Senza di
    esso le due varianti di C-08 finirebbero su disco sotto lo stesso nome: e'
    lo stesso difetto che C-07 ha trovato in `citation_harness`, dove i due
    bracci del ragionamento sarebbero collassati su un unico `config_hash`.
    """
    params = {
        "harness": "citation_precision",
        "entailment_model": cfg.ENTAILMENT_MODEL,
        "threshold": cfg.ENTAILMENT_THRESHOLD,
        "premise_cap": cfg.ENTAILMENT_PREMISE_CAP,
        "source_generations": dump.name,
        "n": n,
    }
    if cfg.ENTAILMENT_RENDER_TABLES:
        params["render_tables"] = True
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def score_dump(dump: Path, limit: int | None, collection: str | None) -> tuple[str, dict]:
    rows = [json.loads(x) for x in dump.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if not r["abstained"] and r["answer"]]
    if limit:
        rows = rows[:limit]
    if not rows:
        raise SystemExit(f"{dump.name}: nessuna risposta valutabile")

    dataset = _dataset_of(rows[0])
    client = get_client(cfg.QDRANT_URL)
    texts = fetch_texts(client, collection or dataset,
                        [cid for r in rows for cid in r["chunk_ids"]])

    per_answer = []
    missing = 0
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        chunks = []
        for cid in r["chunk_ids"]:
            text = texts.get(cid)
            if text is None:
                missing += 1
                text = ""
            chunks.append({"chunk_id": cid, "text": normalize_premise(text)})
        answer = parse(r["answer"], len(chunks))
        per_answer.append(verify_answer(answer, chunks))
        if i % 20 == 0 or i == len(rows):
            el = time.time() - t0
            print(f"  [{i}/{len(rows)}] {el:.0f}s  ETA {(len(rows) - i) * el / i:.0f}s", flush=True)

    report = summarize(per_answer)
    if missing:
        print(f"  ATTENZIONE: {missing} chunk non trovati in Qdrant, trattati come vuoti")
    return dataset, {"report": report, "dump": dump, "n": len(rows)}


def print_report(dataset: str, res: dict) -> None:
    r = res["report"]
    print(f"\n{dataset}   ({res['dump'].name}, {res['n']} risposte)")
    print(f"  citation_precision   {r.citation_precision:.4f}  ({r.n_supported}/{r.n_pairs} citazioni)")
    print(f"  citation_recall      {r.citation_recall:.4f}  "
          f"({r.n_claims_supported}/{r.n_verifiable} affermazioni)")
    print(f"  uncited_claim_rate   {r.uncited_claim_rate:.4f}  ({r.n_uncited}/{r.n_verifiable})")
    print(f"  premesse spezzate    {r.windowed_rate:.4f}  ({r.n_windowed}/{r.n_pairs})")
    print(f"  affermazioni: {r.n_claims} totali, {r.n_verifiable} verificabili "
          f"({r.n_claims - r.n_verifiable} frammenti esclusi)")
    # C-09, stampate insieme e sotto un'intestazione loro: sono un'altra
    # definizione, e affiancarle alle righe qui sopra come se fossero la stessa
    # grandezza e' precisamente cio' che la decisione di OQ-05 vieta.
    print(f"  --- verificatore numerico (C-09), definizione diversa ---")
    print(f"  numeric_citation_precision  {r.numeric_citation_precision:.4f}  "
          f"({r.n_numeric_supported}/{r.n_numeric_judged} citazioni numeriche)")
    print(f"  numeric_coverage            {r.numeric_coverage:.4f}  "
          f"({r.n_numeric_judged}/{r.n_pairs} coppie; le altre restano all'NLI)")


def write_run(dataset: str, res: dict, commit: str) -> Path:
    r = res["report"]
    run = EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=commit,
        config_hash=_config_hash(res["dump"], res["n"]),
        dataset_id=dataset,
        model=cfg.LLM_MODEL,
        quantization=cfg.LLM_QUANTIZATION,
        context_window=cfg.CONTEXT_WINDOW,
        temperature=cfg.TEMPERATURE,
        reasoning_enabled=cfg.REASONING_EFFORT not in ("none", "", None),
        pipeline_mode="generic",
        config={
            "harness": "citation_precision",
            "entailment_model": cfg.ENTAILMENT_MODEL,
            "entailment_threshold": cfg.ENTAILMENT_THRESHOLD,
            "premise_cap": cfg.ENTAILMENT_PREMISE_CAP,
            "source_generations": res["dump"].name,
            "n_answers": res["n"],
            # Registrato sempre, anche quando e' False: e' la variabile di C-08,
            # e un campo assente non distingue "spento" da "misurato prima che
            # l'interruttore esistesse".
            "render_tables": cfg.ENTAILMENT_RENDER_TABLES,
        },
        metrics=build_metrics(r),
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS / f"{stamp}_citation_precision_{dataset}.json"
    path.write_text(json.dumps(json.loads(run.model_dump_json()), indent=2), encoding="utf-8")

    # The per-pair verdicts are what a failure gets read from, and they are not
    # reconstructable from the metrics.
    verdicts = RESULTS / "verdicts" / f"{stamp}_{dataset}.jsonl"
    verdicts.parent.mkdir(parents=True, exist_ok=True)
    with verdicts.open("w", encoding="utf-8") as fh:
        for v in r.verdicts:
            fh.write(json.dumps(asdict(v), ensure_ascii=False) + "\n")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dumps", nargs="*", type=Path, help="generation dumps (default: latest per dataset)")
    ap.add_argument("--limit", type=int, help="first N answers only (smoke test)")
    ap.add_argument("--collection", help="Qdrant collection override")
    ap.add_argument("--no-write", action="store_true", help="print only, write no EvalRun")
    args = ap.parse_args()

    commit = git_commit()
    for dump in (args.dumps or latest_dumps()):
        print(f"\n=== {dump.name}", flush=True)
        dataset, res = score_dump(dump, args.limit, args.collection)
        print_report(dataset, res)
        if not args.no_write:
            print(f"  -> {write_run(dataset, res, commit).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
