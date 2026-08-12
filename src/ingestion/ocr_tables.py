"""Parsing delle tabelle OCR dei chunk LEDGER.

I chunk LEDGER sono output Mathpix: prosa con blocchi `<table>` inline. Questo
modulo li riporta a valori — righe di celle — senza far passare il markup per
markup.

Parsing con `html.parser` della standard library e non lxml/beautifulsoup: le
tabelle sono `<tr><td>` da OCR, nessuna dipendenza vale la pena per questo, e
`STACK.md` impone una revisione di licenza per ognuna. (`bs4` risulta importabile
qui come dipendenza transitiva di qualcos'altro: appoggiarcisi significherebbe
usare un pacchetto che il progetto non ha mai dichiarato.)

Stava in `dashboard/chunk_render.py`, scritto per mostrare i chunk a schermo. È
qui perché serve a due cose che non si parlano — la dashboard e il verificatore
di citazioni numeriche di C-09 — e perché la libreria non deve dipendere dalla
dashboard. Il rendering Streamlit resta di là: là c'è `st`, qui no.

**Le celle unite vengono espanse.** Misurato sulle 103 tabelle citate nella run
LEDGER di C-03: il **75%** usa `colspan≥2` e il **72%** `rowspan≥2`, quasi sempre
le stesse. Senza espanderle una riga di dati e la sua intestazione hanno un
numero di colonne diverso, e l'indice della colonna non identifica più niente —
che è ciò che serve per dire a quale *anno* appartiene un numero. La prima
versione del probe di C-09 ha riportato questa limitazione del parser come se
fosse un difetto del generatore, due volte.
"""

from __future__ import annotations

from html.parser import HTMLParser


def _span(attrs: list[tuple[str, str | None]], name: str) -> int:
    """Il valore di colspan/rowspan, 1 se assente o illeggibile.

    Indulgente come il resto del modulo: `colspan="due"` in un OCR non deve far
    fallire la tabella intera, e trattarlo come 1 è la lettura più conservativa.
    """
    for key, value in attrs:
        if key == name and value:
            try:
                return max(1, min(int(value), 64))  # cap: un OCR può dire 9999
            except ValueError:
                return 1
    return 1


class _TableParser(HTMLParser):
    """Raccoglie `<tr>`/`<td>` come righe di `(testo, colspan, rowspan)`.

    Volutamente indulgente: l'output OCR ha tag non chiusi e spaziatura a caso,
    e un parser che si rifiuta su una tabella malformata è inutile esattamente
    quando serve.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[tuple[str, int, int]]] = []
        self._row: list[tuple[str, int, int]] | None = None
        self._cell: list[str] | None = None
        self._span: tuple[int, int] = (1, 1)

    def _flush_cell(self) -> None:
        if self._cell is not None and self._row is not None:
            self._row.append(("".join(self._cell).strip(), *self._span))
            self._cell = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._flush_cell()
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:  # cella fuori da ogni riga
                self._row = []
            self._flush_cell()     # cella precedente mai chiusa
            self._cell = []
            self._span = (_span(attrs, "colspan"), _span(attrs, "rowspan"))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._flush_cell()
        elif tag == "tr" and self._row is not None:
            self._flush_cell()
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def close(self) -> None:  # noqa: D102
        super().close()
        self._flush_cell()
        if self._row:  # ultima riga non chiusa
            self.rows.append(self._row)
            self._row = None


def parse_html_table(html: str) -> list[list[str]]:
    """Markup di tabella -> griglia rettangolare di testo. Vuota se non parsa.

    Le celle unite sono **espanse ripetendo il valore** in ogni posizione che
    occupano. È la stessa cosa che si vede scollegando celle unite in un foglio
    di calcolo, ed è la semantica che serve per cercare: un'intestazione che
    copre due colonne etichetta davvero entrambe, e un'etichetta di riga con
    `rowspan=2` vale davvero per due righe.

    Le righe restano riempite alla stessa larghezza, perché una tabella
    irregolare formi comunque un rettangolo. Riempite e non scartate: una cella
    mancante è un'informazione sull'OCR, non qualcosa da nascondere.
    """
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    if not parser.rows:
        return []

    # Riempimento a griglia: `carry[colonna] = (testo, righe rimanenti)` porta
    # avanti le celle con rowspan, che occupano posizioni nelle righe seguenti
    # senza comparire nel loro markup.
    grid: list[list[str]] = []
    carry: dict[int, tuple[str, int]] = {}
    for raw in parser.rows:
        row: list[str] = []
        col = 0
        for text, cspan, rspan in raw:
            while col in carry:                       # posizione presa da un rowspan
                held, left = carry[col]
                row.append(held)
                carry[col] = (held, left - 1) if left > 1 else None  # type: ignore[assignment]
                if carry[col] is None:
                    del carry[col]
                col += 1
            for _ in range(cspan):
                row.append(text)
                if rspan > 1:
                    carry[col] = (text, rspan - 1)
                col += 1
        while col in carry:                           # rowspan in coda alla riga
            held, left = carry[col]
            row.append(held)
            if left > 1:
                carry[col] = (held, left - 1)
            else:
                del carry[col]
            col += 1
        grid.append(row)

    width = max(len(r) for r in grid)
    return [r + [""] * (width - len(r)) for r in grid]


def table_density(rows: list[list[str]]) -> float:
    """Frazione di celle vuote nella griglia **espansa**.

    Diagnostica, non estetica: le tabelle LEDGER che il routing sotto-spezza più
    aggressivamente sono anche le più vuote, e un chunk fatto quasi solo di celle
    bianche offre pochissimo a un modello di embedding.

    Si misura dopo l'espansione delle celle unite, quindi una cella che ne copre
    sei conta come sei celle piene. È la lettura giusta per "quanta della griglia
    porta informazione", e va tenuta presente confrontandola con i valori
    riportati prima di C-09, che erano calcolati sulla tabella non espansa.
    """
    total = sum(len(r) for r in rows)
    if not total:
        return 0.0
    return sum(1 for r in rows for c in r if not c.strip()) / total
