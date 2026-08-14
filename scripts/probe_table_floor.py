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

**`--rows` restringe la specifica del verificatore numerico (OQ-05, opzione 2).**
Del 72% che il verificatore rifiuta pur avendo il numero davanti non sappiamo
quanto sia colpa sua e quanto siano claim che citano la *riga* o l'*anno*
sbagliati. Sono due difetti diversi e chiedono due strumenti diversi: cercare
cifre e' mezza giornata di lavoro, capire la struttura di una tabella OCR sono
giorni. `--rows` risale dalla cella che contiene il numero alla sua etichetta di
riga e alla sua intestazione di colonna, e guarda se il claim le nomina.

Uso:
    python scripts/probe_table_floor.py [verdetti.jsonl]
    python scripts/probe_table_floor.py [verdetti.jsonl] --rows
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from qdrant_client import models
from src.index.store import get_client
from src.generation.numeric_verify import Outcome, verify_numeric
from src.ingestion.ocr_tables import parse_html_table
from src.ingestion.ocr_tables import split_segments

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


#: Parole troppo comuni perche' la loro presenza nel claim significhi qualcosa.
_STOP = {"the", "of", "and", "for", "in", "to", "a", "total", "net", "other",
         "year", "years", "ended", "december", "31", "$", "-", ""}


def words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in _STOP}


def _year_header(rows: list[list[str]]) -> tuple[list[str] | None, int]:
    """La riga che porta gli anni, e quante righe di intestazione consumare.

    **Le intestazioni sono a due livelli.** Misurato sulle tabelle vere: la prima
    riga e' spesso una fascia che copre piu' colonne — `['', 'Year ended
    September 30,', '']` — e gli anni stanno nella riga sotto. Prendere `rows[0]`
    come intestazione, che era la prima versione di questo probe, faceva
    risultare la colonna "non nominata dal claim" nel 77% dei casi: un difetto
    dell'euristica riportato come difetto del modello.

    Si cerca quindi, fra le prime tre righe, la prima che contenga almeno due
    anni. Se non c'e', la colonna e' **non determinabile** — che e' diverso da
    "sbagliata", e va contato a parte.
    """
    for i, row in enumerate(rows[:3]):
        if sum(1 for c in row if _YEAR.match(c.strip().replace(",", ""))) >= 2:
            return row, i + 1
    return None, 1


def cells_by_number(chunk_text: str) -> dict[str, list[tuple[str, str | None]]]:
    """numero -> [(etichetta di riga, intestazione di colonna o None), ...].

    L'etichetta di riga e' la prima cella non numerica della riga. La colonna e'
    `None` quando la tabella non espone una riga di anni riconoscibile.
    """
    out: dict[str, list[tuple[str, str | None]]] = {}
    for kind, seg in split_segments(chunk_text):
        if kind != "table":
            continue
        rows = parse_html_table(seg)
        if len(rows) < 2:
            continue
        # Da C-09 `parse_html_table` espande colspan e rowspan, quindi gli
        # indici di colonna di una riga dati e della sua intestazione
        # corrispondono. Prima non era vero -- il 75% di queste tabelle usa celle
        # unite -- e questo probe si rifiutava di leggere la colonna piuttosto
        # che leggerla male.
        header, skip = _year_header(rows)
        for row in rows[skip:]:
            label = next((c for c in row if c.strip() and not numbers(c)), "")
            for j, cell in enumerate(row):
                for n in numbers(cell):
                    col = header[j] if header and j < len(header) else None
                    out.setdefault(n, []).append((label, col))
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


