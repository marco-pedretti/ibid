#!/usr/bin/env python3
"""C-04 — correct abstention on E-02, and what it costs on answerable queries.

Two rates that only mean something together:

    astensione corretta   on the 35 unanswerable queries of E-02
    astensione falsa      on answerable queries the system should have answered

Reporting the first alone is trivially gamed: a system that abstains on
everything scores 100%.

Three columns, because *who* abstained matters as much as whether:

    gate     the C-04 threshold refused before the LLM was called
    modello  the LLM was called and said "Insufficient information."
    nessuno  an answer was produced

The distinction is the whole point of C-04.  The model already abstains 35/35 on
E-02, so the gate cannot improve the rate — what it changes is that the refusal
becomes a property of the code rather than a habit of one model, and costs no
GPU.  A run that cannot tell the two apart cannot show that.

Per `dataset_id`, never pooled (§15).

Usage:
    python scripts/eval_abstention.py
    python scripts/eval_abstention.py --dataset ledger --n-answerable 40
    python scripts/eval_abstention.py --no-gate      # baseline: model only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg  # noqa: E402
from src.datasets.schema import EvalRun  # noqa: E402
from src.eval.citation_harness import _payload_to_chunk  # noqa: E402
from src.eval.provenance import git_commit  # noqa: E402
from src.eval.retrieval_backends import RETRIEVERS  # noqa: E402
from src.generation.chat import generate_detailed  # noqa: E402
from src.generation.citation_format import is_abstention  # noqa: E402
from src.generation.prompt import SYSTEM, build_user_message  # noqa: E402
from src.index.store import get_client  # noqa: E402
from src.retrieval.abstention import decide  # noqa: E402

RESULTS = ROOT / "eval" / "results"

#: Answerable queries drawn for the false-abstention side. They are taken from
#: the tail of the shuffled list so they cannot overlap the 300 the calibration
#: used — a false-abstention rate measured on the queries that set the threshold
#: is not a measurement.
CALIBRATION_RESERVED = 300


def run_group(client, dataset, queries, top_k, model, use_gate, label):
    retrieve = RETRIEVERS["dense"]
    cands = retrieve(client, dataset, [q["query_text"] for q in queries], top_k, None)
    rows = []
    t0 = time.time()
    for i, (q, cand) in enumerate(zip(queries, cands), 1):
        gate = decide(cand.scores, dataset, "dense")
        if use_gate and gate.abstain:
            rows.append({"query_id": q["query_id"], "by": "gate", "abstained": True,
                         "top1": gate.score, "threshold": gate.threshold, "latency_s": 0.0})
        else:
            chunks = [_payload_to_chunk(p) for p in cand.payloads[:top_k]]
            t = time.time()
            comp = generate_detailed(
                base_url=cfg.LLM_BASE_URL, model=model, system=SYSTEM,
                user=build_user_message(q["query_text"], chunks),
                temperature=cfg.TEMPERATURE, max_tokens=cfg.MAX_NEW_TOKENS,
                reasoning_effort=cfg.REASONING_EFFORT)
            abst = is_abstention(comp.content)
            rows.append({"query_id": q["query_id"], "by": "modello" if abst else "nessuno",
                         "abstained": abst, "top1": gate.score, "threshold": gate.threshold,
                         "latency_s": round(time.time() - t, 2), "answer": comp.content})
        if i % 10 == 0 or i == len(queries):
            print(f"    [{label} {i}/{len(queries)}] {time.time() - t0:.0f}s", flush=True)
    return rows


def summarize(rows):
    n = len(rows)
    by = {k: sum(1 for r in rows if r["by"] == k) for k in ("gate", "modello", "nessuno")}
    return {
        "n": n,
        "abstained": sum(1 for r in rows if r["abstained"]),
        "rate": sum(1 for r in rows if r["abstained"]) / n if n else 0.0,
        "by_gate": by["gate"],
        "by_model": by["modello"],
        "answered": by["nessuno"],
        "llm_seconds": round(sum(r["latency_s"] for r in rows), 1),
    }


def _config_hash(use_gate: bool, n_ans: int) -> str:
    params = {
        "harness": "abstention",
        "gate": use_gate,
        "budget": cfg.ABSTENTION_BUDGET if use_gate else None,
        "thresholds": cfg.ABSTENTION_THRESHOLDS if use_gate else None,
        "llm_model": cfg.LLM_MODEL,
        "top_k": cfg.TOP_K,
        "n_answerable": n_ans,
    }
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", choices=["open_ragbench", "ledger"])
    ap.add_argument("--n-answerable", type=int, default=60)
    ap.add_argument("--top-k", type=int, default=cfg.TOP_K)
    ap.add_argument("--model", default=cfg.LLM_MODEL)
    ap.add_argument("--no-gate", action="store_true", help="baseline: solo il modello")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    use_gate = not args.no_gate
    commit = git_commit()
    client = get_client(cfg.QDRANT_URL)

    for dataset in ([args.dataset] if args.dataset else ["open_ragbench", "ledger"]):
        rows = [json.loads(x) for x in
                (ROOT / "eval" / "golden" / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines()
                if x.strip()]
        unanswerable = [r for r in rows if r.get("answerable") is False]
        answerable = [r for r in rows if r.get("answerable") is not False]
        random.Random(1).shuffle(answerable)
        answerable = answerable[CALIBRATION_RESERVED:CALIBRATION_RESERVED + args.n_answerable]

        print(f"\n=== {dataset}  (gate {'ON' if use_gate else 'OFF'})", flush=True)
        un = run_group(client, dataset, unanswerable, args.top_k, args.model, use_gate, "E-02")
        an = run_group(client, dataset, answerable, args.top_k, args.model, use_gate, "risp.")
        s_un, s_an = summarize(un), summarize(an)

        print(f"\n{dataset}")
        print(f"  astensione CORRETTA su E-02   {s_un['rate']:.1%}  ({s_un['abstained']}/{s_un['n']})"
              f"   [gate {s_un['by_gate']}, modello {s_un['by_model']}]")
        print(f"  astensione FALSA su rispondibili {s_an['rate']:.1%}  ({s_an['abstained']}/{s_an['n']})"
              f"   [gate {s_an['by_gate']}, modello {s_an['by_model']}]")
        print(f"  secondi di LLM spesi su E-02  {s_un['llm_seconds']:.0f}s")

        if args.no_write:
            continue
        run = EvalRun(
            run_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc),
            git_commit=commit, config_hash=_config_hash(use_gate, len(an)),
            dataset_id=dataset, model=args.model, quantization=cfg.LLM_QUANTIZATION,
            context_window=cfg.CONTEXT_WINDOW, temperature=cfg.TEMPERATURE,
            reasoning_enabled=cfg.REASONING_EFFORT not in ("none", "", None),
            pipeline_mode="generic",
            config={"harness": "abstention", "abstention_gate": use_gate,
                    "abstention_budget": cfg.ABSTENTION_BUDGET if use_gate else None,
                    "abstention_threshold": cfg.ABSTENTION_THRESHOLDS.get(dataset) if use_gate else None,
                    "top_k": args.top_k, "llm_model": args.model,
                    "n_unanswerable": s_un["n"], "n_answerable": s_an["n"]},
            metrics={
                "correct_abstention_rate": s_un["rate"],
                "false_abstention_rate": s_an["rate"],
                "correct_abstention_by_gate": s_un["by_gate"] / s_un["n"] if s_un["n"] else 0.0,
                "correct_abstention_by_model": s_un["by_model"] / s_un["n"] if s_un["n"] else 0.0,
                "llm_seconds_on_unanswerable": s_un["llm_seconds"],
            },
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = "gate" if use_gate else "nogate"
        path = RESULTS / f"{stamp}_abstention_{tag}_{dataset}.json"
        path.write_text(json.dumps(json.loads(run.model_dump_json()), indent=2), encoding="utf-8")
        detail = RESULTS / "abstention" / f"{stamp}_{tag}_{dataset}.jsonl"
        detail.parent.mkdir(parents=True, exist_ok=True)
        with detail.open("w", encoding="utf-8") as fh:
            for r in un + an:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
