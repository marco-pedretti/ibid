"""Verifica di citazioni numeriche contro tabelle (C-09).

**Perché esiste.** Su LEDGER il 96,7% delle affermazioni generate asserisce dei
numeri presi da tabelle di bilancio OCR, e il verificatore NLI di C-03 non le sa
giudicare: su claim i cui numeri sono *dimostrabilmente* nel chunk citato ne
accetta il **28,0%**, contro il **58,6%** sulla prosa (`scripts/probe_table_floor.py`).
Non è un problema di formattazione — C-08 ha reso le tabelle in righe leggibili
e il numero non si è mosso (p=0,1112, punteggi spostati simmetricamente). È che
la domanda posta non è linguistica: *«cerca la cella giusta e confronta un
numero»* non è un'inferenza.

**Perché è la versione semplice.** La misura di scoping dice che il generatore
non sbaglia: sui claim con il numero presente, nomina l'etichetta di **riga**
giusta nel 78,6% dei casi e l'**anno** giusto nell'89,8%. Quindi lo strumento
deve cercare numeri ed etichette, non capire le tabelle.

**Il nome della metrica è diverso di proposito.** `citation_precision` resta ciò
che misura l'NLI; questa produce `numeric_citation_precision`. Due strumenti con
definizioni diverse i cui numeri finiscano nella stessa colonna renderebbero i
due dataset non confrontabili — che è la cosa che il §3.1 vieta, e la trappola
che la decisione di OQ-05 doveva evitare.

**Limiti noti, trovati leggendo i disaccordi con l'NLI** (2 casi su 131):

- *etichetta di riga vuota* — alcune righe di queste tabelle non hanno una
  cella-etichetta, e senza etichetta non c'e' niente da far combaciare. Il
  verdetto e' `UNSUPPORTED` dove sarebbe piu' onesto `NOT_APPLICABLE`.
- *claim troncato dallo splitter* — `split_claims` di C-03 taglia le frasi, e un
  frammento come *«for the year ended September 30, 2017, was $4,033,000»* ha
  perso il soggetto, quindi non nomina la riga. Non e' un errore del generatore
  ne' del verificatore: e' un difetto a monte, nella segmentazione.

**Tre esiti, non due.** `NOT_APPLICABLE` non è `UNSUPPORTED`: un claim senza
numeri distintivi, o il cui numero sta nella prosa e non in una tabella, non è
sbagliato — è fuori dal dominio di questo strumento e va all'NLI. Confondere
"non lo so misurare" con "è falso" è esattamente il difetto che C-09 corregge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import src.config as cfg
from src.ingestion.ocr_tables import parse_html_table
from src.ingestion.pipeline_table_heavy import _split_segments

#: Numeri "distintivi": con decimale, o almeno quattro cifre. Gli anni sono
#: esclusi perché compaiono in ogni tabella di bilancio e darebbero
#: corrispondenze gratuite — servono invece a disambiguare la *colonna*.
_NUM = re.compile(r"\d[\d,.]*\d|\d")
_YEAR = re.compile(r"^(19|20)\d\d$")

#: Parole troppo comuni perché la loro presenza in un claim significhi qualcosa.
_STOP = frozenset({
    "the", "of", "and", "for", "in", "to", "a", "an", "is", "was", "were",
    "total", "net", "other", "year", "years", "ended", "december", "31",
})


class Outcome(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class NumericVerdict:
    """Un giudizio, con l'evidenza che l'ha prodotto.

    L'evidenza è tenuta perché un verdetto senza il *perché* non è auditabile, e
    perché il tasso di `NOT_APPLICABLE` è la misura di quanto lavoro resta
    all'NLI.
    """

    outcome: Outcome
    numbers: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    row_label: str = ""
    column: str = ""
    reason: str = ""

    @property
    def supported(self) -> bool:
        return self.outcome is Outcome.SUPPORTED


@dataclass(frozen=True)
class Cell:
    """Dove un numero sta nella griglia."""

    row_label: str
    column: str | None   # None quando la tabella non espone una riga di anni


def numbers(text: str) -> set[str]:
    """I numeri distintivi di un testo, normalizzati per il confronto."""
    out: set[str] = set()
    for raw in _NUM.findall(text):
        norm = raw.replace(",", "").rstrip(".")
        if not norm or _YEAR.match(norm) or ("." not in norm and len(norm) < 4):
            continue
        out.add(norm)
    return out


def years(text: str) -> set[str]:
    """Gli anni nominati da un testo — servono a disambiguare la colonna."""
    return {n.replace(",", "") for n in _NUM.findall(text)
            if _YEAR.match(n.replace(",", ""))}


def words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w and w not in _STOP}


def _year_header(rows: list[list[str]]) -> tuple[list[str] | None, int]:
    """La riga che porta gli anni, e quante righe di intestazione consumare.

    Le intestazioni di questi bilanci sono **a due livelli**: la prima riga è
    spesso una fascia (`Year ended September 30,`) e gli anni stanno sotto. Si
    cerca quindi fra le prime tre righe la prima con almeno due anni; se non c'è,
    la colonna è indeterminabile — che non è la stessa cosa che sbagliata.
    """
    for i, row in enumerate(rows[:3]):
        if sum(1 for c in row if _YEAR.match(c.strip().replace(",", ""))) >= 2:
            return row, i + 1
    # Nessuna riga di anni. Con piu' righe la prima e' quasi sempre
    # un'intestazione testuale e va comunque saltata; con una riga sola non c'e'
    # intestazione da saltare, e saltarla perderebbe l'unico dato della tabella.
    return None, 1 if len(rows) > 1 else 0


def table_cells(chunk_text: str) -> dict[str, list[Cell]]:
    """numero -> celle in cui compare, con etichetta di riga e colonna.

    Si appoggia a `parse_html_table`, che da C-09 espande `colspan` e `rowspan`:
    senza quell'espansione l'indice di colonna di una riga dati non corrisponde a
    quello della sua intestazione, e il 75% di queste tabelle usa celle unite.
    """
    out: dict[str, list[Cell]] = {}
    for kind, segment in _split_segments(chunk_text):
        if kind != "table":
            continue
        rows = parse_html_table(segment)
        if not rows:
            continue
        header, skip = _year_header(rows)
        for row in rows[skip:]:
            label = next((c for c in row if c.strip() and not numbers(c)), "")
            for j, cell in enumerate(row):
                for n in numbers(cell):
                    col = header[j] if header and j < len(header) else None
                    out.setdefault(n, []).append(Cell(label, col))
    return out


def _row_matches(label: str, claim_words: set[str]) -> bool:
    """Metà delle parole di contenuto dell'etichetta compaiono nel claim.

    Metà e non tutte: *«Cost of goods sold»* diventa `{cost, goods, sold}` dopo
    le stopword, e un claim che scrive per esteso le ha tutte — ma la soglia
    lascia passare anche le riformulazioni parziali. È un compromesso, ed è la
    prima cosa da guardare se il tasso di `UNSUPPORTED` risulta più alto del
    previsto: la soglia è in `config.py`.
    """
    w = words(label)
    if not w:
        return False
    return len(w & claim_words) >= max(1, round(len(w) * cfg.NUMERIC_ROW_MATCH_RATIO))


def verify_numeric(claim: str, chunk_text: str) -> NumericVerdict:
    """Il chunk citato sostiene i numeri che il claim asserisce?

    La regola, in ordine — ogni passo è una cosa che si può stabilire senza
    inferenza:

    1. **Nessun numero distintivo** → `NOT_APPLICABLE`: è un claim di prosa e
       tocca all'NLI.
    2. **Un numero non compare nel chunk** → `UNSUPPORTED`. È l'unico verdetto
       negativo certo: il chunk non contiene ciò che il claim afferma.
    3. **Nessun numero sta in una tabella** → `NOT_APPLICABLE`: i numeri sono
       nella prosa del chunk, dove questo strumento non ha etichette su cui
       ragionare. Sono 35 casi su 161 nel campione di riferimento.
    4. **L'anno è contraddetto** → `UNSUPPORTED`. Se il claim nomina un anno e
       *tutte* le celle candidate stanno in colonne di anni diversi, il claim
       attribuisce il numero all'esercizio sbagliato.
    5. **L'etichetta di riga combacia** → `SUPPORTED`, altrimenti `UNSUPPORTED`.

    Il passo 4 penalizza la **contraddizione**, non il silenzio: un claim che non
    nomina l'anno non viene punito per questo, perché l'89,8% di quelli corretti
    lo nomina ma il restante 10% no, e rifiutarli sarebbe un falso negativo dello
    strumento invece di un errore del generatore.
    """
    asserted = numbers(claim)
    if not asserted:
        return NumericVerdict(Outcome.NOT_APPLICABLE, reason="nessun numero distintivo")

    in_chunk = numbers(chunk_text)
    missing = tuple(sorted(asserted - in_chunk))
    if missing:
        return NumericVerdict(
            Outcome.UNSUPPORTED, tuple(sorted(asserted)), missing,
            reason="numeri assenti dal chunk",
        )

    cells = table_cells(chunk_text)
    candidates = [c for n in asserted for c in cells.get(n, [])]
    if not candidates:
        return NumericVerdict(
            Outcome.NOT_APPLICABLE, tuple(sorted(asserted)),
            reason="numeri presenti ma fuori da una tabella",
        )

    claim_years = years(claim)
    if claim_years:
        with_year = [c for c in candidates if c.column and years(c.column)]
        if with_year and not any(years(c.column or "") & claim_years for c in with_year):
            return NumericVerdict(
                Outcome.UNSUPPORTED, tuple(sorted(asserted)),
                column=with_year[0].column or "",
                reason="il numero sta in una colonna di un altro anno",
            )

    claim_words = words(claim)
    for cell in candidates:
        if _row_matches(cell.row_label, claim_words):
            return NumericVerdict(
                Outcome.SUPPORTED, tuple(sorted(asserted)),
                row_label=cell.row_label, column=cell.column or "",
                reason="numero e etichetta di riga combaciano",
            )
    return NumericVerdict(
        Outcome.UNSUPPORTED, tuple(sorted(asserted)),
        row_label=candidates[0].row_label,
        reason="il claim non nomina la riga in cui il numero si trova",
    )