def analyse_rows(present: list[dict], texts: dict[str, str]) -> None:
    """Dei claim con il numero presente, quanti nominano anche riga e colonna?"""
    located = row_ok = col_ok = both = unlocated = col_known = 0
    for r in present:
        table = cells_by_number(texts.get(r["chunk_id"], ""))
        claim_words = words(r["claim"])
        hits = [c for n in numbers(r["claim"]) for c in table.get(n, [])]
        if not hits:
            unlocated += 1          # il numero c'e' nel testo ma non in una cella
            continue
        located += 1
        # Basta che **una** delle celle candidate combaci: se il numero compare
        # piu' volte nella tabella, il claim e' sostenuto quando almeno una di
        # quelle occorrenze e' quella giusta.
        def label_matches(label: str) -> bool:
            """Meta' delle parole di contenuto dell'etichetta compaiono nel claim.

            Meta' e non tutte: "Cost of goods sold" diventa {cost, goods, sold}
            dopo le stopword, e un claim che dice "the cost of goods sold was..."
            le ha tutte, ma uno che dice "COGS for 2017" non ne ha nessuna. La
            soglia a meta' e' un compromesso, e come tale va letta.
            """
            w = words(label)
            return bool(w) and len(w & claim_words) * 2 >= len(w)

        r_ok = any(label_matches(lab) for lab, _ in hits)
        with_col = [c for _, c in hits if c is not None]
        row_ok += r_ok
        if with_col:
            col_known += 1
            c_ok = any(words(c) & claim_words for c in with_col)
            col_ok += c_ok
            both += r_ok and c_ok

    print(f"\n--- struttura, sui {len(present)} claim con numeri presenti ---")
    print(f"  numero trovato dentro una cella di tabella : {located}"
          f"   (fuori da tabelle: {unlocated})")
    if not located:
        return
    print(f"  il claim nomina anche l'etichetta di RIGA   : {row_ok}/{located} = {row_ok / located:.1%}")
    if col_known:
        print(f"  colonna (anno) determinabile               : {col_known}/{located}")
        print(f"    e il claim la nomina                     : {col_ok}/{col_known} = {col_ok / col_known:.1%}")
        print(f"    riga e colonna insieme                   : {both}/{col_known} = {both / col_known:.1%}")
    else:
        print("  colonna (anno): **mai determinabile su questo campione**")
        print("    il 74,8% delle tabelle usa colspan e il parser non lo espande,")
        print("    quindi l'anno di un numero non e' ricostruibile. E' un requisito")
        print("    per il verificatore numerico, non un difetto del generatore.")


def compare_verifiers(rows: list[dict], texts: dict[str, str]) -> None:
    """Il verificatore numerico di C-09 contro l'NLI, sulle stesse coppie.

    E' la validazione che il criterio di C-09 chiede. Il confronto e' onesto
    solo sul sottoinsieme che il numerico dichiara di saper giudicare: dove
    risponde NOT_APPLICABLE il lavoro resta all'NLI, e contarlo come un
    fallimento dell'uno o dell'altro sarebbe la confusione che C-09 corregge.
    """
    from collections import Counter
    kinds: Counter[str] = Counter()
    agree = nli_yes = num_yes = 0
    for r in rows:
        v = verify_numeric(r["claim"], texts.get(r["chunk_id"], ""))
        kinds[v.outcome.value] += 1
        if v.outcome is Outcome.NOT_APPLICABLE:
            continue
        nli_yes += r["supported"]
        num_yes += v.supported
        agree += r["supported"] == v.supported

    judged = kinds["supported"] + kinds["unsupported"]
    print(f"\n--- C-09 contro l'NLI, sulle stesse {len(rows)} coppie ---")
    for k in ("supported", "unsupported", "not_applicable"):
        print(f"  {k:<16} {kinds[k]:>4}  ({kinds[k] / len(rows):.1%})")
    if not judged:
        return
    print(f"\n  sulle {judged} coppie che il numerico giudica:")
    print(f"    accettate dal numerico : {num_yes:>4} = {num_yes / judged:.1%}")
    print(f"    accettate dall'NLI     : {nli_yes:>4} = {nli_yes / judged:.1%}")
    print(f"    i due concordano       : {agree:>4} = {agree / judged:.1%}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_rows = "--rows" in sys.argv
    want_numeric = "--numeric" in sys.argv
    path = Path(args[0]) if args else DEFAULT
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

    if want_rows:
        analyse_rows(present, texts)
    if want_numeric:
        compare_verifiers(rows, texts)

    a = auc([r["score"] for r in present], [r["score"] for r in absent])
    print(f"\nAUC presente-vs-assente: {a:.4f}")
    print("  0,5 = il verificatore non distingue un numero presente da uno assente")
    print("  -> in quel caso `citation_precision` su questo genere misura lo strumento,")
    print("     non il generatore, e nessuna riformattazione lo aggiusta (vedi C-08).")


if __name__ == "__main__":
    main()
