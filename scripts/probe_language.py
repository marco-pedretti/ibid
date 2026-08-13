#!/usr/bin/env python3
"""C-05 — does the answer come back in the language of the question?

The acceptance criterion is "nessuna risposta mista incoerente su 20 campioni",
and the honest way to test it is **not** to re-check English questions: both
corpora are English, so an English answer proves nothing about the instruction.
The 891 stored generations already settle that case — 873 English, 18 unknown,
zero mixed.  What was never tested is the instruction itself.

So the probe asks the same questions in another language against **the same
chunks**.  Retrieval runs on the original English query and is then held fixed:
translating the query would also move retrieval, and a wrong answer could then
be a retrieval failure wearing a language failure's clothes.  One variable.

Three things are checked per answer, because they can fail independently:

    lingua       is the answer in the language of the question?
    coerenza     is it in *one* language, or does it switch mid-answer?
    formato      does §3.2 still hold?  A prompt line that fixes the language
                 and breaks the citations is not an improvement.

Material: `tests/fixtures/multilingual_queries.jsonl` — 20 real golden queries,
10 per dataset, hand-translated, with their query_id so a run is traceable back
to the retrieval gold.

Usage:
    python scripts/probe_language.py
    python scripts/probe_language.py --dataset ledger --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from src.eval.citation_harness import _payload_to_chunk
from src.eval.retrieval_backends import RETRIEVERS
from src.generation.chat import generate_detailed
from src.generation.citation_format import check_format
from src.generation.language import UNKNOWN, detect, profile
from src.generation.prompt import SYSTEM, build_user_message
from src.index.store import get_client

FIXTURE = ROOT / "tests" / "fixtures" / "multilingual_queries.jsonl"


def load(dataset: str | None, limit: int | None) -> list[dict]:
    rows = [json.loads(x) for x in FIXTURE.read_text(encoding="utf-8").splitlines() if x.strip()]
    if dataset:
        rows = [r for r in rows if r["dataset_id"] == dataset]
    return rows[:limit] if limit else rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=registry.dataset_ids())
    ap.add_argument("--limit", type=int)
    ap.add_argument("--top-k", type=int, default=cfg.TOP_K)
    ap.add_argument("--model", default=cfg.LLM_MODEL)
    args = ap.parse_args()

    rows = load(args.dataset, args.limit)
    client = get_client(cfg.QDRANT_URL)
    retrieve = RETRIEVERS["dense"]

    results = []
    for dataset in sorted({r["dataset_id"] for r in rows}):
        group = [r for r in rows if r["dataset_id"] == dataset]
        # Retrieval on the ENGLISH query, held fixed across the comparison.
        cands = retrieve(client, dataset, [r["en"] for r in group], args.top_k, None)
        for row, cand in zip(group, cands):
            chunks = [_payload_to_chunk(p) for p in cand.payloads[:args.top_k]]
            completion = generate_detailed(
                base_url=cfg.LLM_BASE_URL,
                model=args.model,
                system=SYSTEM,
                user=build_user_message(row["translated"], chunks),
                temperature=cfg.TEMPERATURE,
                max_tokens=cfg.MAX_NEW_TOKENS,
                reasoning_effort=cfg.REASONING_EFFORT,
            )
            prof = profile(completion.content)
            fmt = check_format(completion.content, len(chunks))
            asked = detect(row["translated"]) or row["lang"]
            results.append({
                "query_id": row["query_id"],
                "dataset_id": dataset,
                "asked": row["lang"],
                "asked_detected": asked,
                "answered": prof.dominant,
                "mixed": prof.is_mixed,
                "languages": sorted(prof.languages),
                "compliant": fmt.compliant,
                "abstained": fmt.abstained,
                "answer": completion.content,
            })
            mark = "OK " if (prof.dominant == row["lang"] and not prof.is_mixed) else "NO "
            print(f"  {mark} [{dataset[:3]}] chiesto {row['lang']} -> risposto "
                  f"{prof.dominant:8s} mista={prof.is_mixed}  formato={fmt.compliant}"
                  f"{'  (astensione)' if fmt.abstained else ''}", flush=True)

    print(f"\n{'=' * 62}\n{len(results)} campioni")
    for dataset in sorted({r["dataset_id"] for r in results}):
        g = [r for r in results if r["dataset_id"] == dataset]
        scored = [r for r in g if not r["abstained"]]
        right = sum(1 for r in scored if r["answered"] == r["asked"])
        mixed = sum(1 for r in scored if r["mixed"])
        unk = sum(1 for r in scored if r["answered"] == UNKNOWN)
        fmt = sum(1 for r in scored if r["compliant"])
        print(f"\n{dataset}  ({len(g)} campioni, {len(g) - len(scored)} astensioni)")
        print(f"  lingua della domanda   {right}/{len(scored)}")
        print(f"  risposte MISTE         {mixed}/{len(scored)}   <- il criterio C-05")
        print(f"  lingua non identificata {unk}/{len(scored)}")
        print(f"  formato §3.2 rispettato {fmt}/{len(scored)}")

    out = ROOT / "eval" / "results" / "language_probe.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
