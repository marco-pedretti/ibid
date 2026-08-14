#!/usr/bin/env python3
"""R-11: quanto e' stipato un indice, e quindi quanto gli serve la ricerca esatta.

R-10 aveva trovato che la ricerca approssimata perde molto richiamo su
`ledger_routed`. R-11 ha misurato le altre tre collection e il guadagno **non
segue il numero di punti**:

    open_ragbench          18.840 punti   +0,00
    ledger                 47.110 punti   +0,37
    open_ragbench_routed   98.312 punti   +0,43
    ledger_routed         228.331 punti   +8,24

98.312 punti rendono quasi zero, 228.331 rendono otto punti. La taglia da sola
non lo spiega.

L'ipotesi e' la **densita'**: HNSW cammina in un grafo di prossimita', e per
camminare gli serve una pendenza. Se i primi cento candidati sono quasi
equidistanti dalla query, la camminata si ferma in un vicinato plausibile e non
sa che poco piu' in la' ce n'e' uno migliore. Bilanci finanziari si somigliano
tutti; articoli accademici no.

Questo script misura la pendenza: di quanto cala il punteggio scendendo nella
classifica, e quanti candidati stanno a pari merito col primo. Sono numeri che
si ottengono in un minuto e che dicono, **prima** di spendere una valutazione,
se una collection ha bisogno di `SEARCH_EXACT`.

Usage:
    python scripts/probe_index_density.py --dataset ledger
    python scripts/probe_index_density.py --collections ledger ledger_routed
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from qdrant_client.models import QueryRequest, SearchParams
from src.index.embed import encode
from src.index.store import get_client, search_batch, search_params


#: Soglia di "pari merito". E' il distacco mediano fra il chunk vincente e il
#: miglior chunk d'oro misurato in R-10 sulle query fallite: la differenza che
#: separa un successo da un fallimento su questo corpus.
TIE = 0.0090


def _exact_top5(client, coll: str, vecs: list[list[float]]) -> list[list]:
    """Il vero top-5, senza grafo. E' il metro contro cui si misura l'ANN."""
    out = []
    for start in range(0, len(vecs), 64):
        reqs = [QueryRequest(query=v, using="dense", limit=5,
                             params=SearchParams(exact=True))
                for v in vecs[start:start + 64]]
        out.extend(r.points for r in
                   client.query_batch_points(collection_name=coll, requests=reqs))
    return out


def _queries(dataset_id: str, limit: int) -> list[str]:
    out = []
    path = ROOT / "eval" / "golden" / f"{dataset_id}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        if j.get("qrels"):
            out.append(j["query_text"])
        if len(out) >= limit:
            break
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="R-11: densita' di un indice")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collections", nargs="+", default=None)
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--depth", type=int, default=100)
    args = p.parse_args()

    colls = args.collections or [args.dataset, f"{args.dataset}_routed"]
    queries = _queries(args.dataset, args.limit)
    print(f"{args.dataset}: {len(queries)} query, pari merito entro {TIE}\n")

    client = get_client(cfg.QDRANT_URL)
    vecs = encode(queries, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)

    print(f"  {'collection':<24} {'punti':>8} {'1->5':>8} {'a pari':>7} "
          f"{'recall@5':>9} {'perfette':>9}")
    for coll in colls:
        n = client.get_collection(coll).points_count
        hits = search_batch(client, coll, vecs, args.depth, using="dense",
                            params=search_params(cfg.SEARCH_EXACT, cfg.HNSW_EF))
        # Il numero che decide: quanta parte del **vero** top-5 l'ANN
        # restituisce. E' una proprieta' dell'indice, non del dataset d'oro --
        # si misura senza qrels, quindi si puo' calcolare su qualunque
        # collection prima di spenderci una valutazione.
        d5, ties, rec, perfect = [], [], [], 0
        exact_hits = _exact_top5(client, coll, vecs)
        for pts, ex in zip(hits, exact_hits):
            s = [pt.score for pt in pts]
            if len(s) < 5:
                continue
            d5.append(s[0] - s[4])
            ties.append(sum(1 for x in s if s[0] - x <= TIE))
            got = {p.id for p in list(pts)[:5]}
            want = {p.id for p in ex}
            overlap = len(got & want) / max(len(want), 1)
            rec.append(overlap)
            perfect += overlap == 1.0
        print(f"  {coll:<24} {n:>8} {statistics.median(d5):>8.4f} "
              f"{statistics.median(ties):>7.0f} {statistics.mean(rec):>9.4f} "
              f"{perfect/len(rec):>8.1%}")

    print("\n  '1->5': di quanto cala il punteggio fra il primo e il quinto. Piu' e'")
    print("  piatto, meno pendenza ha il grafo HNSW da seguire.")
    print(f"  'a pari': quanti dei primi 100 stanno entro {TIE:.4f} dal primo.")
    print("  'recall@5': quanta parte del VERO top-5 la ricerca approssimata trova.")
    print("  'perfette': query in cui lo trova tutto. E' il numero da guardare.")


if __name__ == "__main__":
    main()
