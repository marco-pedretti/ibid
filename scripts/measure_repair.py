#!/usr/bin/env python3
"""How much of the raw non-compliance the parser recovers (C-02).

C-01 measured the prompt: compliance of the model's raw output.  C-02 measures
the parser: compliance after `citations.parse` has repaired what it knows how to
repair.  The gap between the two is the parser's contribution, and it is the only
number that says whether C-02 did anything.

The two must not be confused, which is why they are computed by different tools
against the same stored generations.  Running the repair before the C-01 checker
would report ~100% by construction and say nothing about either.

Reported per `dataset_id`, per ROADMAP §14 — a repair rate averaged over a corpus
that cites `[n]` and one that does not is a number about neither.  `dataset_id`
comes from the chunk ids in each record, not from the filename.

Usage:
    python scripts/measure_repair.py
    python scripts/measure_repair.py eval/results/generations/X.jsonl
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.generation.citation_format import VIOLATION_KINDS, check_format  # noqa: E402
from src.generation.citations import parse  # noqa: E402

GENERATIONS_DIR = ROOT / "eval" / "results" / "generations"


def _dataset_of(record: dict) -> str:
    """Chunk ids are `{dataset_id}:{doc_id}:{n}` — the record's own provenance,
    which a renamed file cannot contradict."""
    ids = record.get("chunk_ids") or []
    return ids[0].split(":")[0] if ids else "unknown"


class Tally:
    def __init__(self) -> None:
        self.scored = 0
        self.raw_ok = 0
        self.repaired_ok = 0
        self.fixed_by_kind: defaultdict[str, int] = defaultdict(int)
        self.left_by_kind: defaultdict[str, int] = defaultdict(int)

    def add(self, answer: str, n_chunks: int) -> None:
        before = check_format(answer, n_chunks)
        if before.abstained:
            return
        after = check_format(parse(answer, n_chunks), n_chunks)
        self.scored += 1
        self.raw_ok += before.compliant
        self.repaired_ok += after.compliant
        for kind in before.kinds:
            if kind not in after.kinds:
                self.fixed_by_kind[kind] += 1
        for kind in after.kinds:
            self.left_by_kind[kind] += 1

    @property
    def raw_rate(self) -> float:
        return self.raw_ok / self.scored if self.scored else 0.0

    @property
    def repaired_rate(self) -> float:
        return self.repaired_ok / self.scored if self.scored else 0.0

    @property
    def recovered(self) -> float:
        """Share of the non-compliant answers that the parser made compliant.

        Reported next to the two rates because a +2 point gain means something
        different when 3% was broken than when 30% was.
        """
        broken = self.scored - self.raw_ok
        return (self.repaired_ok - self.raw_ok) / broken if broken else 0.0


def _report(label: str, t: Tally) -> None:
    print(f"\n{label}")
    print(f"  {t.scored} risposte valutate (astensioni escluse)")
    print(f"  conformita  grezza {t.raw_rate:.4f}  ->  dopo parse {t.repaired_rate:.4f}  "
          f"({t.repaired_rate - t.raw_rate:+.4f})")
    print(f"  non conformi recuperate: {t.repaired_ok - t.raw_ok}/{t.scored - t.raw_ok}"
          f"  ({t.recovered:.1%})")
    fixed = [(k, t.fixed_by_kind[k]) for k in VIOLATION_KINDS if t.fixed_by_kind[k]]
    left = [(k, t.left_by_kind[k]) for k in VIOLATION_KINDS if t.left_by_kind[k]]
    if fixed:
        print("  riparati   " + "  ".join(f"{k}={n}" for k, n in fixed))
    if left:
        print("  residui    " + "  ".join(f"{k}={n}" for k, n in left))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dumps", nargs="*", type=Path,
                   help="JSONL dumps (default: all in eval/results/generations)")
    args = p.parse_args()

    dumps = args.dumps or sorted(GENERATIONS_DIR.glob("*.jsonl"))
    if not dumps:
        raise SystemExit(f"No dumps found in {GENERATIONS_DIR}")

    per_dataset: defaultdict[str, Tally] = defaultdict(Tally)
    for path in dumps:
        per_run = Tally()
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            per_run.add(rec["answer"], rec["n_chunks"])
            per_dataset[_dataset_of(rec)].add(rec["answer"], rec["n_chunks"])
        _report(path.name, per_run)

    print("\n" + "=" * 60)
    print("PER DATASET (run dello stesso dataset messe insieme)")
    for dataset in sorted(per_dataset):
        _report(dataset, per_dataset[dataset])


if __name__ == "__main__":
    main()
