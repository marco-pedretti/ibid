#!/usr/bin/env python3
"""Test appaiato fra due run di baseline, dalle loro risposte per query (Q-02).

E-04 (prompt permissivo) e E-05 (prompt severo) sono la stessa domanda posta due
volte con istruzioni diverse, e il risultato che il progetto riporta -- il tasso
di risposte corrette che cala dal 45% al 17% -- e' finora **un'inferenza dai
totali**: due percentuali, e nessun modo di sapere se le corrette del permissivo
siano *le stesse* di quelle del severo.

Con le risposte per query diventa un test appaiato: quante query solo A azzecca,
quante solo B, e se la sproporzione sia piu' grande di quanto il caso produrrebbe
(McNemar esatto, §15).

Serve anche a leggere i casi, che e' la parte che qui ha ribaltato piu' di una
conclusione: `--show` stampa le query discordanti con le due risposte affiancate.

Usage:
    python scripts/compare_baselines.py A.jsonl B.jsonl
    python scripts/compare_baselines.py A.jsonl B.jsonl --outcome abstained --show 5
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.dump import aligned, read_jsonl
from src.eval.paired import compare_paired


def main() -> None:
    p = argparse.ArgumentParser(description="Q-02: due baseline, appaiati")
    p.add_argument("a", type=Path, help="dump della run di riferimento (es. E-04)")
    p.add_argument("b", type=Path, help="dump della run sotto esame (es. E-05)")
    p.add_argument("--outcome", choices=["correct", "abstained", "wrong"],
                   default="correct", help="quale esito si conta come successo")
    p.add_argument("--show", type=int, default=0,
                   help="stampa N query discordanti per lato, con le due risposte")
    args = p.parse_args()

    rows_a = {r["query_id"]: r for r in read_jsonl(args.a)}
    rows_b = {r["query_id"]: r for r in read_jsonl(args.b)}
    try:
        qids = aligned(rows_a, rows_b)
    except ValueError as e:
        raise SystemExit(f"{e}. Un test appaiato vuole la stessa popolazione.") from None

    hits_a = [rows_a[q]["verdict"] == args.outcome for q in qids]
    hits_b = [rows_b[q]["verdict"] == args.outcome for q in qids]
    res = compare_paired(hits_a, hits_b)

    print(f"{len(qids)} query,  esito contato: {args.outcome}")
    print(f"  A {args.a.name}   {res.rate_a:.4f}")
    print(f"  B {args.b.name}   {res.rate_b:.4f}")
    print(f"  delta {res.delta:+.4f}")
    print(f"  solo A {res.only_a}   solo B {res.only_b}   "
          f"discordanti {res.discordant}   p = {res.p_value:.4f}")
    print(f"  -> {res.verdict()}")

    # Quante query il giudice non ha nemmeno visto: sull'insieme non
    # rispondibile `wrong` e' una conseguenza logica, non un parere, e leggerlo
    # come un giudizio sarebbe un errore.
    unjudged = sum(1 for q in qids if not rows_a[q].get("judged", True))
    if unjudged:
        print(f"  ({unjudged} query non giudicate dal modello giudice)")

    if not args.show:
        return
    for label, cond in (("solo A", lambda i: hits_a[i] and not hits_b[i]),
                        ("solo B", lambda i: hits_b[i] and not hits_a[i])):
        picked = [qids[i] for i in range(len(qids)) if cond(i)][: args.show]
        if not picked:
            continue
        print(f"\n=== {label} ===")
        for q in picked:
            print(f"\n  {q}")
            print(f"    domanda: {rows_a[q]['query_text'][:100]}")
            print(f"    A ({rows_a[q]['verdict']}): {rows_a[q]['response'][:160]}")
            print(f"    B ({rows_b[q]['verdict']}): {rows_b[q]['response'][:160]}")


if __name__ == "__main__":
    main()
