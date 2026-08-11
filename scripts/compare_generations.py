#!/usr/bin/env python3
"""Paired comparison of two generation runs over the same golden queries.

C-07 compares reasoning on against off; C-06 will compare model sizes.  Both are
the same question — *did this switch change anything* — and neither is answered
by putting two aggregate rates side by side, because two rates cannot say
whether their difference survives the sampling error of the query set.

`src/eval/paired.py` holds the test (exact McNemar) and the argument for it: only
the queries where the two runs disagree carry information.  It also says why the
E-07 noise floor is the wrong instrument *for retrieval* — and, in the same
breath, why it is the right one here: generation samples, so the same
configuration run twice does not reproduce itself query by query.

**Hence the two comparisons this script is meant to be run for.**  One between
the arms, and one between a run and a replicate of itself.  The second is not
optional: ROADMAP §14 forbids declaring an improvement without comparing it
against the noise baseline, and for generation that baseline has to be measured,
not assumed to be zero.

Usage:
    python scripts/compare_generations.py --a <off>.jsonl --b <on>.jsonl
    python scripts/compare_generations.py --a <off>.jsonl --b <off-replicate>.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.paired import compare_paired  # noqa: E402


def load(path: Path) -> dict[str, dict]:
    """Generations keyed by query_id.

    A partial file is refused rather than scored: `.partial` means the run did
    not reach the end, and a comparison over a prefix of one arm and the whole
    of the other is not paired at all.
    """
    if path.suffix == ".partial" or path.name.endswith(".jsonl.partial"):
        raise SystemExit(f"{path.name} is a partial run — no verdict from an unfinished arm.")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["query_id"]: r for r in records}


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _arm_summary(name: str, recs: list[dict]) -> None:
    scored = [r for r in recs if not r["abstained"]]
    print(
        f"  {name:<10} n={len(recs):<4} astenute={sum(r['abstained'] for r in recs):<4} "
        f"format={sum(r['compliant'] for r in scored) / len(scored) if scored else 0:.4f}  "
        f"lat_p50={_median([r['latency_s'] for r in recs]):.1f}s  "
        f"tok_p50={_median([float(r['completion_tokens']) for r in recs]):.0f}  "
        f"troncate={sum(r['finish_reason'] == 'length' for r in recs)}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="paired comparison of two generation runs")
    p.add_argument("--a", required=True, type=Path, help="baseline arm JSONL")
    p.add_argument("--b", required=True, type=Path, help="arm under test JSONL")
    p.add_argument("--label-a", default="A")
    p.add_argument("--label-b", default="B")
    args = p.parse_args()

    a, b = load(args.a), load(args.b)
    shared = sorted(set(a) & set(b))
    if not shared:
        raise SystemExit("The two runs share no query_id — different query sets.")
    if len(shared) != len(a) or len(shared) != len(b):
        # Not fatal, but it changes what the verdict is about, so it is stated.
        print(f"[warn] {len(a)} vs {len(b)} query, {len(shared)} in comune: confronto sulle comuni")

    print(f"\n=== {args.label_a} vs {args.label_b} - {len(shared)} query appaiate ===")
    _arm_summary(args.label_a, [a[q] for q in shared])
    _arm_summary(args.label_b, [b[q] for q in shared])

    # Abstained answers are excluded from the format comparison for the reason
    # C-01 excludes them: "Insufficient information." carries no citation, and
    # scoring it as a format failure would blame the prompt for a refusal.  A
    # query is paired only when *both* arms answered it.
    paired_ids = [q for q in shared if not a[q]["abstained"] and not b[q]["abstained"]]
    n_split = len(shared) - len(paired_ids)
    if n_split:
        print(f"  ({n_split} query astenute da un solo braccio, fuori dal test appaiato)")

    result = compare_paired(
        [a[q]["compliant"] for q in paired_ids],
        [b[q]["compliant"] for q in paired_ids],
    )
    print(f"\nformat_compliance  {args.label_a} {result.rate_a:.4f} -> "
          f"{args.label_b} {result.rate_b:.4f}   delta {result.delta:+.4f}")
    print(f"  discordanti: solo {args.label_a} {result.only_a}, "
          f"solo {args.label_b} {result.only_b}  (su {result.n})")
    print(f"  {result.verdict()}")


if __name__ == "__main__":
    main()
