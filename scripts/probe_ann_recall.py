#!/usr/bin/env python3
"""R-10: quanta parte del regresso del routing e' HNSW che non trova (OQ-01).

Il passo 1 aveva lasciato una contraddizione. Per le query in cui il documento
d'oro non compare **nemmeno a rango 100**, il suo miglior chunk sta appena 0,0097
di coseno sotto il vincitore, e i concorrenti dentro quel distacco sono una
manciata. Un chunk cosi' dovrebbe stare verso rango 7, non oltre il centesimo.

L'unica spiegazione che regge e' che la ricerca **non ci arrivi**. Qdrant cerca
con HNSW, che e' approssimato: percorre un grafo, e se il vicinato e' denso puo'
non raggiungere candidati che meriterebbero il podio. `ledger_routed` ha 228.331
punti contro i 47.110 di `ledger`, tutti stipati in una banda di similarita'
strettissima -- le condizioni peggiori per un grafo di prossimita'.

Questo script confronta la ricerca approssimata con quella **esatta**, che il
grafo non lo usa affatto. La differenza fra le due e' il richiamo perso
dall'indice, e non ha niente a che vedere con la qualita' dei chunk.

E' una misura che non costa niente provare e che, se positiva, si adotta a query
time: `hnsw_ef` e `exact` sono parametri di ricerca, non di costruzione. Nessuna
re-ingestione.

Usage:
    python scripts/probe_ann_recall.py --dataset ledger
    python scripts/probe_ann_recall.py --dataset ledger --limit 3000 --sweep
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from qdrant_client.models import QueryRequest, SearchParams  # noqa: E402
from src.eval.paired import compare_paired  # noqa: E402
from src.index.embed import encode  # noqa: E402
from src.index.store import get_client  # noqa: E402

_BATCH = 64


def _load(dataset_id: str, limit: int | None):
    queries, gold = [], []
    path = ROOT / "eval" / "golden" / f"{dataset_id}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        if not j.get("qrels"):
            continue
        docs = {q["chunk_id"].split(":")[1] for q in j["qrels"]
                if q["relevance"] > 0 and ":" in q["chunk_id"]}
        if not docs:
            continue
        queries.append(j["query_text"])
        gold.append(docs)
        if limit and len(queries) >= limit:
            break
    return queries, gold


def _hits(client, coll, vecs, gold, params, top_k) -> tuple[list[bool], float]:
    out, t0 = [], time.time()
    for start in range(0, len(vecs), _BATCH):
        idx = range(start, min(start + _BATCH, len(vecs)))
        reqs = [QueryRequest(query=vecs[i], using="dense", limit=top_k,
                             with_payload=True, params=params) for i in idx]
        res = client.query_batch_points(collection_name=coll, requests=reqs)
        for i, r in zip(idx, res):
            out.append(bool(gold[i] & {(p.payload or {}).get("doc_id") for p in r.points}))
    return out, time.time() - t0


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-01: richiamo perso da HNSW")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collections", nargs="+", default=None,
                   help="default: <dataset> e <dataset>_routed")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sweep", action="store_true", help="aggiunge ef=128 e ef=2048")
    args = p.parse_args()

    colls = args.collections or [args.dataset, f"{args.dataset}_routed"]
    queries, gold = _load(args.dataset, args.limit)
    print(f"{args.dataset}: {len(queries)} query, doc hit@{args.top_k}\n", flush=True)

    client = get_client(cfg.QDRANT_URL)
    vecs = encode(queries, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)

    configs = [("approssimata (default)", None)]
    if args.sweep:
        configs.append(("ef=128", SearchParams(hnsw_ef=128)))
    configs.append(("ef=512", SearchParams(hnsw_ef=512)))
    if args.sweep:
        configs.append(("ef=2048", SearchParams(hnsw_ef=2048)))
    configs.append(("ESATTA", SearchParams(exact=True)))

    baselines = {}
    for coll in colls:
        n = client.get_collection(coll).points_count
        print(f"=== {coll}  ({n} punti) ===")
        base = None
        for label, params in configs:
            hits, dt = _hits(client, coll, vecs, gold, params, args.top_k)
            rate = sum(hits) / len(hits)
            extra = ""
            if base is None:
                base = hits
            else:
                r = compare_paired(base, hits)
                extra = (f"   solo prima {r.only_a}, solo dopo {r.only_b}, "
                         f"p = {r.p_value:.4f}")
            print(f"  {label:<22} {rate:.4f}   {dt/len(vecs)*1000:4.1f} ms/query{extra}")
        baselines[coll] = base
        print()

    if len(colls) == 2:
        # Il numero che serve: quanto del divario fra le due pipeline e'
        # richiamo perso dall'indice, e quanto resta da spiegare altrove.
        a, b = colls
        ex = {}
        for coll in colls:
            hits, _ = _hits(client, coll, vecs, gold, SearchParams(exact=True), args.top_k)
            ex[coll] = sum(hits) / len(hits)
        app = {c: sum(baselines[c]) / len(baselines[c]) for c in colls}
        gap_app = app[a] - app[b]
        gap_ex = ex[a] - ex[b]
        print(f"  divario {a} - {b}")
        print(f"    con ricerca approssimata  {gap_app:+.4f}")
        print(f"    con ricerca esatta        {gap_ex:+.4f}")
        quota = gap_app - gap_ex
        # La percentuale ha senso solo se il divario e' un regresso vero da
        # spiegare. Con un divario minuscolo o di segno opposto -- cioe' dove il
        # routing *guadagna* -- "il 72% del divario" e' un rapporto fra rumori,
        # e stamparlo inviterebbe a leggerlo come su LEDGER. Su open_ragbench
        # questa riga e' comparsa una volta a -72,2% e non voleva dire niente.
        if gap_app > 0.02:
            print(f"    quota imputabile a HNSW   {quota:+.4f}  "
                  f"({quota/gap_app:.1%} del divario)")
        else:
            print(f"    quota imputabile a HNSW   {quota:+.4f}  "
                  f"(divario troppo piccolo per una percentuale)")


if __name__ == "__main__":
    main()
