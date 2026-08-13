#!/usr/bin/env python3
"""`citation_precision` dipende dalla lunghezza della premessa? (I-11)

**Misura, non codice di produzione.** Committato perche' il numero citato in
`docs/progress.md` si possa ri-derivare invece che credere.

Nato per rispondere a una domanda precisa: il tetto di chunking di I-11 alza
`citation_precision` di 11 punti (0,6634 -> 0,7745). E' del sistema o dello
strumento?

I due bracci differiscono per la lunghezza dei chunk, quindi per la lunghezza
delle **premesse** date al verificatore. C-03 aveva gia' documentato che questo
verificatore e' sensibile alla lunghezza (STACK.md: correlazione 0,46-0,54 fra
numero di finestre e P(entailment) massima).

Se dentro il braccio `plain` -- a parita' di tutto il resto -- le premesse corte
vengono accettate piu' spesso di quelle lunghe, allora una parte del guadagno di
`capped` e' l'artefatto e non il sistema.

**Risposta, misurata il 2026-08-12:** dentro `plain`, dal quartile piu' corto al
piu' lungo, l'accettazione scende da 79,2% a 57,8% in modo monotono. Le premesse
di `capped` stanno tutte sotto i 515 token, cioe' nella fascia dove `plain`
accetta il 68-79%: il suo 77,5% e' quello che si prevede senza alcun
miglioramento della qualita' delle citazioni.

**Conseguenza che sopravvive a I-11:** `citation_precision` non e' confrontabile
fra configurazioni che cambiano la lunghezza dei chunk. Vale per qualunque
modifica al chunking, non solo per questa.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
os.chdir(r"c:\Users\marco\dev\ibid")
sys.path.insert(0, r"c:\Users\marco\dev\ibid")

from qdrant_client import models
import src.config as cfg
from fastembed import TextEmbedding
from src.index.store import get_client

tok = TextEmbedding(model_name=cfg.EMBEDDING_MODEL, providers=["CPUExecutionProvider"],
                    cache_dir=cfg.FASTEMBED_CACHE).model.tokenizer
tok.no_truncation()
client = get_client(cfg.QDRANT_URL)

ARMS = {
    "plain":  ("eval/results/verdicts/20260812_181041_open_ragbench.jsonl", "open_ragbench_probe_plain"),
    "capped": ("eval/results/verdicts/20260812_181226_open_ragbench.jsonl", "open_ragbench_probe_capped"),
}

for arm, (vpath, collection) in ARMS.items():
    rows = [json.loads(x) for x in open(vpath, encoding="utf-8") if x.strip()]
    ids = sorted({r["chunk_id"] for r in rows})
    texts = {}
    for i in range(0, len(ids), 64):
        pts, _ = client.scroll(collection, scroll_filter=models.Filter(must=[models.FieldCondition(
            key="chunk_id", match=models.MatchAny(any=ids[i:i + 64]))]), limit=256,
            with_payload=["chunk_id", "text"])
        for p in pts:
            texts[p.payload["chunk_id"]] = p.payload["text"]

    lens = {c: len(tok.encode(t).ids) for c, t in texts.items()}
    pairs = [(lens.get(r["chunk_id"], 0), r["supported"], r["score"]) for r in rows
             if r["chunk_id"] in lens]
    pairs.sort()
    n = len(pairs)
    if not n:
        print(f"{arm}: nessuna coppia risolvibile")
        continue

    print(f"\n=== {arm} ===  {n} coppie   (mancanti: {len(rows) - n})")
    # Quartili di lunghezza della premessa, e tasso di accettazione in ciascuno.
    for q in range(4):
        lo, hi = q * n // 4, (q + 1) * n // 4
        part = pairs[lo:hi]
        toks = [p[0] for p in part]
        acc = sum(p[1] for p in part) / len(part)
        print(f"  quartile {q + 1}: premessa {toks[0]:>5}-{toks[-1]:>6} token   "
              f"accettate {acc:.1%}   P(entail) mediana {sorted(p[2] for p in part)[len(part) // 2]:.3f}")
