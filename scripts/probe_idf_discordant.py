#!/usr/bin/env python3
"""OQ-06, passi 1-2: cosa recupera l'IDF quando allontana dal chunk giusto.

R-08 ha misurato che su LEDGER accendere `modifier=IDF` porta al **documento**
giusto molto piu' spesso (doc@5 +27,85) e al **chunk** giusto un po' meno spesso
(chunk@5 -1,31, 484 query perse contro 353 guadagnate, p<0,0001). Le due
direzioni sono entrambe reali.

L'ipotesi scritta allora, e mai misurata: su LEDGER i token rari sono cifre e
identificativi; con l'IDF dominano il punteggio e tirano verso il documento che
contiene quella cifra, ma verso il chunk che la **nomina** -- un indice, un
sommario, un rimando -- invece che verso quello che risponde.

Questo script non decide: estrae le query discordanti e **mostra cosa ognuno dei
due bracci ha recuperato**, perche' l'ipotesi si verifica leggendo, non
contando. Quello che conta e' distinguibile solo a occhio:

    il chunk trovato con IDF e' un indice/sommario/rimando  -> ipotesi regge, e
        la correzione non e' l'IDF ma un filtro su content_type
    e' un chunk di contenuto sbagliato                      -> ipotesi cade, e
        resta da spiegare perche' l'IDF sbagli chunk dentro il documento giusto

Solo CPU e Qdrant: BM25 e' statistico e fastembed lo esegue senza acceleratore.

Usage:
    python scripts/probe_idf_discordant.py --sample 30
    python scripts/probe_idf_discordant.py --sample 10 --chars 400
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    Modifier,
    SparseVectorParams,
)
from src.retrieval.backends import RETRIEVERS
from src.index.store import get_client


def _set_modifier(client, name: str, modifier: Modifier) -> None:
    """Cambia il modificatore e rilegge che sia cambiato davvero.

    `Modifier.NONE`, non `None`: in `update_collection` un campo Python `None`
    vuol dire "non toccare". La prima versione del probe di R-08 lo spegneva con
    `None` e otteneva zero query discordanti su 200 -- due bracci che erano lo
    stesso braccio, senza alcun errore.
    """
    client.update_collection(
        collection_name=name,
        sparse_vectors_config={"sparse": SparseVectorParams(modifier=modifier)},
    )
    got = (client.get_collection(name).config.params.sparse_vectors or {}).get("sparse")
    if getattr(got, "modifier", None) != modifier:
        raise RuntimeError(f"{name}: chiesto {modifier}, l'indice dice {got}")


def _load(dataset_id: str, limit: int | None):
    queries, gold = [], []
    path = ROOT / "eval" / "golden" / f"{dataset_id}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        if not j.get("qrels"):
            continue
        ids = {q["chunk_id"] for q in j["qrels"] if q["relevance"] > 0}
        if not ids:
            continue
        queries.append(j["query_text"])
        gold.append(ids)
        if limit and len(queries) >= limit:
            break
    return queries, gold


def _describe(payload: dict, chars: int) -> str:
    text = (payload.get("text") or "").replace("\n", " ")
    sp = (payload.get("section_path") or "").strip() or "(nessuna sezione)"
    return (f"      content_type={payload.get('content_type')}  sezione={sp[:60]}\n"
            f"      {text[:chars]}")


def main() -> None:
    p = argparse.ArgumentParser(description="OQ-06: leggere le query discordanti")
    p.add_argument("--dataset", default="ledger")
    p.add_argument("--collection", default=None)
    p.add_argument("--depth", type=int, default=5)
    p.add_argument("--limit", type=int, default=None, help="query da valutare")
    p.add_argument("--sample", type=int, default=30, help="discordanti da mostrare per gruppo")
    p.add_argument("--chars", type=int, default=260)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    collection = args.collection or args.dataset
    queries, gold = _load(args.dataset, args.limit)
    client = get_client(cfg.QDRANT_URL)
    retrieve = RETRIEVERS["sparse"]
    config = cfg.RequestConfig.from_defaults(top_k=args.depth, retrieval_mode="sparse")
    print(f"{args.dataset}: {len(queries)} query, sparse @{args.depth}", flush=True)

    try:
        _set_modifier(client, collection, Modifier.NONE)
        off = retrieve(client, collection, queries, args.depth, None, config)
        _set_modifier(client, collection, Modifier.IDF)
        on = retrieve(client, collection, queries, args.depth, None, config)
    finally:
        _set_modifier(client, collection, Modifier.IDF)

    # I payload dei chunk d'oro delle query discordanti, presi dall'indice: il
    # dump non li contiene, e per sapere se ripetono il nome dell'azienda va
    # letto il testo.
    gold_payloads: dict[str, dict] = {}

    lost, gained = [], []
    for i, g in enumerate(gold):
        hit_off = bool(g & set(off[i].chunk_ids))
        hit_on = bool(g & set(on[i].chunk_ids))
        if hit_off and not hit_on:
            lost.append(i)
        elif hit_on and not hit_off:
            gained.append(i)
    print(f"  perse con l'IDF: {len(lost)}   guadagnate: {len(gained)}", flush=True)

    wanted = sorted({c for i in lost + gained for c in gold[i]})
    for start in range(0, len(wanted), 128):
        batch = wanted[start:start + 128]
        flt = Filter(must=[FieldCondition(key="chunk_id", match=MatchAny(any=batch))])
        offset = None
        while True:
            pts, offset = client.scroll(collection_name=collection, scroll_filter=flt,
                                        limit=512, offset=offset, with_payload=True)
            for p in pts:
                gold_payloads[(p.payload or {}).get("chunk_id", "")] = p.payload or {}
            if offset is None:
                break
    print(f"  chunk d'oro recuperati dall'indice: {len(gold_payloads)}/{len(wanted)}\n",
          flush=True)

    rnd = random.Random(args.seed)
    for label, idxs, shown in (
        ("PERSE con l'IDF (le trovava senza, non le trova con)", lost, on),
        ("GUADAGNATE con l'IDF", gained, off),
    ):
        print(f"\n{'=' * 70}\n{label}: {len(idxs)}\n{'=' * 70}")
        n = max(len(idxs), 1)
        ct = Counter(shown[i].payloads[0].get("content_type") for i in idxs)
        print("  content_type del chunk in cima nell'altro braccio: "
              + "  ".join(f"{k}:{v/n:.0%}" for k, v in ct.most_common()))

        # Discriminante meccanico, e non circolare: quando l'IDF perde il chunk
        # giusto, resta almeno **dentro il documento giusto**? Se si', il guasto
        # e' "chunk sbagliato del documento giusto" -- coerente con l'ipotesi
        # dell'indice o del rimando. Se no, l'IDF sta andando altrove del tutto,
        # e l'ipotesi cade comunque si leggano i casi.
        same_doc = 0
        for i in idxs:
            gold_docs = {c.split(":")[1] for c in gold[i] if ":" in c}
            top = on[i].chunk_ids[0] if on[i].chunk_ids else ""
            if ":" in top and top.split(":")[1] in gold_docs:
                same_doc += 1
        print(f"  con IDF il chunk in cima sta comunque nel documento d'oro: "
              f"{same_doc}/{len(idxs)} ({same_doc/n:.0%})")

        # Il meccanismo, misurato invece che letto. Su LEDGER ogni domanda nomina
        # un'azienda, e il ticker e' il token piu' raro che contenga: e' quello
        # che l'IDF fa pesare. Se l'ipotesi regge, i chunk che l'IDF porta in
        # cima devono ripetere il ticker **piu'** di quelli che porta l'altro
        # braccio -- e i chunk che lo ripetono di piu' sono la modulistica
        # (allegati, certificazioni, elenchi di controllate), non il paragrafo
        # che risponde.
        #
        # Il ticker si prende dal doc_id (EXCHANGE_TICKER_ANNO), non dalla
        # domanda: cosi' non lo si va a cercare dove si spera di trovarlo.
        def _ticker_count(payload: dict, doc_id: str) -> int:
            parts = doc_id.split("_")
            if len(parts) < 2:
                return 0
            return (payload.get("text") or "").upper().count(parts[1].upper())

        c_off, c_on, usable = 0, 0, 0
        for i in idxs:
            doc = (on[i].chunk_ids[0].split(":")[1]
                   if on[i].chunk_ids and ":" in on[i].chunk_ids[0] else "")
            if not doc or len(doc.split("_")) < 2:
                continue
            usable += 1
            c_off += _ticker_count(off[i].payloads[0], doc)
            c_on += _ticker_count(on[i].payloads[0], doc)
        if usable:
            print(f"  ripetizioni del ticker nel chunk in cima ({usable} query): "
                  f"IDF spento {c_off/usable:.2f}  acceso {c_on/usable:.2f}")

        # La chiave di volta. Se l'ipotesi regge, il chunk **d'oro** -- quello
        # che risponde davvero -- deve nominare l'azienda **poco**: ripete
        # l'argomento, non l'entita'. Se invece la ripetesse quanto la
        # modulistica, l'IDF non avrebbe motivo di preferire l'una all'altra e
        # tutta la spiegazione cadrebbe.
        gold_counts = []
        for i in idxs:
            for cid in sorted(gold[i]):
                pl = gold_payloads.get(cid)
                if pl is None or ":" not in cid:
                    continue
                gold_counts.append(_ticker_count(pl, cid.split(":")[1]))
        if gold_counts:
            print(f"  ripetizioni del ticker nel chunk D'ORO ({len(gold_counts)} chunk): "
                  f"{sum(gold_counts)/len(gold_counts):.2f}")

        for i in rnd.sample(idxs, min(args.sample, len(idxs))):
            print(f"\n  --- {queries[i][:90]}")
            print("    IDF SPENTO, in cima:")
            print(_describe(off[i].payloads[0], args.chars))
            print("    IDF ACCESO, in cima:")
            print(_describe(on[i].payloads[0], args.chars))


if __name__ == "__main__":
    main()
