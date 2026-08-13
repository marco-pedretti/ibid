#!/usr/bin/env python3
"""OQ-04 — il chunk giusto viene mancato più spesso quando supera la finestra?

**Misura, non codice di produzione.**  Committato perché i numeri citati in
`docs/open-questions.md` (OQ-04) e in `STACK.md` si possano ri-derivare invece
che credere.

L'embedder tronca a 512 token e le pipeline di chunking non lo sanno: del chunk
mediano entra nell'indice circa metà del testo.  Questo probe chiede se il
difetto **morde**, e lo chiede senza spendere GPU — usa solo dati già su disco:

  chunk recuperati  ->  i dump delle generazioni di C-01
  chunk giusti      ->  i qrels dei golden set
  testi             ->  Qdrant (sola lettura)

Il tokenizer è CPU, quindi il probe si può lanciare mentre la GPU sta girando
un'altra misura.

**Cosa NON dimostra.**  È descrittivo.  La lunghezza correla con altro — genere
della sezione, posizione nel documento, quanto è specifica la domanda — e da qui
non si separa.  Serve a decidere se vale la pena di I-10, non a sostituirlo.

Ciò che rende la lettura non banale è la direzione: **a parità di tutto il resto
un chunk più lungo contiene più testo, quindi dovrebbe essere più facile da
trovare, non più difficile.**  Se viene mancato di più, la spiegazione più
semplice è che quel testo in più nell'indice non c'è.

Uso:
    python scripts/probe_truncation.py [dump_orb] [dump_ledger]
"""

from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg
from src.providers import CPU_ONLY
from fastembed import TextEmbedding
from qdrant_client import models
from src.index.store import get_client

GENERATIONS = ROOT / "eval" / "results" / "generations"
GOLDEN = ROOT / "eval" / "golden"

#: I dump di riferimento: l'ultima run di C-01 per dataset, cioè il prompt che
#: sta in albero.  Sovrascrivibili da riga di comando.
DEFAULT_DUMPS = {
    "open_ragbench": "20260810_102617_open_ragbench.jsonl",
    "ledger": "20260810_110845_ledger.jsonl",
}

WINDOW = 512  # finestra del tokenizer di multilingual-e5-large


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """p a due code per la tabella [[a, b], [c, d]].

    Esatto e non chi-quadro: uno dei due gruppi qui ha 38 elementi, e
    l'approssimazione non è affidabile su conteggi così piccoli — la stessa
    ragione per cui `src/eval/paired.py` usa McNemar esatto.
    """
    n, r1, c1 = a + b + c + d, a + b, a + c
    def prob(x: int) -> float:
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    p0 = prob(a)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return sum(p for x in range(lo, hi + 1) if (p := prob(x)) <= p0 * (1 + 1e-9))


def _tokenizer():
    model = TextEmbedding(
        model_name=cfg.EMBEDDING_MODEL, providers=CPU_ONLY,
        cache_dir=cfg.FASTEMBED_CACHE,
    ).model.tokenizer
    # Senza questo si conterebbero i token dopo il taglio, cioè 512 per tutti:
    # il probe misurerebbe la propria troncatura invece di quella dell'indice.
    model.no_truncation()
    return model


def _texts(client, collection: str, ids: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), 64):
        pts, _ = client.scroll(
            collection,
            scroll_filter=models.Filter(must=[models.FieldCondition(
                key="chunk_id", match=models.MatchAny(any=ids[i:i + 64]))]),
            limit=256, with_payload=["chunk_id", "text"])
        for p in pts:
            out[p.payload["chunk_id"]] = p.payload["text"]
    return out


def _quartiles(xs: list[int]) -> str:
    xs = sorted(xs)
    if not xs:
        return "-"
    def q(f: float) -> int:
        return xs[min(len(xs) - 1, int(f * len(xs)))]
    return f"mediana {q(.5):>6}  q1 {q(.25):>5}  q3 {q(.75):>6}"


def run(dataset: str, dump_name: str, tok, client) -> None:
    dump = GENERATIONS / dump_name
    rows = [json.loads(x) for x in dump.read_text(encoding="utf-8").splitlines() if x.strip()]
    retrieved = {r["query_id"]: set(r["chunk_ids"]) for r in rows}

    gold: dict[str, list[str]] = {}
    for line in (GOLDEN / f"{dataset}.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        g = json.loads(line)
        if g["query_id"] in retrieved and g.get("qrels"):
            gold[g["query_id"]] = [q["chunk_id"] for q in g["qrels"] if q.get("relevance", 0) > 0]

    texts = _texts(client, dataset, [c for ids in gold.values() for c in ids])
    lens = {c: len(tok.encode(t).ids) for c, t in texts.items()}

    hit, miss = [], []
    for qid, gids in gold.items():
        known = [c for c in gids if c in lens]
        if not known:
            continue
        found = [c for c in known if c in retrieved[qid]]
        # Il più corto fra i chunk giusti, non il più lungo: è il caso più
        # favorevole all'ipotesi nulla, e non gonfia l'effetto per costruzione.
        (hit if found else miss).append(
            min(lens[c] for c in (found or known))
        )

    if not hit or not miss:
        print(f"\n=== {dataset} === campione degenere ({len(hit)} trovati, {len(miss)} mancati)")
        return

    h_over = sum(1 for x in hit if x > WINDOW)
    m_over = sum(1 for x in miss if x > WINDOW)
    p = fisher_exact_two_sided(h_over, len(hit) - h_over, m_over, len(miss) - m_over)

    print(f"\n=== {dataset} ===  {len(hit) + len(miss)} query con qrel risolvibile  ({dump.name})")
    print(f"  chunk giusto TROVATO   n={len(hit):<4} {_quartiles(hit)}")
    print(f"  chunk giusto MANCATO   n={len(miss):<4} {_quartiles(miss)}")
    print(f"  oltre {WINDOW} token: fra i trovati {h_over}/{len(hit)} = {h_over / len(hit):.1%}"
          f"   fra i mancati {m_over}/{len(miss)} = {m_over / len(miss):.1%}")
    print(f"  Fisher esatto, due code: p = {p:.5f}")


if __name__ == "__main__":
    dumps = dict(DEFAULT_DUMPS)
    if len(sys.argv) > 1:
        dumps["open_ragbench"] = sys.argv[1]
    if len(sys.argv) > 2:
        dumps["ledger"] = sys.argv[2]
    tokenizer, qdrant = _tokenizer(), get_client(cfg.QDRANT_URL)
    for ds, dump_file in dumps.items():
        run(ds, dump_file, tokenizer, qdrant)
