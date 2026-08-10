#!/usr/bin/env python3
"""Recompute C-01 metrics from a stored generations dump, without generating.

Why this exists: the compliance checker is a measuring instrument, and changing
it changes every number it ever produced.  Because `run_citation_eval` stores
the raw answers, a checker change can be re-evaluated against past runs for free
instead of costing another 40 minutes of GPU per dataset — and, more to the
point, instead of leaving old and new numbers silently incomparable.

It never overwrites a stored EvalRun.  The results in `eval/results/` are what
was measured with the checker of the day; this prints what the same generations
would score today, so the difference is a stated correction rather than a quiet
rewrite.

Usage:
    python scripts/rescore_citations.py                       # every dump
    python scripts/rescore_citations.py eval/results/generations/X.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.generation.citation_format import (
    COMPLIANCE_TARGET,
    VIOLATION_KINDS,
    check_format,
    summarize,
)

GENERATIONS_DIR = ROOT / "eval" / "results" / "generations"


def rescore(path: Path) -> dict:
    """Re-run the checker over a dump and return the recomputed summary."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    reports = [check_format(r["answer"], r["n_chunks"]) for r in rows]
    s = summarize(reports)
    stored_compliant = sum(1 for r in rows if r["compliant"])
    stored_scored = sum(1 for r in rows if not r["abstained"])
    return {
        "path": path,
        "n": len(rows),
        "stored_rate": stored_compliant / stored_scored if stored_scored else 0.0,
        "summary": s,
        "rows": rows,
        "reports": reports,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Recompute C-01 metrics from stored generations")
    p.add_argument("dumps", nargs="*", type=Path,
                   help="JSONL dumps (default: all in eval/results/generations)")
    p.add_argument("--show-changed", action="store_true",
                   help="print the answers whose verdict changed")
    args = p.parse_args()

    dumps = args.dumps or sorted(GENERATIONS_DIR.glob("*.jsonl"))
    if not dumps:
        print(f"No dumps found in {GENERATIONS_DIR.relative_to(ROOT)}")
        return

    for path in dumps:
        r = rescore(path)
        s = r["summary"]
        delta = s.rate - r["stored_rate"]
        verdict = "PASS" if s.meets_target else "FAIL"
        print(f"\n{path.name}")
        print(f"  {r['n']} generazioni, {s.n_abstained} astensioni, {s.n_scored} valutate")
        print(f"  conformita: registrata {r['stored_rate']:.4f} -> ricalcolata {s.rate:.4f} "
              f"({delta:+.4f})")
        print(f"  CI95 inf {s.rate_lower95:.4f} -> {verdict} (soglia {COMPLIANCE_TARGET})")
        offenders = [(k, s.kind_rates[k]) for k in VIOLATION_KINDS if s.kind_rates[k] > 0]
        for kind, rate in sorted(offenders, key=lambda x: -x[1]):
            print(f"    {kind:<16} {rate:.3f}")

        if args.show_changed:
            for row, rep in zip(r["rows"], r["reports"]):
                if row["compliant"] != rep.compliant:
                    was, now = row["compliant"], rep.compliant
                    print(f"    cambiato {row['query_id'][:8]}: {was} -> {now}  "
                          f"{sorted(rep.kinds)}")


if __name__ == "__main__":
    main()
