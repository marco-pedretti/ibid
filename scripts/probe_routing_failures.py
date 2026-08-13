#!/usr/bin/env python3
"""R-10, passo 1b: perche' una *domanda* non raggiunge il suo documento (OQ-01).

Il passo 1 aveva isolato 651 query in cui il documento corretto non compare
nemmeno a rango 100. La prima lettura -- "651 documenti mal rappresentati" -- era
sbagliata di unita': LEDGER ha **494 documenti d'oro per 10.000 query**, e
misurando per documento risulta *uno solo* mai trovato. Lo stesso documento viene
raggiunto da certe domande e non da altre.

Quindi il guasto non e' "questo documento e' invisibile" ma "questa domanda non
arriva al suo documento", ed e' una cosa diversa: significa che nell'indice
routed il chunk che risponde **a quella domanda** non si fa trovare, mentre altri
chunk dello stesso documento si.

La misura decisiva sfrutta il filtro di Qdrant: cercando **dentro il documento
d'oro** si ottiene il punteggio del miglior chunk che avrebbe potuto rispondere.
Confrontandolo con il punteggio del chunk che ha vinto davvero si separano due
cause che il recall non distingue:

    miglior chunk d'oro ha punteggio ALTO ma perde  -> concorrenza: i vicini sono
        piu' simili alla domanda. Rimedio: reranker, o filtro per content_type.
    miglior chunk d'oro ha punteggio BASSO          -> rappresentazione: quel
        chunk non assomiglia alla domanda comunque lo si ordini. Rimedio: cambiare
        come viene costruito, cioe' re-ingestione (passo 3).

Usage:
    python scripts/probe_routing_failures.py --dataset ledger --sample 400
"""

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from qdrant_client.models import FieldCondition, Filter, MatchAny
from src.index.embed import encode
from src.index.store import get_client, search_batch

_MARKUP = re.compile(r"<[^>]+>")


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
        gold_docs.append(sorted(docs))
        if limit and len(queries) >= limit:
            break
    return queries, gold_docs


def _stats(payload: dict) -> tuple[int, float]:
    text = _MARKUP.sub(" ", payload.get("text") or "")
    letters = sum(c.isalpha() for c in text)
    return len(text), (letters / len(text) if text else 0.0)


def _summarize(label: str, rows: list[dict]) -> None:
    if not rows:
        print(f"\n  {label}: vuoto")
        return
    n = len(rows)
    gold_s = [r["gold_score"] for r in rows if r["gold_score"] is not None]
    top_s = [r["top_score"] for r in rows]
    gaps = [r["top_score"] - r["gold_score"] for r in rows if r["gold_score"] is not None]
    print(f"\n  {label}  ({n} query)")
    print(f"    punteggio del chunk vincente          mediana {statistics.median(top_s):.4f}")
    if gold_s:
        print(f"    punteggio del miglior chunk d'oro     mediana {statistics.median(gold_s):.4f}")
        print(f"    distacco                              mediana {statistics.median(gaps):+.4f}")
    print("    content_type del miglior chunk d'oro  "
          + "  ".join(f"{k}:{v/n:.1%}" for k, v in
                      Counter(r["gold_ctype"] for r in rows).most_common()))
    print("    content_type del chunk vincente       "
          + "  ".join(f"{k}:{v/n:.1%}" for k, v in
                      Counter(r["top_ctype"] for r in rows).most_common()))
    lens = [r["gold_len"] for r in rows if r["gold_len"] is not None]
    alpha = [r["gold_alpha"] for r in rows if r["gold_alpha"] is not None]
    if lens:
        print(f"    miglior chunk d'oro: {statistics.median(lens):.0f} char, "
              f"lettere/char {statistics.median(alpha):.2f}")
    heading = sum(1 for r in rows if r["gold_has_heading"])
    withpath = sum(1 for r in rows if r["gold_has_path"])
    print(f"    section_path valorizzato {withpath/n:.1%}, "
          f"presente nel testo {heading/max(withpath, 1):.1%} di quelli")


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-01: concorrenza o rappresentazione?")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collection", default=None)
    p.add_argument("--sample", type=int, default=400,
                   help="query per gruppo (fallite / riuscite), campionate a caso")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--deep", type=int, default=100,
                   help="profondita' che separa 'perso di poco' da 'mai emerso'")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    collection = args.collection or f"{args.dataset}_routed"
    queries, gold_docs = _load(args.dataset, args.limit)
    print(f"{args.dataset}: {len(queries)} query su {collection}", flush=True)

    client = get_client(cfg.QDRANT_URL)
    vecs = encode(queries, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH)
    hits = search_batch(client, collection, vecs, top_k=5, using="dense")

    failed, ok = [], []
    for i, (points, gold) in enumerate(zip(hits, gold_docs)):
        seen = {(p.payload or {}).get("doc_id") for p in points}
        (ok if (set(gold) & seen) else failed).append(i)
    print(f"  fallite a top-5: {len(failed)}   riuscite: {len(ok)}")

    # Le fallite non sono una cosa sola. Il passo 1 aveva trovato che il 27,7%
    # non vede il documento giusto nemmeno a rango 100, e i quasi-pareggi non
    # possono spiegare quelle: un pareggio perso finisce a rango 6, non oltre
    # il 100. Se le due sotto-popolazioni hanno distacchi diversi, sono due
    # guasti diversi e vanno raccontati separatamente.
    deep_hits = search_batch(client, collection, [vecs[i] for i in failed],
                             top_k=args.deep, using="dense")
    near, far = [], []
    for i, points in zip(failed, deep_hits):
        seen = {(p.payload or {}).get("doc_id") for p in points}
        (near if (set(gold_docs[i]) & seen) else far).append(i)
    print(f"  di cui trovate entro rango {args.deep}: {len(near)}   "
          f"mai trovate: {len(far)}")

    rnd = random.Random(args.seed)
    groups = {
        "FALLITE ma il documento e' entro rango 100": rnd.sample(
            near, min(args.sample, len(near))),
        "FALLITE e il documento non compare mai": rnd.sample(
            far, min(args.sample, len(far))),
        "RIUSCITE": rnd.sample(ok, min(args.sample, len(ok))),
    }

    for label, idxs in groups.items():
        # Una ricerca per query, ristretta al documento d'oro: restituisce il
        # miglior chunk che *avrebbe potuto* rispondere, con il suo punteggio.
        filters = [Filter(must=[FieldCondition(key="doc_id",
                                               match=MatchAny(any=gold_docs[i]))])
                   for i in idxs]
        best = search_batch(client, collection, [vecs[i] for i in idxs],
                            top_k=1, using="dense", filters=filters)
        rows = []
        for i, gold_hits in zip(idxs, best):
            top = hits[i][0]
            g = gold_hits[0] if gold_hits else None
            gp = (g.payload or {}) if g else {}
            glen, galpha = _stats(gp) if g else (None, None)
            sp = (gp.get("section_path") or "").strip()
            rows.append({
                "top_score": top.score,
                "top_ctype": (top.payload or {}).get("content_type"),
                "gold_score": g.score if g else None,
                "gold_ctype": gp.get("content_type"),
                "gold_len": glen, "gold_alpha": galpha,
                "gold_has_path": bool(sp),
                "gold_has_heading": bool(sp) and sp.lower() in (gp.get("text") or "").lower(),
            })
        _summarize(label, rows)


if __name__ == "__main__":
    main()
