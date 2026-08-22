#!/usr/bin/env python3
"""OQ-07 — il segno di un numero appartiene al prospetto, non alla grandezza.

**Misura, non codice di produzione.** Committato perche' i numeri citati in
`docs/open-questions.md` (OQ-07) si possano ri-derivare invece che credere.

Nei bilanci le parentesi sono la notazione contabile del negativo, e in un
rendiconto finanziario una spesa in conto capitale e' un deflusso: compare come
`(222.8)`. La stessa grandezza, nella tabella riassuntiva dello stesso
documento, compare come `222.8`. Il segno e' una proprieta' del **prospetto**,
non della quantita' -- e una cella copiata in prosa se lo porta dietro.

Due misure indipendenti, nessuna delle quali tocca la GPU:

1. **Nel corpus** (`--corpus`): quante celle numeriche sono fra parentesi, e in
   quanti documenti la *stessa* grandezza compare in tutte e due le forme. E'
   la misura che rende il caso osservato una proprieta' del genere invece che
   un aneddoto.

2. **Nelle risposte gia' generate** (`--risposte`): quante portano un numero fra
   parentesi dentro la prosa. I dump di generazione sono su disco dal C-01, e
   le risposte con la loro citazione ci sono gia'.

**Cosa NON dimostra.** Che quei numeri siano *trapianti*. Una perdita, un
decremento, una rettifica sono negativi veri, e li' le parentesi ci vogliono:
separarli chiede di leggere la riga del chunk citato, ed e' il passo 1 del
protocollo di OQ-07. Questo probe misura quanto e' grande il bacino, non quanta
parte di esso e' un errore.

**Sulla soglia delle grandezze.** Il confronto "con e senza" tiene solo i
decimali di almeno tre cifre. Contando anche gli interi tondi il numero sale
molto, ma dentro ci finiscono coincidenze come `100` e `1000` che compaiono in
tabelle senza rapporto fra loro: e' una misura piu' alta e meno vera.

Uso:
    python scripts/probe_sign_convention.py
    python scripts/probe_sign_convention.py --corpus --documenti 200
    python scripts/probe_sign_convention.py --risposte
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg  # noqa: E402
from src.index.store import get_by_chunk_id, get_client  # noqa: E402

MMD = ROOT / "data" / "ledger" / "eval" / "mmd"
GENERAZIONI = ROOT / "eval" / "results" / "generations"

#: Il contenuto di una cella di tabella. I documenti di LEDGER sono Mathpix
#: Markdown: le tabelle restano in HTML, ed e' li' che stanno i numeri.
_CELLA = re.compile(r"<td[^>]*>([^<]*)</td>")
_FRA_PARENTESI = re.compile(r"^\s*\$?\s*\(\s*([\d,]+\.?\d*)\s*\)\s*$")
_NUDA = re.compile(r"^\s*\$?\s*([\d,]+\.?\d*)\s*$")

#: In prosa: un numero decimale fra parentesi, con o senza il simbolo di valuta.
#: Decimale e non intero perche' `(1)` e `(2)` in un bilancio sono richiami a
#: nota, non importi.
_IN_PROSA = re.compile(r"\(\s*\$?\s*[\d,]+\.\d+\s*\)")


def _grandezza(cella: str) -> tuple[str, str] | None:
    """`("par" | "nuda", valore normalizzato)` per una cella numerica."""
    m = _FRA_PARENTESI.match(cella)
    if m:
        return "par", m.group(1).replace(",", "")
    m = _NUDA.match(cella)
    if m:
        return "nuda", m.group(1).replace(",", "")
    return None


def corpus(quanti: int, seme: int) -> None:
    file = sorted(MMD.glob("*.mmd"))
    if not file:
        print(f"nessun documento in {MMD} -- serve `make fetch-datasets`")
        return
    random.seed(seme)
    campione = random.sample(file, min(quanti, len(file)))

    par = nuda = 0
    con_parentesi = 0
    ambivalenti: list[int] = []
    esempi: list[tuple[str, list[str]]] = []

    for f in campione:
        testo = f.read_text(encoding="utf-8", errors="replace")
        p: Counter[str] = Counter()
        n: Counter[str] = Counter()
        for cella in _CELLA.findall(testo):
            g = _grandezza(cella)
            if g is None:
                continue
            (p if g[0] == "par" else n)[g[1]] += 1
        par += sum(p.values())
        nuda += sum(n.values())
        if p:
            con_parentesi += 1
        # Solo decimali di almeno tre cifre: vedi la nota in testa.
        comuni = sorted(
            x for x in set(p) & set(n) if "." in x and len(x.replace(".", "")) >= 3
        )
        if comuni:
            ambivalenti.append(len(comuni))
            if len(esempi) < 5:
                esempi.append((f.stem, comuni[:5]))

    tot = par + nuda
    print(f"== il corpus ({len(campione)} documenti su {len(file)})")
    print(f"   celle numeriche: {tot}")
    print(f"   fra parentesi:   {par} ({par / max(1, tot):.1%})")
    print(
        f"   documenti con almeno una cella fra parentesi: "
        f"{con_parentesi} ({con_parentesi / len(campione):.0%})"
    )
    print(
        f"   documenti in cui la stessa grandezza compare in tutte e due le forme: "
        f"{len(ambivalenti)} ({len(ambivalenti) / len(campione):.0%})"
    )
    if ambivalenti:
        ambivalenti.sort()
        print(
            f"      quante per documento: mediana {ambivalenti[len(ambivalenti) // 2]}, "
            f"massimo {ambivalenti[-1]}"
        )
    for nome, valori in esempi:
        print(f"      {nome}: {', '.join(valori)}")


def risposte(mostra: int) -> None:
    dump = sorted(GENERAZIONI.glob("*ledger*.jsonl"))
    if not dump:
        print(f"nessun dump in {GENERAZIONI}")
        return
    print(f"\n== le risposte gia' generate ({len(dump)} run su LEDGER)")
    campioni: list[str] = []
    for f in dump:
        righe = [
            json.loads(r)
            for r in f.read_text(encoding="utf-8").splitlines()
            if r.strip()
        ]
        # Le astenute non affermano niente, quindi non possono trapiantare niente.
        vive = [x for x in righe if not x.get("abstained")]
        con = [x for x in vive if _IN_PROSA.search(x.get("answer") or "")]
        quota = len(con) / len(vive) if vive else 0.0
        print(
            f"   {f.name:34s} {len(vive):4d} non astenute, con parentesi in prosa: "
            f"{len(con):3d} ({quota:.0%})"
        )
        for x in con:
            m = _IN_PROSA.search(x["answer"])
            assert m is not None
            frase = " ".join(x["answer"][max(0, m.start() - 90) : m.end() + 45].split())
            campioni.append(frase)

    print(f"\n   {len(campioni)} casi in tutto. I primi {min(mostra, len(campioni))}:")
    for frase in campioni[:mostra]:
        print(f"      … {frase}")
    print("\n   Quanti di questi siano trapianti e quanti negativi veri lo dice")
    print("   `--righe`, che risale alla riga del chunk citato (passo 1).")


_TR = re.compile(r"<tr>(.*?)</tr>", re.S)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def _senza_tag(cella: str) -> str:
    return re.sub(r"<[^>]+>", "", cella).strip()


def righe(mostra: int) -> None:
    """Il passo 1: per ogni caso, l'etichetta di riga della cella citata.

    **Deduplicare e' meta' del risultato.**  Il conto grezzo dice 43 casi, ma
    sono le stesse domande viste in sei run: per `(query_id, numero)` distinti
    sono **13**.  Un bacino contato con le ripetizioni dentro fa sembrare la
    classe tre volte piu' grande di com'e', ed e' l'errore che la trappola
    «contare il bacino come se fosse l'errore» prevedeva in una forma sola --
    qui ne aveva due.

    **La classificazione non la fa questo codice, e non e' pigrizia.**  La
    distinzione fra trapianto e negativo vero sta nella semantica
    dell'etichetta: «Capital expenditures» nomina una **grandezza**, e le
    parentesi attorno al numero sono la notazione del prospetto; «Net financing
    cash» e «Basic net loss per share» nominano una **quantita' con segno**, e
    li' il negativo e' l'informazione.  Distinguerle con una regex su `Net|loss`
    darebbe una risposta che sembra misurata e non lo e'.  Il codice porta
    quindi le prove -- etichetta, cella, celle vicine -- e il verdetto sta
    scritto in `docs/open-questions.md`, dove si puo' contestare riga per riga.
    """
    dump = sorted(GENERAZIONI.glob("*ledger*.jsonl"))
    casi: dict[tuple[str, str], tuple[list[str], list[int]]] = {}
    for f in dump:
        for riga in f.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            d = json.loads(riga)
            if d.get("abstained"):
                continue
            for num in re.findall(
                r"\(\s*\$?\s*([\d,]+\.\d+)\s*\)", d.get("answer") or ""
            ):
                casi.setdefault(
                    (d["query_id"], num), (d["chunk_ids"], d.get("markers") or [])
                )

    print("\n== la riga del chunk citato, per ogni caso distinto (passo 1)")
    print(f"   {len(casi)} coppie (domanda, numero) distinte, dalle {len(dump)} run")

    cliente = get_client(cfg.QDRANT_URL)
    for (q, n), (cids, mk) in casi.items():
        trovate = []
        for m in mk or [1]:
            if m - 1 >= len(cids):
                continue
            payload = get_by_chunk_id(cliente, "ledger", cids[m - 1])
            if payload is None:
                continue
            for tr in _TR.findall(payload.get("text", "")):
                celle = [_senza_tag(c) for c in _TD.findall(tr)]
                nudo = n.replace(",", "")
                if any(nudo in c.replace(",", "") for c in celle[1:]):
                    vicine = [c for c in celle[1:] if c][:4]
                    trovate.append(f"[{m}] {celle[0][:58]!r} -> {vicine}")
                    break
        print(f"   {q:32s} ({n:>9s})  " + ("; ".join(trovate) or "riga non trovata"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", action="store_true", help="solo la misura sul corpus")
    ap.add_argument("--risposte", action="store_true", help="solo la misura sui dump")
    ap.add_argument(
        "--righe", action="store_true", help="solo il passo 1: le etichette"
    )
    ap.add_argument(
        "--documenti", type=int, default=120, help="quanti documenti campionare"
    )
    ap.add_argument("--seme", type=int, default=0, help="il seme del campione")
    ap.add_argument("--mostra", type=int, default=8, help="quante frasi stampare")
    a = ap.parse_args()

    entrambe = not (a.corpus or a.risposte or a.righe)
    if a.corpus or entrambe:
        corpus(a.documenti, a.seme)
    if a.risposte or entrambe:
        risposte(a.mostra)
    if a.righe or entrambe:
        righe(a.mostra)


if __name__ == "__main__":
    main()
