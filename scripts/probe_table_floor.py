#!/usr/bin/env python3
"""OQ-05 — il verificatore distingue un numero presente da uno assente?

**Misura, non codice di produzione.** Committato perché il numero citato in
`docs/open-questions.md` (OQ-05) si possa ri-derivare invece che credere.

Su LEDGER `citation_precision` vale 0,3656 e non sappiamo cosa misuri: il
modello che cita male, o il verificatore che non sa leggere una tabella. C-08 ha
escluso che sia il markup. Questo probe prova a separare le due cose.

**L'idea.** Il 96,7% dei claim su LEDGER asserisce dei numeri. Un numero è
presente nel chunk citato o non lo è, e questo si controlla con una ricerca di
stringa — nessun modello coinvolto. Se il verificatore funziona, deve dare
punteggi più alti quando il numero c'è. Se non separa i due casi, è cieco
esattamente su ciò che il claim afferma.

**Costo zero.** I punteggi sono già nei verdetti salvati da C-03/C-08, i testi
sono in Qdrant: nessuna inferenza, nessuna GPU.

**Cosa NON dimostra.** La presenza del numero non prova che il claim sia
corretto: `1.234` può stare nella tabella sulla riga sbagliata o sull'anno
sbagliato. È un *proxy direzionale* — un numero assente rende il claim
certamente infondato, un numero presente lo rende plausibile. Serve a rispondere
"il verificatore vede la differenza?", non "il claim è vero?".

Uso:
    python scripts/probe_table_floor.py [verdetti.jsonl]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg  # noqa: E402
from qdrant_client import models  # noqa: E402
from src.index.store import get_client  # noqa: E402

DEFAULT = ROOT / "eval" / "results" / "verdicts" / "20260812_133954_ledger.jsonl"

#: Numeri "distintivi": con decimale, o almeno quattro cifre. Esclude gli anni,
#: che compaiono in ogni tabella di bilancio e darebbero corrispondenze gratuite.
_NUM = re.compile(r"\d[\d,.]*\d|\d")
_YEAR = re.compile(r"^(19|20)\d\d$")


def numbers(text: str) -> set[str]:
    """I numeri distintivi di un testo, normalizzati per il confronto."""
    out = set()
    for raw in _NUM.findall(text):
        norm = raw.replace(",", "").rstrip(".")
        if _YEAR.match(norm) or "." not in norm and len(norm) < 4:
            continue
        if norm:
            out.add(norm)
    return out


def quartiles(xs: list[float]) -> str:
    xs = sorted(xs)
    if not xs:
        return "-"
    def q(f: float) -> float:
        return xs[min(len(xs) - 1, int(f * len(xs)))]
    return f"mediana {q(.5):.3f}  q1 {q(.25):.3f}  q3 {q(.75):.3f}"


def auc(pos: list[float], neg: list[float]) -> float:
    """P(punteggio positivo > punteggio negativo), pareggi contati mezzi."""
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    dataset = rows[0]["chunk_id"].split(":")[0]

    client = get_client(cfg.QDRANT_URL)
    ids = sorted({r["chunk_id"] for r in rows})
    texts: dict[str, str] = {}
    for i in range(0, len(ids), 64):
        pts, _ = client.scroll(
            dataset,
            scroll_filter=models.Filter(must=[models.FieldCondition(
                key="chunk_id", match=models.MatchAny(any=ids[i:i + 64]))]),
            limit=256, with_payload=["chunk_id", "text"])
        for p in pts:
            texts[p.payload["chunk_id"]] = p.payload["text"]

    present, absent, skipped = [], [], 0
    for r in rows:
        claim_nums = numbers(r["claim"])
        if not claim_nums:
            skipped += 1
            continue
        chunk_nums = numbers(texts.get(r["chunk_id"], ""))
        # "Presente" = **tutti** i numeri distintivi del claim stanno nel chunk.
        # Il criterio piu' severo: se ne manca uno, il claim afferma qualcosa che
        # il chunk non contiene.
        (present if claim_nums <= chunk_nums else absent).append(r)

    thr = cfg.ENTAILMENT_THRESHOLD
    print(f"\n=== {path.name} — {dataset} ===")
    print(f"coppie: {len(rows)}   senza numeri distintivi (escluse): {skipped}")
    for label, group in (("numeri PRESENTI nel chunk", present),
                         ("numeri ASSENTI dal chunk", absent)):
        if not group:
            print(f"\n  {label}: nessuna")
            continue
        scores = [r["score"] for r in group]
        acc = sum(1 for r in group if r["supported"]) / len(group)
        print(f"\n  {label}: {len(group)} coppie")
        print(f"    P(entailment): {quartiles(scores)}")
        print(f"    accettate a soglia {thr}: {acc:.1%}")

    a = auc([r["score"] for r in present], [r["score"] for r in absent])
    print(f"\nAUC presente-vs-assente: {a:.4f}")
    print("  0,5 = il verificatore non distingue un numero presente da uno assente")
    print("  -> in quel caso `citation_precision` su questo genere misura lo strumento,")
    print("     non il generatore, e nessuna riformattazione lo aggiusta (vedi C-08).")


if __name__ == "__main__":
    main()
