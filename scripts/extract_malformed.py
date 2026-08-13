"""Extract real malformed citation constructs from C-01 generation dumps (C-02).

C-02 is accepted on "test sugli output malformati reali".  The T-06 parser was
written against variants imagined at the desk; this script builds the test
material from what the model actually produced, so the tests can be re-derived
when new runs land instead of being hand-copied once and left to drift.

Output: one record per *distinct* construct, with the sentence it appeared in
(the surrounding text matters — repairing a marker changes the whitespace around
it), how many times it occurred, and which runs produced it.

Two categories come out, and the second is the one worth naming.  Violations are
what the parser must repair.  `not_a_citation` records are bracketed constructs
the checker deliberately excuses — mathematical intervals like `[0,1]` — and they
are collected because a repair rule is only safe if it leaves them alone.  A
fixture holding only the things to fix cannot catch a fix that overreaches.

    python scripts/extract_malformed.py --out tests/fixtures/malformed_citations.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# The private names are the point: the fixture has to be cut with exactly the
# same blade the checker uses, or it would describe a different corpus than the
# one C-01 measured.
from src.generation.citation_format import (
    _PATTERNS,
    _is_citation_attempt,
    find_violations,
)

#: How much text to keep around a construct.  A whole answer is up to 2000
#: characters of prose that says nothing about the parser; a bare `[1] [3]` says
#: nothing about the whitespace either side.  One sentence is the unit that
#: carries both.
_SENTENCE = re.compile(r"[^.!?\n]*$")


def _window(text: str, start: int, end: int) -> str:
    """The sentence containing text[start:end]."""
    left = _SENTENCE.search(text[:start]).group(0)
    right = re.match(r"[^.!?\n]*[.!?]?", text[end:]).group(0)
    return (left + text[start:end] + right).strip()


def extract(paths: list[Path]) -> list[dict]:
    """Distinct malformed constructs across the given generation dumps."""
    seen: dict[tuple[str, str, int], dict] = {}
    for path in paths:
        run = path.stem
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["abstained"]:
                continue
            n_chunks = rec["n_chunks"]
            answer = rec["answer"]
            found = [(v.kind, v.snippet) for v in find_violations(answer, n_chunks)
                     if v.kind != "no_citation"]
            # Bracketed constructs the checker excuses. They are not defects,
            # but a repair rule that mangles them is.
            found += [("not_a_citation", m.group(0))
                      for _, pattern in _PATTERNS
                      for m in pattern.finditer(answer)
                      if not _is_citation_attempt(m.group(0))]

            for kind, snippet in found:
                key = (kind, snippet, n_chunks)
                pos = answer.find(snippet)
                entry = seen.setdefault(key, {
                    "kind": kind,
                    "snippet": snippet,
                    "n_chunks": n_chunks,
                    "text": _window(answer, pos, pos + len(snippet)) if pos >= 0 else snippet,
                    "occurrences": 0,
                    "runs": [],
                    "query_id": rec["query_id"],
                })
                entry["occurrences"] += 1
                if run not in entry["runs"]:
                    entry["runs"].append(run)
    return sorted(seen.values(), key=lambda e: (e["kind"], -e["occurrences"], e["snippet"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generations", default="eval/results/generations",
                    help="directory of C-01 generation dumps")
    ap.add_argument("--out", default="tests/fixtures/malformed_citations.jsonl")
    args = ap.parse_args()

    paths = sorted(Path(args.generations).glob("*.jsonl"))
    if not paths:
        raise SystemExit(f"no generation dumps in {args.generations}")

    records = extract(paths)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = sum(r["occurrences"] for r in records)
    print(f"{len(paths)} dumps -> {len(records)} distinct constructs, {total} occurrences")
    for kind in sorted({r["kind"] for r in records}):
        rs = [r for r in records if r["kind"] == kind]
        print(f"  {kind:16s} {len(rs):3d} distinct  {sum(r['occurrences'] for r in rs):3d} occurrences")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
