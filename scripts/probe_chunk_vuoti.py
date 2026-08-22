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

3. **Se vengono recuperati**, che e' una domanda piu' larga della seconda e la
   contiene. Il passo 2 guarda i chunk **mandati in contesto** -- `top_k=5` su
   900 query -- e un chunk morto potrebbe comparire in fondo a un top-10 senza
   mai entrare in un top-5. I dump di recupero coprono **tutte** le query del
   golden set alla profondita' di valutazione, quindi chiudono il buco che il
   passo 2 lasciava aperto.

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
RECUPERI = Path("eval/results/retrieved")
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


def recuperati(vuoti: set[str], mostra: int) -> None:
    """Il passo 1 del protocollo di OQ-08: cercarli nel **recupero**.

    La differenza col conto di `pescati` non e' di misura ma di domanda. Li'
    si guarda cosa e' arrivato al modello, cioe' un top-5 su 900 query; qui si
    guarda cosa il recupero ha **restituito**, alla profondita' con cui viene
    valutato e su tutte le query del golden set. Un nodo morto che non vince
    mai ma compare al decimo posto e' invisibile al primo conto e visibile a
    questo.

    Se non compaiono nemmeno qui, la questione e' chiusa come **igiene**: 498
    punti che occupano memoria e nodi del grafo senza servire a nessuno, da
    togliere all'ingestione quando ci sara' un'altra ragione per ri-ingerire --
    non prima, perche' cancellarli dall'indice vivo cambierebbe il numero di
    punti sotto misure gia' registrate.
    """
    dump = sorted(glob.glob(str(RECUPERI / "*ledger*.jsonl")))
    if not dump:
        print(f"\nnessun dump di recupero in {RECUPERI}")
        return

    print(
        "\n== vengono recuperati? (dump di recupero, tutte le query, profondita' di valutazione)"
    )
    trovati: list[str] = []
    for f in dump:
        righe = [
            json.loads(r)
            for r in Path(f).read_text(encoding="utf-8").splitlines()
            if r.strip()
        ]
        resi = [c for r in righe for c in r.get("chunk_ids", [])]
        colpiti = [c for c in resi if c in vuoti]
        trovati += colpiti
        quante = sum(
            1 for r in righe if any(c in vuoti for c in r.get("chunk_ids", []))
        )
        prof = max((len(r.get("chunk_ids", [])) for r in righe), default=0)
        print(
            f"   {Path(f).name:44s} {len(righe):5d} query x {prof} = {len(resi):6d} resi, "
            f"senza contenuto {len(colpiti):3d}, in {quante} query"
        )
    if not trovati:
        print("\n   nessuno. Nemmeno in fondo a un top-10: la questione e' igiene.")
        return
    for f in dump:
        danno(Path(f), vuoti, mostra)


def qrels(dataset: str) -> dict[str, set[str]]:
    """I chunk d'oro per query, dal golden set.  `relevance > 0` e' rilevante."""
    fuori: dict[str, set[str]] = {}
    percorso = ROOT / "eval" / "golden" / f"{dataset}.jsonl"
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        if not riga.strip():
            continue
        d = json.loads(riga)
        fuori[d["query_id"]] = {
            q["chunk_id"] for q in d.get("qrels", []) if q.get("relevance", 0) > 0
        }
    return fuori


def danno(dump: Path, vuoti: set[str], mostra: int) -> None:
    """Quanto costa davvero avere dei nodi morti in cima.

    **Il conto grezzo non basta a decidere.**  Sapere che 46 risultati su
    centomila sono vuoti non dice niente finche' non si sa *dove* cadono: al
    decimo posto non li vede nessuno, perche' la generazione prende i primi
    cinque.  E anche dentro i primi cinque contano solo se hanno **spinto
    fuori** qualcosa che serviva: uno slot sprecato su una query che comunque
    non aveva il suo chunk d'oro nel top-10 non cambia nessuna metrica.

    Il conto simula quindi la rimozione: si tolgono i vuoti dalla lista, si
    riprende il top-5, e si guarda in quante query entra un chunk d'oro che
    prima non c'era.  E' esattamente il delta di `R@5` che l'igiene
    comprerebbe, misurato invece che stimato.
    """
    righe = [
        json.loads(r)
        for r in dump.read_text(encoding="utf-8").splitlines()
        if r.strip()
    ]
    dataset = righe[0]["query_id"] and dump.name.split("_")[2]
    oro = qrels(dataset)

    rango: Counter[int] = Counter()
    per_documento: Counter[str] = Counter()
    con_vuoti = 0
    guadagnate: list[str] = []
    for r in righe:
        ids = r.get("chunk_ids", [])
        for i, c in enumerate(ids, 1):
            if c in vuoti:
                rango[i] += 1
        if not any(c in vuoti for c in ids[:5]):
            continue
        con_vuoti += 1
        for c in ids[:5]:
            if c in vuoti:
                per_documento[c.split(":")[1]] += 1
        g = oro.get(r["query_id"], set())
        puliti = [c for c in ids if c not in vuoti][:5]
        if g and set(puliti) & g and not set(ids[:5]) & g:
            guadagnate.append(r["query_id"])

    entro5 = sum(n for i, n in rango.items() if i <= 5)
    print(
        "\n   distribuzione per rango: "
        + "  ".join(f"{i}:{rango[i]}" for i in sorted(rango))
    )
    print(
        f"   dentro il top-5: {entro5} su {sum(rango.values())}, in {con_vuoti} query"
    )
    print(f"   query che guadagnerebbero un chunk d'oro togliendoli: {len(guadagnate)}")
    if guadagnate:
        print(f"      {guadagnate[:mostra]}")
    print("   documenti da cui vengono quelli in top-5:")
    for k, v in per_documento.most_common(mostra):
        print(f"      {k}: {v}")


def main() -> None:
    ap = argparse.ArgumentParser(description="OQ-08: i chunk senza contenuto di LEDGER")
    ap.add_argument(
        "--esempi", type=int, default=8, help="quanti chunk pescati elencare"
    )
    a = ap.parse_args()
    vuoti = conta()
    pescati(vuoti, a.esempi)
    recuperati(vuoti, a.esempi)


if __name__ == "__main__":
    main()
