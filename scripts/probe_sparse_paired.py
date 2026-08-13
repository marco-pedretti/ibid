#!/usr/bin/env python3
"""Confronto **appaiato** delle due meta' di OQ-03, sulle stesse query.

Le run archiviate non salvano i risultati per query, quindi il confronto con
loro e' marginale: due medie, nessun test. Ma entrambe le correzioni sono
**reversibili a comando**, e questo permette la misura giusta -- stesse query,
stessi chunk, una sola causa che cambia, McNemar esatto sulle discordanti.

    --vary idf          R-08. Vive nell'indice: si toglie e si rimette con
                        `update_collection`, in secondi, senza toccare un punto.
    --vary query_embed  R-09. Vive nel client: si sceglie quale funzione di
                        codifica chiamare, e l'indice non c'entra affatto.

**I due bracci non sono le stesse due cose nei due casi.** `--vary idf` misura
il passo dal nulla a R-08; `--vary query_embed` misura il passo da R-08 a R-09,
perche' l'indice ha ormai il modificatore. Sono i due gradini di una scala, non
due misure indipendenti.

Con `--vary idf` il modificatore viene **sempre** ripristinato a IDF, anche se
qualcosa va storto: lasciare l'indice a meta' migrazione falserebbe ogni misura
successiva senza dare alcun segnale.

Usage:
    python scripts/probe_sparse_paired.py --dataset open_ragbench --limit 200
    python scripts/probe_sparse_paired.py --dataset ledger --vary query_embed
    python scripts/probe_sparse_paired.py --dataset ledger --retrieval-mode hybrid
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.datasets import registry
from qdrant_client.models import Modifier, SparseVectorParams
from src.eval import retrieval_backends
from src.eval.paired import compare_paired
from src.eval.retrieval_backends import RETRIEVERS
from src.index.embed import encode_sparse, encode_sparse_query
from src.index.store import get_client


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


def _arms(client, collection, queries, depth, mode, vary) -> tuple[list, list]:
    """I due bracci: (prima della correzione, dopo la correzione).

    Entrambi passano dallo stesso identico percorso di retrieval, fusione RRF
    compresa. L'unica differenza e' la causa sotto esame.
    """
    if vary == "idf":
        try:
            _set_modifier(client, collection, Modifier.NONE)
            off = _hits(client, collection, queries, depth, mode)
            _set_modifier(client, collection, Modifier.IDF)
            on = _hits(client, collection, queries, depth, mode)
        finally:
            # L'indice torna sempre allo stato corretto, comunque sia andata.
            _set_modifier(client, collection, Modifier.IDF)
        return off, on

    # R-09 vive nel client: si sostituisce la funzione di codifica che i
    # RETRIEVERS chiamano, e l'indice resta quello che e'.
    _assert_encodings_differ()
    original = retrieval_backends.encode_sparse_query
    try:
        retrieval_backends.encode_sparse_query = encode_sparse  # lo stato pre-R-09
        off = _hits(client, collection, queries, depth, mode)
        retrieval_backends.encode_sparse_query = original
        on = _hits(client, collection, queries, depth, mode)
    finally:
        retrieval_backends.encode_sparse_query = original
    return off, on


def _assert_encodings_differ() -> None:
    """Le due codifiche producono davvero vettori diversi?

    Stessa ragione della rilettura del modificatore in `_set_modifier`: un
    esperimento in cui i due bracci coincidono restituisce "nessuna differenza",
    che e' un risultato credibile e indistinguibile da un errore. Qui il rischio
    concreto e' che `encode_sparse` e `encode_sparse_query` diventino un giorno
    la stessa funzione senza che nessuno se ne accorga.
    """
    probe = "qual e' il margine operativo consolidato del gruppo nel 2023"
    d = encode_sparse([probe], cfg.SPARSE_EMBEDDING_MODEL)[0]
    q = encode_sparse_query([probe], cfg.SPARSE_EMBEDDING_MODEL)[0]
    if list(d.values) == list(q.values):
        raise RuntimeError(
            "encode_sparse e encode_sparse_query danno lo stesso vettore: "
            "i due bracci sarebbero lo stesso braccio"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-03: le due meta', appaiate")
    p.add_argument("--dataset", choices=registry.dataset_ids(), default="open_ragbench")
    p.add_argument("--collection", default=None)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--depth", type=int, default=5)
    p.add_argument("--retrieval-mode", choices=["sparse", "hybrid"], default="sparse",
                   help="hybrid dice se il guadagno sopravvive alla fusione RRF")
    p.add_argument("--vary", choices=["idf", "query_embed"], default="idf",
                   help="idf = R-08 (indice); query_embed = R-09 (client)")
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

    names = {"idf": ("senza IDF", "con IDF"),
             "query_embed": ("query da embed()", "query da query_embed()")}[args.vary]
    print(f"{args.dataset}: {len(queries)} query, {args.retrieval_mode} @{args.depth}, "
          f"vario {args.vary}", flush=True)
    client = get_client(cfg.QDRANT_URL)

    off, on = _arms(client, collection, queries, args.depth, args.retrieval_mode, args.vary)

    for label, gold, retrieved in [
        ("chunk", gold_chunks, lambda h: set(h)),
        ("doc", gold_docs, lambda h: {c.split(":")[1] for c in h if ":" in c}),
    ]:
        a = [bool(gold[i] & retrieved(off[i])) for i in range(len(queries))]
        b = [bool(gold[i] & retrieved(on[i])) for i in range(len(queries))]
        r = compare_paired(a, b)
        print(f"\n  hit@{args.depth} a livello {label}")
        print(f"    {names[0]} {sum(a)/len(a):.4f}   {names[1]} {sum(b)/len(b):.4f}   "
              f"delta {(sum(b)-sum(a))/len(a):+.4f}")
        print(f"    solo prima {r.only_a}   solo dopo {r.only_b}   "
              f"discordanti {r.only_a + r.only_b}   p = {r.p_value:.4f}")


if __name__ == "__main__":
    main()
