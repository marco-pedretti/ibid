#!/usr/bin/env python3
"""Test appaiato fra due run di retrieval, dai loro dump per query (Q-02).

Il confronto fra due medie dice che un tasso e' salito. Non dice se sia salito
**su queste query** o se sia il caso: per quello servono i risultati per query e
McNemar esatto sulle discordanti (§15).

Fino a Q-02 le run di retrieval non li salvavano. In R-08 il confronto con le
run archiviate e' stato percio' marginale, e McNemar e' stato possibile solo
perche' lo stato pre-correzione era **riproducibile a comando** -- si toglieva e
si rimetteva `modifier=IDF` sull'indice. Una fortuna, non un metodo: la prossima
correzione potrebbe non essere reversibile, e allora l'unica prova sarebbe il
dump di prima.

I dump si confrontano **solo se coprono le stesse query**: lo script lo verifica
e si rifiuta altrimenti, invece di intersecare in silenzio e riportare un numero
calcolato su una popolazione che nessuno ha scelto.

Usage:
    python scripts/compare_retrieved.py A.jsonl B.jsonl
    python scripts/compare_retrieved.py A.jsonl B.jsonl --depth 10 --level doc
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.eval.dump import read_jsonl
from src.eval.paired import compare_paired


def _hit(record: dict, depth: int, level: str) -> bool:
    """La query ha trovato qualcosa di rilevante entro `depth`?"""
    gold = set(record["gold_chunk_ids"])
    got = set(record["chunk_ids"][:depth])
    if level == "doc":
        # Il `doc_id` si ricava dal `chunk_id`: salvarlo nel dump sarebbe stato
        # un megabyte per run per non dire niente di nuovo.
        gold = {c.split(":")[1] for c in gold if ":" in c}
        got = {c.split(":")[1] for c in got if ":" in c}
    return bool(gold & got)


def main() -> None:
    p = argparse.ArgumentParser(description="Q-02: due run di retrieval, appaiate")
    p.add_argument("a", type=Path, help="dump della run di riferimento")
    p.add_argument("b", type=Path, help="dump della run sotto esame")
    p.add_argument("--depth", type=int, default=5)
    p.add_argument("--level", choices=["chunk", "doc"], default="chunk")
    p.add_argument("--show", type=int, default=0,
                   help="stampa N query discordanti per lato, da leggere")
    args = p.parse_args()

    rows_a = {r["query_id"]: r for r in read_jsonl(args.a)}
    rows_b = {r["query_id"]: r for r in read_jsonl(args.b)}

    if set(rows_a) != set(rows_b):
        only_a, only_b = len(set(rows_a) - set(rows_b)), len(set(rows_b) - set(rows_a))
        raise SystemExit(
            f"I due dump non coprono le stesse query: {only_a} solo in A, "
            f"{only_b} solo in B. Un test appaiato su un'intersezione scelta dal "
            "caso non e' un test appaiato."
        )

    qids = sorted(rows_a)
    hits_a = [_hit(rows_a[q], args.depth, args.level) for q in qids]
    hits_b = [_hit(rows_b[q], args.depth, args.level) for q in qids]
    res = compare_paired(hits_a, hits_b)

    print(f"{len(qids)} query,  hit@{args.depth} a livello {args.level}")
    print(f"  A {args.a.name}   {res.rate_a:.4f}")
    print(f"  B {args.b.name}   {res.rate_b:.4f}")
    print(f"  delta {res.delta:+.4f}")
    print(f"  solo A {res.only_a}   solo B {res.only_b}   "
          f"discordanti {res.discordant}   p = {res.p_value:.4f}")
    print(f"  -> {res.verdict()}")

    if args.show:
        for label, cond in (("solo A", lambda i: hits_a[i] and not hits_b[i]),
                            ("solo B", lambda i: hits_b[i] and not hits_a[i])):
            picked = [qids[i] for i in range(len(qids)) if cond(i)][: args.show]
            if picked:
                print(f"\n  {label}:")
                for q in picked:
                    print(f"    {q}  {rows_a[q]['query_text'][:70]}")


if __name__ == "__main__":
    main()
