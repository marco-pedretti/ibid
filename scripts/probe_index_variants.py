#!/usr/bin/env python3
"""I-10 e I-08 — misurare una ricetta di indicizzazione senza re-ingestare tutto.

Una re-ingestione completa costa 618 minuti (misurati in R-07) e serve ad
*adottare* una correzione, non a decidere se adottarla. Questo strumento decide:
campiona qualche migliaio di chunk, li indicizza in due varianti che differiscono
per una cosa sola, e confronta in appaiato sulle query golden.

Due misure lo usano, **una alla volta** (§15):

  capped     I-10 / OQ-04 — il tokenizer tronca a 512 token e le pipeline non lo
             sanno. La variante spezza i chunk a `--cap` token.
  prefixed   I-08 / OQ-02 — la model card di E5 richiede `query: ` / `passage: `
             e fastembed li lascia al chiamante. La variante li aggiunge da
             entrambi i lati.

Tre passi, perché solo i primi due costano GPU e il primo non costa niente:

    python scripts/probe_index_variants.py sample --dataset open_ragbench
    python scripts/probe_index_variants.py index  --dataset open_ragbench --variant plain
    python scripts/probe_index_variants.py index  --dataset open_ragbench --variant capped
    python scripts/probe_index_variants.py eval   --dataset open_ragbench --variant capped

**Il campione contiene documenti interi, non chunk sparsi.** Un indice fatto dei
soli chunk giusti li fa trovare tutti: senza i vicini che oggi li superano non si
misura il retrieval, si misura che il chunk esiste. Si campionano quindi tutti i
chunk dei documenti che contengono un chunk giusto, più altri documenti interi
come distrattori.

**Si legge a livello di documento**, come R-07 e per la stessa ragione: la
variante `capped` cambia i `chunk_id` — un chunk spezzato in tre non coincide più
con nessun qrel — mentre il `doc_id` sopravvive a qualunque ri-chunking. È anche
l'unico modo di confrontare due indici che contengono un numero diverso di chunk.

**I tassi assoluti sono ottimistici e non vanno riportati come recall.** Con 450
documenti su 997 (misurato su open_ragbench: 9.312 chunk, il 49% del corpus) ogni
query ha metà dei concorrenti che avrebbe in produzione. Ciò che si legge è il
**delta appaiato** fra due varianti che condividono esattamente lo stesso
campione: quello non risente della riduzione, perché la riduzione è la stessa dai
due lati.

Costo misurato del campione open_ragbench: ~16 minuti di GPU per la variante
`plain`, ~34 per `capped` (che produce più chunk). Contro i 618 di una
re-ingestione completa.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg
from src.providers import CPU_ONLY
from src.datasets import registry
from qdrant_client import models
from src.datasets.schema import Chunk
from src.eval.paired import compare_paired
from src.index.store import ensure_collection, get_client
from src.retrieval.doc_aggregation import doc_id_from_chunk_id

SAMPLES = ROOT / "eval" / "results" / "probe_samples"
GOLDEN = ROOT / "eval" / "golden"

#: Documenti distrattori oltre a quelli che contengono un chunk giusto. Servono
#: a dare al retrieval qualcosa da sbagliare: un indice di soli documenti
#: rilevanti misurerebbe una domanda diversa da quella posta.
DISTRACTOR_DOCS = 300

#: Query golden usate. 200 e' il campione con cui girano C-01 e i confronti
#: appaiati gia' in `progress.md`, quindi i numeri restano leggibili accanto.
N_QUERIES = 200


def _collection(dataset: str, variant: str) -> str:
    return f"{dataset}_probe_{variant}"


# --------------------------------------------------------------------------
# passo 1 — campione (nessuna GPU)
# --------------------------------------------------------------------------

def cmd_sample(dataset: str, n_queries: int) -> None:
    client = get_client(cfg.QDRANT_URL)

    queries = []
    for line in (GOLDEN / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        g = json.loads(line)
        if g.get("qrels") and g["dataset_id"] == dataset:
            queries.append(g)
        if len(queries) >= n_queries:
            break

    gold_docs = {doc_id_from_chunk_id(q["chunk_id"])
                 for g in queries for q in g["qrels"] if q.get("relevance", 0) > 0}

    # Tutti i doc_id della collection, in ordine di scroll: i distrattori sono i
    # primi che non sono gia' dentro. Deterministico, quindi il campione si
    # ricostruisce identico.
    all_docs: list[str] = []
    seen: set[str] = set()
    offset = None
    while True:
        pts, offset = client.scroll(dataset, limit=2000, offset=offset, with_payload=["doc_id"])
        for p in pts:
            d = p.payload["doc_id"]
            if d not in seen:
                seen.add(d)
                all_docs.append(d)
        if offset is None:
            break

    distractors = [d for d in all_docs if d not in gold_docs][:DISTRACTOR_DOCS]
    keep = sorted(gold_docs | set(distractors))

    SAMPLES.mkdir(parents=True, exist_ok=True)
    out = SAMPLES / f"{dataset}_sample.json"
    out.write_text(json.dumps({
        "dataset": dataset,
        "query_ids": [g["query_id"] for g in queries],
        "doc_ids": keep,
        "n_gold_docs": len(gold_docs),
        "n_distractor_docs": len(distractors),
    }, indent=2), encoding="utf-8")

    n_chunks = client.count(dataset, count_filter=models.Filter(must=[
        models.FieldCondition(key="doc_id", match=models.MatchAny(any=keep[:200]))])).count
    print(f"{dataset}: {len(queries)} query, {len(gold_docs)} documenti con chunk giusto, "
          f"{len(distractors)} distrattori, {len(keep)} documenti in totale")
    print(f"  (i primi 200 documenti valgono gia' {n_chunks} chunk)")
    print(f"  documenti totali nella collection: {len(all_docs)}")
    print(f"Salvato -> {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------
# passo 2 — indicizzazione della variante (GPU)
# --------------------------------------------------------------------------

def _split_capped(text: str, cap: int, tok) -> list[str]:
    ids = tok.encode(text).ids
    if len(ids) <= cap:
        return [text]
    return [tok.decode(ids[i:i + cap]) for i in range(0, len(ids), cap)]


def cmd_index(dataset: str, variant: str, cap: int) -> None:
    from src.index.embed import encode, encode_sparse, vector_size

    sample = json.loads((SAMPLES / f"{dataset}_sample.json").read_text(encoding="utf-8"))
    client = get_client(cfg.QDRANT_URL)
    target = _collection(dataset, variant)

    payloads: list[dict] = []
    doc_ids = sample["doc_ids"]
    for i in range(0, len(doc_ids), 64):
        offset = None
        while True:
            pts, offset = client.scroll(
                dataset, limit=2000, offset=offset,
                scroll_filter=models.Filter(must=[models.FieldCondition(
                    key="doc_id", match=models.MatchAny(any=doc_ids[i:i + 64]))]),
                with_payload=True)
            payloads.extend(p.payload for p in pts)
            if offset is None:
                break
    print(f"{target}: {len(payloads)} chunk sorgente")

    tok = None
    if variant == "capped":
        from fastembed import TextEmbedding
        tok = TextEmbedding(
            model_name=cfg.EMBEDDING_MODEL, providers=CPU_ONLY,
            cache_dir=cfg.FASTEMBED_CACHE,
        ).model.tokenizer
        tok.no_truncation()

    chunks: list[Chunk] = []
    for p in payloads:
        pieces = _split_capped(p["text"], cap, tok) if variant == "capped" else [p["text"]]
        for j, piece in enumerate(pieces):
            chunks.append(Chunk(
                chunk_id=p["chunk_id"] if len(pieces) == 1 else f"{p['chunk_id']}:s{j}",
                dataset_id=p["dataset_id"], doc_id=p["doc_id"],
                doc_genre=p.get("doc_genre", ""), pipeline=p.get("pipeline", ""),
                section_path=p.get("section_path", ""), page=p.get("page", 0), bbox=None,
                content_type=p.get("content_type", "text"), text=piece,
                source_uri=p["source_uri"]))
    print(f"  -> {len(chunks)} chunk indicizzati (variante {variant})")

    # Il prefisso e' l'unica differenza della variante `prefixed`, e va applicato
    # a cio' che si embedda, non a cio' che si conserva: il payload deve restare
    # il testo vero, o il contesto dell'LLM conterrebbe "passage: ".
    to_embed = [f"passage: {c.text}" for c in chunks] if variant == "prefixed" \
        else [c.text for c in chunks]

    if client.collection_exists(target):
        client.delete_collection(target)
    ensure_collection(client, target, vector_size(cfg.EMBEDDING_MODEL))

    from src.index.store import upsert
    B = 512
    for i in range(0, len(chunks), B):
        part, texts = chunks[i:i + B], to_embed[i:i + B]
        upsert(client, target, part,
               encode(texts, cfg.EMBEDDING_MODEL, batch_size=cfg.EMBEDDING_BATCH),
               encode_sparse(texts, cfg.SPARSE_EMBEDDING_MODEL), id_offset=i)
        print(f"  {min(i + B, len(chunks))}/{len(chunks)}", flush=True)
    print(f"Fatto -> {target}")


# --------------------------------------------------------------------------
# passo 3 — confronto appaiato (GPU per le sole query)
# --------------------------------------------------------------------------

def cmd_eval(dataset: str, variant: str, top_k: int, limit: int | None = None) -> None:
    from src.eval.retrieval_backends import RETRIEVERS

    sample = json.loads((SAMPLES / f"{dataset}_sample.json").read_text(encoding="utf-8"))
    in_sample = set(sample["doc_ids"])

    # **Tutte le query valutabili, non solo le 200 che hanno scelto i documenti.**
    # Il campione contiene documenti interi, e una query e' valutabile se *tutti*
    # i suoi documenti rilevanti stanno dentro: se ne mancasse uno risulterebbe
    # fallita per assenza dal campione invece che per colpa del retrieval.
    # Su open_ragbench sono 1.903 invece di 200 — dieci volte la potenza per il
    # costo di embeddare qualche migliaio di query in piu', cioe' secondi. Il
    # confronto e' appaiato e i due bracci vedono le stesse query, quindi la
    # selezione non lo distorce; sposta solo i tassi assoluti, che infatti non
    # vanno letti come recall (vedi il docstring in testa).
    queries, gold_docs = [], {}
    for line in (GOLDEN / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        g = json.loads(line)
        if g["dataset_id"] != dataset or not g.get("qrels"):
            continue
        docs = {doc_id_from_chunk_id(q["chunk_id"])
                for q in g["qrels"] if q.get("relevance", 0) > 0}
        if docs and docs <= in_sample:
            queries.append(g)
            gold_docs[g["query_id"]] = docs
    if limit:
        queries = queries[:limit]

    client = get_client(cfg.QDRANT_URL)
    ranks: dict[str, list[int]] = {}
    for var in ("plain", variant):
        col = _collection(dataset, var)
        if not client.collection_exists(col):
            raise SystemExit(f"{col} non esiste — lanciare prima `index --variant {var}`")
        texts = [g["query_text"] for g in queries]
        if var == "prefixed":
            texts = [f"query: {t}" for t in texts]
        cands = RETRIEVERS["dense"](client, col, texts, top_k, None)
        ranks[var] = []
        for g, c in zip(queries, cands):
            docs: list[str] = []
            for cid in c.chunk_ids:
                d = doc_id_from_chunk_id(cid)
                if d not in docs:
                    docs.append(d)
            # Posizione del primo documento rilevante, 0 se non compare affatto.
            ranks[var].append(
                next((i + 1 for i, d in enumerate(docs) if d in gold_docs[g["query_id"]]), 0)
            )

    print(f"\n=== {dataset}: plain vs {variant} — {len(queries)} query appaiate ===")
    print("criterio: il primo documento rilevante entro le prime k posizioni")
    # **Tutte e tre le profondita', sempre.** `doc@5` e' saturo — 7 fallimenti su
    # 200 su open_ragbench e 1 su ledger — quindi non ha la potenza per
    # distinguere niente; `doc@1` ne ha tre o quattro volte tanta. Ma scegliere
    # la profondita' dopo aver visto quale conviene sarebbe selezione, quindi si
    # riportano tutte e la scelta resta visibile a chi legge.
    for k in (1, 3, 5):
        res = compare_paired([0 < r <= k for r in ranks["plain"]],
                             [0 < r <= k for r in ranks[variant]])
        n_fail = sum(1 for r in ranks["plain"] if not 0 < r <= k)
        print(f"\n  doc@{k}:  plain {res.rate_a:.4f}  ->  {variant} {res.rate_b:.4f}"
              f"   delta {res.delta:+.4f}")
        print(f"    discordanti: solo plain {res.only_a}, solo {variant} {res.only_b}"
              f"   (fallimenti di plain: {n_fail})")
        print(f"    {res.verdict()}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="I-10 / I-08 su indice ridotto")
    p.add_argument("step", choices=["sample", "index", "eval"])
    p.add_argument("--dataset", choices=registry.dataset_ids(), default="open_ragbench")
    p.add_argument("--variant", choices=["plain", "capped", "prefixed"], default="capped")
    p.add_argument("--cap", type=int, default=512, help="tetto in token per la variante capped")
    p.add_argument("--top-k", type=int, default=20,
                   help="chunk recuperati; i primi 5 *documenti* distinti decidono")
    p.add_argument("--n-queries", type=int, default=N_QUERIES)
    p.add_argument("--limit", type=int, default=None,
                   help="valuta solo le prime N query valutabili")
    a = p.parse_args()

    if a.step == "sample":
        cmd_sample(a.dataset, a.n_queries)
    elif a.step == "index":
        cmd_index(a.dataset, a.variant, a.cap)
    else:
        cmd_eval(a.dataset, a.variant, a.top_k, a.limit)
