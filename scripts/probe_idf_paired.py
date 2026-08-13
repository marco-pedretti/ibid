#!/usr/bin/env python3
"""R-08: confronto **appaiato** con e senza `modifier=IDF`, sulle stesse query.

Le run archiviate del 2026-08-07 non salvano i risultati per query, quindi il
confronto con loro e' marginale: due medie, nessun test. Ma lo stato pre-R-08 e'
riproducibile, perche' l'IDF vive nella configurazione dell'indice e non nei
vettori -- si toglie e si rimette con `update_collection`, in secondi, senza
toccare un solo punto.

Quindi qui si misura davvero cio' che serve: le stesse query, gli stessi chunk,
una sola causa che cambia, e McNemar esatto sulle query discordanti.

Il modificatore viene **sempre** ripristinato a IDF, anche se qualcosa va storto:
lasciare l'indice a meta' migrazione falserebbe ogni misura successiva senza dare
alcun segnale.

Usage:
    python scripts/probe_idf_paired.py --dataset open_ragbench --limit 200
    python scripts/probe_idf_paired.py --dataset ledger --depth 5
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from qdrant_client.models import Modifier, SparseVectorParams  # noqa: E402
from src.eval.paired import compare_paired  # noqa: E402
from src.eval.retrieval_backends import RETRIEVERS  # noqa: E402
from src.index.store import get_client  # noqa: E402


def _set_modifier(client, name: str, modifier: Modifier) -> None:
    """Cambia il modificatore e **rilegge** che sia cambiato davvero.

    `Modifier.NONE`, non `None`: in `update_collection` un campo Python `None`
    vuol dire "non toccare", non "azzera". La prima versione di questo script
    spegneva l'IDF con `None` e otteneva zero query discordanti su 200 -- il
    risultato perfetto di un esperimento in cui i due bracci erano lo stesso
    braccio. La rilettura sta qui perche' quel modo di fallire non da' errori.
    """
    client.update_collection(
        collection_name=name,
        sparse_vectors_config={"sparse": SparseVectorParams(modifier=modifier)},
    )
    got = (client.get_collection(name).config.params.sparse_vectors or {}).get("sparse")
    if getattr(got, "modifier", None) != modifier:
        raise RuntimeError(
            f"{name}: chiesto modifier={modifier}, l'indice dice {getattr(got, 'modifier', None)}"
        )


def _hits(client, collection, texts, depth: int, mode: str) -> list[list[str]]:
    """chunk_id recuperati per query, in ordine.

    Passa dagli stessi `RETRIEVERS` che usa `scripts/eval.py`, invece di
    rifare la ricerca a mano: in `hybrid` la fusione RRF e' cio' che decide se
    il guadagno dello sparso sopravvive, e riscriverla qui misurerebbe la mia
    copia della fusione, non quella del sistema.
    """
    cands = RETRIEVERS[mode](client, collection, texts, depth, None)
    return [c.chunk_ids for c in cands]


def main() -> None:
    p = argparse.ArgumentParser(description="R-08: IDF on/off, appaiato")
    p.add_argument("--dataset", choices=["open_ragbench", "ledger"], default="open_ragbench")
    p.add_argument("--collection", default=None)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--depth", type=int, default=5)
    p.add_argument("--retrieval-mode", choices=["sparse", "hybrid"], default="sparse",
                   help="hybrid dice se il guadagno sopravvive alla fusione RRF")
    args = p.parse_args()

    collection = args.collection or args.dataset
    golden = ROOT / "eval" / "golden" / f"{args.dataset}.jsonl"

    queries, gold_chunks, gold_docs = [], [], []
    for line in golden.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        if not j.get("qrels"):
            continue
        queries.append(j["query_text"])
        ids = {q["chunk_id"] for q in j["qrels"] if q["relevance"] > 0}
        gold_chunks.append(ids)
        gold_docs.append({c.split(":")[1] for c in ids if ":" in c})
        if args.limit and len(queries) >= args.limit:
            break

    print(f"{args.dataset}: {len(queries)} query, {args.retrieval_mode} @{args.depth}", flush=True)
    client = get_client(cfg.QDRANT_URL)

    try:
        _set_modifier(client, collection, Modifier.NONE)
        off = _hits(client, collection, queries, args.depth, args.retrieval_mode)
        _set_modifier(client, collection, Modifier.IDF)
        on = _hits(client, collection, queries, args.depth, args.retrieval_mode)
    finally:
        # L'indice torna sempre allo stato corretto, comunque sia andata.
        _set_modifier(client, collection, Modifier.IDF)

    for label, gold, retrieved in [
        ("chunk", gold_chunks, lambda h: set(h)),
        ("doc", gold_docs, lambda h: {c.split(":")[1] for c in h if ":" in c}),
    ]:
        a = [bool(gold[i] & retrieved(off[i])) for i in range(len(queries))]
        b = [bool(gold[i] & retrieved(on[i])) for i in range(len(queries))]
        r = compare_paired(a, b)
        print(f"\n  hit@{args.depth} a livello {label}")
        print(f"    senza IDF {sum(a)/len(a):.4f}   con IDF {sum(b)/len(b):.4f}   "
              f"delta {(sum(b)-sum(a))/len(a):+.4f}")
        print(f"    solo senza {r.only_a}   solo con {r.only_b}   "
              f"discordanti {r.only_a + r.only_b}   p = {r.p_value:.4f}")


if __name__ == "__main__":
    main()
