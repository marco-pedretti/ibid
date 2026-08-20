#!/usr/bin/env python3
"""OQ-08 — quanti chunk di LEDGER non hanno niente da leggere, e se qualcuno li pesca.

**Misura, non codice di produzione.** Committato perche' i numeri citati in
`docs/open-questions.md` (OQ-08) si possano ri-derivare invece che credere.

Nati guardando la mappa dell'esploratore (U-06): il pezzo piu' piccolo di
`NYSE_SHW_2017` era largo 19 caratteri e conteneva `![](images/0_0.jpg)`, quello
di `NASDAQ_LOOP_2017` 32 e conteneva `Powered by TCPDF (www.tcpdf.org)`. Non
sono chunk piccoli: sono pagine di servizio del PDF, indicizzate ed embeddate
come tutte le altre.

Due conti, e il secondo e' quello che conta:

1. **Quanti sono**, esatto. Si conta sui `.mmd`, che sono la sorgente: il loader
   generico produce un chunk per pagina non vuota, quindi il conto non e'
   campionato.

2. **Se arrivano al modello.** I dump di generazione su disco portano i
   `chunk_ids` mandati in contesto: e' una misura gia' pagata, e risponde alla
   domanda che rende il primo conto interessante o irrilevante.

**Cosa NON dimostra.** Che non vengano mai recuperati: i dump coprono 900 query
con `top_k=5`, non le 10.000 del golden set intero. Dice che su quel campione non
ne e' arrivato **nessuno**, il che e' un limite superiore stretto, non uno zero
dimostrato.

Uso:
    python scripts/probe_chunk_vuoti.py
    python scripts/probe_chunk_vuoti.py --esempi 10
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.datasets.ledger import PAGE_SEP

MMD = ROOT / "data" / "ledger" / "eval" / "mmd"
GENERAZIONI = ROOT / "eval" / "results" / "generations"

#: Un riferimento a un'immagine in Markdown: si toglie prima di giudicare, perche'
#: una copertina che e' solo un'immagine non ha niente da leggere.
IMMAGINE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

#: Cio' che resta e non e' contenuto. L'elenco viene dall'osservazione, non
#: dall'immaginazione: sono le tre forme che compaiono davvero.
VUOTO = re.compile(
    r"^(powered by tcpdf.*|\[?this page intentionally left blank\.?\]?|\s)*$", re.I
)


def senza_contenuto(testo: str) -> bool:
    return VUOTO.match(IMMAGINE.sub("", testo).strip()) is not None


def conta() -> set[str]:
    """Stampa quanti sono e restituisce i loro `chunk_id`."""
    if not MMD.exists():
        print(f"nessun documento in {MMD} -- serve `make fetch-datasets`")
        return set()

    totale = 0
    per_documento: Counter[str] = Counter()
    forme: Counter[str] = Counter()
    vuoti: set[str] = set()

    for f in sorted(MMD.glob("*.mmd")):
        doc = f.stem
        pagine = [
            p.strip()
            for p in f.read_text(encoding="utf-8", errors="replace").split(PAGE_SEP)
        ]
        n = 0
        for pagina in pagine:
            if not pagina:
                continue
            chunk_id = f"ledger:{doc}:{n:04d}"
            n += 1
            totale += 1
            if senza_contenuto(pagina):
                vuoti.add(chunk_id)
                per_documento[doc] += 1
                forme[
                    IMMAGINE.sub("", pagina).strip()[:44] or "(solo un'immagine)"
                ] += 1

    print(
        f"== l'indice: {totale} chunk, senza contenuto {len(vuoti)} ({len(vuoti) / totale:.2%})"
    )
    print(
        f"   documenti che ne hanno almeno uno: {len(per_documento)} su {len(list(MMD.glob('*.mmd')))}"
    )
    for testo, n in forme.most_common(6):
        print(f"      {n:5d}x  {testo!r}")
    return vuoti


def pescati(vuoti: set[str], mostra: int) -> None:
    dump = sorted(glob.glob(str(GENERAZIONI / "*ledger*.jsonl")))
    if not dump:
        print(f"\nnessun dump in {GENERAZIONI}")
        return

    print("\n== arrivano al modello? (chunk mandati in contesto, dai dump su disco)")
    trovati: list[str] = []
    for f in dump:
        righe = [
            json.loads(r)
            for r in Path(f).read_text(encoding="utf-8").splitlines()
            if r.strip()
        ]
        mandati = [c for r in righe for c in r.get("chunk_ids", [])]
        colpiti = [c for c in mandati if c in vuoti]
        trovati += colpiti
        quante = sum(
            1 for r in righe if any(c in vuoti for c in r.get("chunk_ids", []))
        )
        print(
            f"   {Path(f).name:34s} {len(mandati):5d} in contesto, senza contenuto "
            f"{len(colpiti):3d}, in {quante} query su {len(righe)}"
        )
    if trovati:
        print(f"\n   i primi {min(mostra, len(trovati))}:")
        for c in trovati[:mostra]:
            print(f"      {c}")
    else:
        print("\n   nessuno. Sono nell'indice e non finiscono in contesto: vedi OQ-08.")


def main() -> None:
    ap = argparse.ArgumentParser(description="OQ-08: i chunk senza contenuto di LEDGER")
    ap.add_argument(
        "--esempi", type=int, default=8, help="quanti chunk pescati elencare"
    )
    a = ap.parse_args()
    pescati(conta(), a.esempi)


if __name__ == "__main__":
    main()
