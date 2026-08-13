#!/usr/bin/env python3
"""R-10, passo 2: simulazione offline di H1 (OQ-01), senza re-ingestare.

H1 dice che i chunk del routing non embeddano il proprio `section_path`, e che
questo li rende irraggiungibili. Qui si verifica **senza toccare l'indice**:
per ogni query fallita si costruisce un pool (il top-20 attuale piu' tutti i
chunk del documento d'oro), si ri-embedda ogni chunk in due varianti -- `text` e
`section_path\\n\\ntext` -- e si riordina. Poi si conta in quante query un chunk
del documento corretto entra nei primi 5 **solo** con il contesto.

**La simulazione e' ottimistica per costruzione** e va usata per falsificare H1,
non per confermarla: ri-embedda solo il pool, mentre una re-ingestione vera
cambierebbe *tutti* i chunk dell'indice, inclusi i concorrenti che qui non
vediamo. Un risultato positivo non e' il risultato -- e' il permesso di pagare
le 6-7 ore GPU del passo 3.

Il protocollo e' quello scritto in `open-questions.md` prima di guardare i dati,
ed e' eseguito com'era: la sua ragione d'essere e' proprio non poter scegliere
il test dopo aver visto i numeri.

Usage:
    python scripts/probe_section_context.py --dataset ledger --sample 50
"""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from qdrant_client.models import FieldCondition, Filter, MatchAny  # noqa: E402
from src.eval.paired import compare_paired  # noqa: E402
from src.index.embed import encode  # noqa: E402
from src.index.store import get_client, search_batch  # noqa: E402


def _cos(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return num / (na * nb) if na and nb else 0.0


def _load(dataset_id: str):
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
        gold_docs.append(sorted(docs))
    return queries, gold_docs


def _doc_chunks(client, collection, doc_ids, cap):
    flt = Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))])
    points, _ = client.scroll(collection_name=collection, scroll_filter=flt,
                              limit=cap, with_payload=True, with_vectors=False)
    return [p.payload for p in points]


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-01 H1: il contesto di sezione aiuta?")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collection", default=None)
    p.add_argument("--sample", type=int, default=50, help="query fallite da simulare")
    p.add_argument("--pool-cap", type=int, default=60, help="max chunk del documento d'oro")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    collection = args.collection or f"{args.dataset}_routed"
    queries, gold_docs = _load(args.dataset)
    client = get_client(cfg.QDRANT_URL)

    print(f"{args.dataset}: {len(queries)} query, cerco le fallite su {collection}", flush=True)
    qvecs = encode(queries, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    hits = search_batch(client, collection, qvecs, top_k=20, using="dense")

    failed = [i for i, (pts, gold) in enumerate(zip(hits, gold_docs))
              if not (set(gold) & {(p.payload or {}).get("doc_id") for p in list(pts)[:5]})]
    print(f"  fallite a top-5: {len(failed)}", flush=True)

    idxs = random.Random(args.seed).sample(failed, min(args.sample, len(failed)))
    plain_win, ctx_win, n_ctx_chunks, n_chunks = [], [], 0, 0
    cache_plain: dict[str, list[float]] = {}
    cache_ctx: dict[str, list[float]] = {}

    for k, i in enumerate(idxs, 1):
        pool = [(p.payload or {}) for p in hits[i]]
        pool += _doc_chunks(client, collection, gold_docs[i], args.pool_cap)
        seen, uniq = set(), []
        for pl in pool:
            cid = pl.get("chunk_id")
            if cid and cid not in seen:
                seen.add(cid)
                uniq.append(pl)

        # I 10.000 quesiti pescano da soli ~494 documenti, e i pool si
        # sovrappongono pesantemente: senza cache si ri-embedderebbero gli
        # stessi chunk decine di volte. Con, il costo scende di piu' di 4x --
        # cioe' si puo' permettere un campione abbastanza grande da decidere.
        todo_plain, todo_ctx = [], []
        for pl in uniq:
            cid = pl.get("chunk_id")
            sp = (pl.get("section_path") or "").strip()
            t = pl.get("text") or ""
            if sp:
                n_ctx_chunks += 1
            if cid not in cache_plain:
                todo_plain.append((cid, t))
            if cid not in cache_ctx:
                todo_ctx.append((cid, f"{sp}\n\n{t}" if sp else t))
        n_chunks += len(uniq)

        for todo, cache in [(todo_plain, cache_plain), (todo_ctx, cache_ctx)]:
            if todo:
                vs = encode([t for _, t in todo], cfg.EMBEDDING_MODEL,
                            batch_size=cfg.EMBEDDING_BATCH)
                cache.update(zip((c for c, _ in todo), vs))

        q = qvecs[i]
        gold = set(gold_docs[i])
        for cache, out in [(cache_plain, plain_win), (cache_ctx, ctx_win)]:
            scored = sorted(
                ((_cos(q, cache[pl.get("chunk_id")]), pl.get("doc_id")) for pl in uniq),
                key=lambda x: -x[0],
            )
            out.append(any(doc in gold for _, doc in scored[:5]))

        if k % 10 == 0:
            print(f"  [{k}/{len(idxs)}] senza {sum(plain_win)}  con {sum(ctx_win)}", flush=True)

    n = len(idxs)
    res = compare_paired(plain_win, ctx_win)
    print(f"\n  Query simulate: {n}   chunk nel pool: {n_chunks} "
          f"({n_ctx_chunks/max(n_chunks,1):.1%} con section_path da anteporre)")
    print("  un chunk d'oro entra nei primi 5:")
    print(f"    senza contesto  {sum(plain_win)}/{n}  ({res.rate_a:.2%})")
    print(f"    con contesto    {sum(ctx_win)}/{n}  ({res.rate_b:.2%})")
    print(f"    solo senza {res.only_a}   solo con {res.only_b}   p = {res.p_value:.4f}")
    print("\n  Soglia del protocollo: <10% delle query -> H1 falsificata, "
          "non pagare il passo 3.  >=25% -> H1 sopravvive.")
    print(f"  Guadagno netto: {(res.rate_b - res.rate_a):.2%}")


if __name__ == "__main__":
    main()
