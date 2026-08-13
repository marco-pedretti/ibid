#!/usr/bin/env python3
"""R-10, passo 1: a che rango compare il documento giusto (OQ-01, H2a).

H2a dice: i chunk giusti sono nell'indice, ma i vicini li spingono fuori dal
top-5. Confrontare `doc_R@5` con `doc_R@10` risponde male a questa domanda --
dice solo se guardando il doppio si recupera qualcosa, e se la risposta e' "un
po'" non si impara niente.

La domanda giusta e': **per le query che il routing sbaglia, dove sta il
documento corretto?** Se sta a rango 6-20, e' un problema di ordinamento e si
compra con un reranker. Se non compare nemmeno a rango 100, non e' ordinamento:
il chunk giusto non e' rappresentato in modo da farsi trovare, e nessuna
profondita' lo salva.

Le due letture portano a lavori completamente diversi, e la media non le
distingue.

Usage:
    python scripts/probe_routing_depth.py --dataset ledger
    python scripts/probe_routing_depth.py --dataset ledger --deep 200 --limit 2000
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from src.eval.paired import compare_paired  # noqa: E402
from src.index.embed import encode  # noqa: E402
from src.index.store import get_client, search_batch  # noqa: E402

#: Fasce di rango riportate. Il confine a 20 e' quello che un reranker
#: raggiunge con RERANK_FETCH_K senza cambiare niente altro.
BANDS = [(1, 5), (6, 10), (11, 20), (21, 50), (51, 100)]


def _load(dataset_id: str, limit: int | None):
    queries, gold_docs = [], []
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
        gold_docs.append(docs)
        if limit and len(queries) >= limit:
            break
    return queries, gold_docs


def _first_gold_rank(client, collection, vecs, gold_docs, deep):
    """Rango del primo chunk di un documento corretto (o None), piu' due diagnosi.

    `distinct` conta quanti **documenti diversi** compaiono nei primi 5. Serve a
    escludere un confondente che nessuna metrica di recall vede: `ledger_routed`
    ha 4,8 volte i chunk di `ledger`, e con chunk piu' fini i primi 5 possono
    venire tutti dallo stesso documento. In quel caso il doc-recall@5 calerebbe
    per una ragione puramente combinatoria -- meno documenti guardati a parita'
    di posti -- e non perche' i chunk siano rappresentati peggio.

    Sono due diagnosi con due rimedi opposti: se e' diversita', si recupera
    guardando piu' in profondita' o deduplicando per documento; se e'
    rappresentazione, non si recupera affatto senza re-ingestare.
    """
    hits = search_batch(client, collection, vecs, top_k=deep, using="dense")
    ranks, distinct, ctypes = [], [], []
    for points, gold in zip(hits, gold_docs):
        rank = None
        for i, p in enumerate(points, 1):
            if (p.payload or {}).get("doc_id") in gold:
                rank = i
                break
        ranks.append(rank)
        top5 = list(points)[:5]
        distinct.append(len({(p.payload or {}).get("doc_id") for p in top5}))
        ctypes.append(Counter((p.payload or {}).get("content_type") for p in top5))
    return ranks, distinct, ctypes


def _report(label: str, ranks: list[int | None]) -> None:
    n = len(ranks)
    print(f"\n  {label}")
    cumulative = 0
    for lo, hi in BANDS:
        c = sum(1 for r in ranks if r is not None and lo <= r <= hi)
        cumulative += c
        print(f"    rango {lo:>3}-{hi:<3}  {c:>5}  ({c/n:6.2%})   cumulato {cumulative/n:6.2%}")
    missing = sum(1 for r in ranks if r is None)
    print(f"    mai trovato   {missing:>5}  ({missing/n:6.2%})")


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-01 H2a: dove sta il documento giusto")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--generic-collection", default=None)
    p.add_argument("--routed-collection", default=None)
    p.add_argument("--deep", type=int, default=100, help="quanto scendere a cercarlo")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    generic = args.generic_collection or args.dataset
    routed = args.routed_collection or f"{args.dataset}_routed"

    queries, gold_docs = _load(args.dataset, args.limit)
    print(f"{args.dataset}: {len(queries)} query, cerco fino a rango {args.deep}", flush=True)

    client = get_client(cfg.QDRANT_URL)
    vecs = encode(queries, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)

    g, g_dist, g_ct = _first_gold_rank(client, generic, vecs, gold_docs, args.deep)
    r, r_dist, r_ct = _first_gold_rank(client, routed, vecs, gold_docs, args.deep)

    _report(f"{generic} (generic)", g)
    _report(f"{routed} (routed)", r)

    print("\n  === Documenti distinti nei primi 5 (il confondente combinatorio) ===")
    for label, dist in [(generic, g_dist), (routed, r_dist)]:
        c = Counter(dist)
        mean = sum(dist) / len(dist)
        spread = "  ".join(f"{k}:{c.get(k, 0)}" for k in range(1, 6))
        print(f"    {label:<16} media {mean:.2f}   distribuzione  {spread}")

    print("\n  === content_type dei primi 5 ===")
    for label, cts in [(generic, g_ct), (routed, r_ct)]:
        tot = Counter()
        for c in cts:
            tot.update(c)
        n = sum(tot.values())
        share = "  ".join(f"{k}:{v/n:.1%}" for k, v in tot.most_common())
        print(f"    {label:<16} {share}")

    # La domanda di H2a, posta solo dove il routing sbaglia.
    failed = [i for i, rank in enumerate(r) if rank is None or rank > 5]
    print(f"\n  === Le {len(failed)} query che il routing sbaglia a top-5 ===")
    sub = [r[i] for i in failed]
    _report("dove sta il documento corretto in routed", sub)

    recoverable = sum(1 for x in sub if x is not None and x <= 20)
    print(f"\n    recuperabili con un reranker a profondita' 20: {recoverable}/{len(failed)} "
          f"({recoverable/len(failed):.2%})")
    print(f"    irrecuperabili a qualunque profondita' <= {args.deep}: "
          f"{sum(1 for x in sub if x is None)}/{len(failed)} "
          f"({sum(1 for x in sub if x is None)/len(failed):.2%})")

    # E il confronto appaiato che OQ-01 chiede: stessa query, due pipeline.
    for depth in (5, 10, 20):
        a = [x is not None and x <= depth for x in g]
        b = [x is not None and x <= depth for x in r]
        res = compare_paired(a, b)
        print(f"\n  hit@{depth} doc:  generic {res.rate_a:.4f}  routed {res.rate_b:.4f}  "
              f"delta {res.delta:+.4f}")
        print(f"    solo generic {res.only_a}   solo routed {res.only_b}   p = {res.p_value:.4f}")

    counts = Counter(x for x in r if x is not None and x <= 5)
    print(f"\n  (controllo: routed trova a rango 1 in {counts.get(1, 0)} query)")


if __name__ == "__main__":
    main()
