#!/usr/bin/env python3
"""C-07 spike — what does the reasoning switch actually do on this endpoint?

**This is measurement, not product code.**  C-07 asks for one row on the effect
of extended reasoning on/off, and the whole row rests on `reasoning_effort`
behaving the way the OpenAI contract says.  Two things had to be settled before
designing a run around it, and neither could be assumed:

  effort   Are "low" / "medium" / "high" distinguishable from each other, and
           from omitting the field?  `src/generation/chat.py` records "low" as
           *accepted, no effect* — measured on **one** prompt while looking for
           a way to switch reasoning off, not while trying to grade it.  If the
           three levels are indistinguishable the axis is binary, which is what
           the ROADMAP calls it ("on/off"), and C-07 must say so rather than
           report a level it did not control.

  budget   With reasoning on, the thinking tokens are spent before the answer
           starts.  `MAX_NEW_TOKENS` is 1024 and the one measurement on record
           has reasoning consuming 1410, so the deployed budget may not fit an
           answer at all.  A run flipping only the switch would then measure
           **the token budget**, and report it as a property of reasoning.

  levels   Follow-up, after the documentation was read (see `chat.py`).  Ollama
           passes the effort *string* down and Gemma 4's thinking is the boolean
           `enable_thinking`, so `medium == high == max` is what both sources
           predict — and `effort` confirmed the first two.  `"low"` is the
           anomaly neither source explains, and this probe asks the only
           question that separates a real third state from sampling jitter:
           **does `"low"` reproduce itself?**  It also covers `"max"`, a
           documented value the first probe never sent.

Both arms of C-07 have to share every parameter but the switch, so the budget
this probe settles is applied to *both* — including the control.

Usage:
    python scripts/probe_reasoning.py effort  [dataset] [n]
    python scripts/probe_reasoning.py budget  [dataset] [n]
    python scripts/probe_reasoning.py levels  [dataset] [n]
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as cfg
from src.eval.provenance import load_golden
from src.eval.retrieval_backends import RETRIEVERS
from src.generation.chat import generate_detailed
from src.generation.citation_format import check_format
from src.generation.prompt import SYSTEM, build_user_message
from src.index.store import chunk_from_payload, get_client

#: `None` means "omit the field entirely" — the state every generation before
#: C-01 was in, and the one the docstring of chat.py calls invisible reasoning.
EFFORTS: list[str | None] = ["none", "low", "medium", "high", None]

BUDGETS: list[int] = [1024, 2048, 4096]


def _prompts(dataset: str, n: int) -> list[tuple[str, str, int]]:
    """(query_id, user_message, n_chunks) for the first n answerable queries.

    Retrieval is re-run rather than replayed from the stored generations: the
    probe has to exercise the same path as the harness, and a context rebuilt by
    hand would be a different measurement wearing the same name.
    """
    golden = cfg.ROOT / "eval" / "golden" / f"{dataset}.jsonl"
    queries = [q for q in load_golden(golden) if q.answerable and q.dataset_id == dataset][:n]
    client = get_client(cfg.QDRANT_URL)
    cands = RETRIEVERS["dense"](
        client, dataset, [q.query_text for q in queries], cfg.TOP_K, None
    )
    out = []
    for q, cand in zip(queries, cands):
        chunks = [chunk_from_payload(p) for p in cand.payloads[: cfg.TOP_K]]
        out.append((q.query_id, build_user_message(q.query_text, chunks), len(chunks)))
    return out


def _run(user: str, n_chunks: int, effort: str | None, budget: int) -> dict:
    t0 = time.time()
    comp = generate_detailed(
        base_url=cfg.LLM_BASE_URL,
        model=cfg.LLM_MODEL,
        system=SYSTEM,
        user=user,
        temperature=cfg.TEMPERATURE,
        max_tokens=budget,
        reasoning_effort=effort,
    )
    report = check_format(comp.content, n_chunks)
    return {
        "tokens": comp.completion_tokens,
        "chars": len(comp.content),
        "empty": not comp.content,
        "truncated": comp.truncated,
        "compliant": report.compliant,
        "latency": time.time() - t0,
    }


def _table(rows: list[tuple[str, list[dict]]], header: str) -> None:
    print(f"\n{header}")
    print(f"{'arm':<18} {'tokens':>8} {'chars':>7} {'empty':>6} {'trunc':>6} {'fmt-ok':>7} {'s':>7}")
    print("-" * 64)
    for name, rs in rows:
        n = len(rs)
        print(
            f"{name:<18} "
            f"{statistics.median(r['tokens'] for r in rs):>8.0f} "
            f"{statistics.median(r['chars'] for r in rs):>7.0f} "
            f"{sum(r['empty'] for r in rs) / n:>6.2f} "
            f"{sum(r['truncated'] for r in rs) / n:>6.2f} "
            f"{sum(r['compliant'] for r in rs) / n:>7.2f} "
            f"{statistics.median(r['latency'] for r in rs):>7.1f}"
        )


def probe_effort(dataset: str, n: int) -> None:
    prompts = _prompts(dataset, n)
    rows = []
    for effort in EFFORTS:
        label = "(omitted)" if effort is None else effort
        rs = []
        for i, (qid, user, k) in enumerate(prompts, 1):
            rs.append(_run(user, k, effort, cfg.MAX_NEW_TOKENS))
            print(f"  {label:<10} [{i}/{len(prompts)}] {qid} {rs[-1]['tokens']}t", flush=True)
        rows.append((label, rs))
    _table(rows, f"effort @ max_tokens={cfg.MAX_NEW_TOKENS}  ({dataset}, n={n}, median)")


def probe_budget(dataset: str, n: int) -> None:
    prompts = _prompts(dataset, n)
    rows = []
    for effort in ("none", "high"):
        for budget in BUDGETS:
            rs = []
            for i, (qid, user, k) in enumerate(prompts, 1):
                rs.append(_run(user, k, effort, budget))
                print(f"  {effort}/{budget} [{i}/{len(prompts)}] {qid} {rs[-1]['tokens']}t", flush=True)
            rows.append((f"{effort} @ {budget}", rs))
    _table(rows, f"budget  ({dataset}, n={n}, median)")


#: `low` appears twice on purpose.  The endpoint is deterministic at T=0 for an
#: identical request — `effort` showed medium, high and the omitted field
#: agreeing token for token — so if the two `low` passes disagree, the axis has
#: jitter and the `low` anomaly is that jitter rather than a third state.
LEVELS: list[str | None] = ["none", "low", "low", "medium", "high", "max"]


def probe_levels(dataset: str, n: int) -> None:
    prompts = _prompts(dataset, n)
    rows = []
    seen: dict[str, int] = {}
    for effort in LEVELS:
        seen[effort] = seen.get(effort, 0) + 1
        label = f"{effort}#{seen[effort]}" if LEVELS.count(effort) > 1 else str(effort)
        rs = []
        for i, (qid, user, k) in enumerate(prompts, 1):
            rs.append(_run(user, k, effort, 2048))
            print(f"  {label:<10} [{i}/{len(prompts)}] {qid} {rs[-1]['tokens']}t", flush=True)
        rows.append((label, rs))
    _table(rows, f"levels @ max_tokens=2048  ({dataset}, n={n}, median)")
    # Medians can agree while individual queries differ, and the claim under
    # test is per-query identity — so the token sequences are compared directly.
    print("\ntoken per query (l'identita' e' per query, non sulla mediana):")
    for label, rs in rows:
        print(f"  {label:<10} {[r['tokens'] for r in rs]}")


if __name__ == "__main__":
    probe = sys.argv[1] if len(sys.argv) > 1 else "effort"
    ds = sys.argv[2] if len(sys.argv) > 2 else "open_ragbench"
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    {"effort": probe_effort, "budget": probe_budget, "levels": probe_levels}[probe](ds, count)
