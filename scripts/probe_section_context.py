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

## Il terzo braccio, e perche' senza non si conclude niente

Il passo 1 ha stabilito che i fallimenti del routing sono **quasi-pareggi**: il
chunk d'oro perde per 0,0090 di coseno, e l'intero top-5 sta dentro 0,0085. In
un regime cosi', *qualunque* perturbazione consistente ribalta una frazione di
casi -- e anteporre un titolo sposta l'embedding molto piu' di nove millesimi.

Quindi un risultato positivo con due soli bracci e' ambiguo fra:

    il titolo porta segnale utile          -> H1 reale
    il titolo sposta e basta               -> abbiamo misurato l'instabilita'
                                              del pareggio, non il contesto

Il braccio di **controllo** antepone un `section_path` **sbagliato**, preso da un
altro documento: stessa lunghezza, stesso stile, contenuto senza relazione. Se
ribalta quante query ne ribalta quello giusto, il guadagno non era il contesto.

E' la regola aggiunta al §14 dopo I-11: prima di confrontare una metrica fra
configurazioni, verificare che il cambiamento non muova lo strumento.

Usage:
    python scripts/probe_section_context.py --dataset ledger --sample 150
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


def _decoy_pool(client, collection: str, size: int) -> list[tuple[str, str]]:
    """(doc_id, section_path) veri, pescati dalla collection, per il controllo.

    Titoli **veri** e non stringhe inventate: il controllo deve differire dal
    braccio vero per una cosa sola -- la pertinenza -- non anche per la forma.
    Un prefisso finto sarebbe fuori distribuzione e l'embedder reagirebbe a
    quello.
    """
    points, _ = client.scroll(collection_name=collection, limit=size,
                              with_payload=True, with_vectors=False)
    out = []
    for p in points:
        sp = ((p.payload or {}).get("section_path") or "").strip()
        if sp:
            out.append(((p.payload or {}).get("doc_id"), sp))
    return out


def _decoy_for(chunk_id: str, doc_id: str, pool: list[tuple[str, str]], seed: int) -> str:
    """Un titolo da un documento diverso, scelto in modo deterministico."""
    rnd = random.Random(f"{seed}:{chunk_id}")
    for _ in range(20):
        d, sp = rnd.choice(pool)
        if d != doc_id:
            return sp
    return pool[0][1]


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-01 H1: il contesto di sezione aiuta?")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collection", default=None)
    p.add_argument("--sample", type=int, default=50, help="query fallite da simulare")
    p.add_argument("--pool-cap", type=int, default=60, help="max chunk del documento d'oro")
    p.add_argument("--decoy-pool", type=int, default=3000,
                   help="chunk da cui pescare i titoli-esca del braccio di controllo")
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

    decoys = _decoy_pool(client, collection, args.decoy_pool)
    print(f"  titoli-esca disponibili per il controllo: {len(decoys)}", flush=True)

    idxs = random.Random(args.seed).sample(failed, min(args.sample, len(failed)))
    plain_win, ctx_win, ctrl_win = [], [], []
    n_ctx_chunks, n_chunks = 0, 0
    cache_plain: dict[str, list[float]] = {}
    cache_ctx: dict[str, list[float]] = {}
    cache_ctrl: dict[str, list[float]] = {}

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
        todo_plain, todo_ctx, todo_ctrl = [], [], []
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
            if cid not in cache_ctrl:
                # Il controllo antepone un titolo **solo** dove lo antepone il
                # braccio vero: altrimenti differirebbero anche per quanti
                # chunk vengono toccati, e non solo per la pertinenza.
                decoy = _decoy_for(cid, pl.get("doc_id"), decoys, args.seed) if sp else ""
                todo_ctrl.append((cid, f"{decoy}\n\n{t}" if decoy else t))
        n_chunks += len(uniq)

        for todo, cache in [(todo_plain, cache_plain), (todo_ctx, cache_ctx),
                            (todo_ctrl, cache_ctrl)]:
            if todo:
                vs = encode([t for _, t in todo], cfg.EMBEDDING_MODEL,
                            batch_size=cfg.EMBEDDING_BATCH)
                cache.update(zip((c for c, _ in todo), vs))

        q = qvecs[i]
        gold = set(gold_docs[i])
        for cache, out in [(cache_plain, plain_win), (cache_ctx, ctx_win),
                           (cache_ctrl, ctrl_win)]:
            scored = sorted(
                ((_cos(q, cache[pl.get("chunk_id")]), pl.get("doc_id")) for pl in uniq),
                key=lambda x: -x[0],
            )
            out.append(any(doc in gold for _, doc in scored[:5]))

        if k % 10 == 0:
            print(f"  [{k}/{len(idxs)}] senza {sum(plain_win)}  "
                  f"con {sum(ctx_win)}  controllo {sum(ctrl_win)}", flush=True)

    n = len(idxs)
    vero = compare_paired(plain_win, ctx_win)
    ctrl = compare_paired(plain_win, ctrl_win)
    print(f"\n  Query simulate: {n}   chunk nel pool: {n_chunks} "
          f"({n_ctx_chunks/max(n_chunks,1):.1%} con section_path da anteporre)")
    print("\n  un chunk d'oro entra nei primi 5:")
    print(f"    senza contesto        {sum(plain_win):>3}/{n}  ({vero.rate_a:.2%})")
    print(f"    con contesto VERO     {sum(ctx_win):>3}/{n}  ({vero.rate_b:.2%})   "
          f"solo con {vero.only_b}, solo senza {vero.only_a}, p = {vero.p_value:.4f}")
    print(f"    con contesto FINTO    {sum(ctrl_win):>3}/{n}  ({ctrl.rate_b:.2%})   "
          f"solo con {ctrl.only_b}, solo senza {ctrl.only_a}, p = {ctrl.p_value:.4f}")

    print("\n  Soglia del protocollo: <10% delle query -> H1 falsificata, "
          "non pagare il passo 3.  >=25% -> H1 sopravvive.")
    print(f"    guadagno del contesto vero   {(vero.rate_b - vero.rate_a):+.2%}")
    print(f"    guadagno del contesto finto  {(ctrl.rate_b - ctrl.rate_a):+.2%}")

    # La domanda del controllo: il titolo porta segnale, o sposta e basta?
    testa = compare_paired(ctrl_win, ctx_win)
    print(f"\n  VERO contro FINTO (appaiato): {testa.rate_a:.2%} -> {testa.rate_b:.2%}   "
          f"solo finto {testa.only_a}, solo vero {testa.only_b}, p = {testa.p_value:.4f}")
    if testa.p_value < 0.05 and testa.only_b > testa.only_a:
        print("    -> il titolo GIUSTO batte quello sbagliato: porta segnale, H1 resta viva.")
    else:
        print("    -> il titolo giusto non batte quello sbagliato: il guadagno era "
              "perturbazione di un pareggio, non contesto. H1 morta.")


if __name__ == "__main__":
    main()
