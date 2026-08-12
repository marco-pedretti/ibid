"""Parsing delle tabelle OCR dei chunk LEDGER.

I chunk LEDGER sono output Mathpix: prosa con blocchi `<table>` inline. Questo
modulo li riporta a valori — righe di celle — senza far passare il markup per
markup.

Parsing con `html.parser` della standard library e non lxml/beautifulsoup: le
tabelle sono `<tr><td>` piatti da OCR, nessuna dipendenza vale la pena per
questo, e `STACK.md` impone una revisione di licenza per ognuna. (`bs4` risulta
importabile qui come dipendenza transitiva di qualcos'altro: appoggiarcisi
significherebbe usare un pacchetto che il progetto non ha mai dichiarato.)

Stava in `dashboard/chunk_render.py`, scritto per mostrare i chunk a schermo. È
qui perché serve a due cose che non si parlano — la dashboard e il verificatore
di entailment di C-03 — e perché la libreria non deve dipendere dalla dashboard.
Il rendering Streamlit resta di là: là c'è `st`, qui no.
"""

from __future__ import annotations

from html.parser import HTMLParser


class _TableParser(HTMLParser):
    """Raccoglie il contenuto di `<tr>`/`<td>` come lista di righe.

    Volutamente indulgente: l'output OCR ha tag non chiusi e spaziatura a caso,
    e un parser che si rifiuta su una tabella malformata è inutile esattamente
    quando serve.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            if self._row is None:  # cella fuori da ogni riga
                self._row = []
            if self._cell is not None:  # cella precedente mai chiusa: la si scarica
                self._row.append("".join(self._cell).strip())
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:  # ultima cella non chiusa
                self._row.append("".join(self._cell).strip())
                self._cell = None
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def close(self) -> None:  # noqa: D102
        super().close()
        if self._row:  # ultima riga non chiusa
            if self._cell is not None:
                self._row.append("".join(self._cell).strip())
            self.rows.append(self._row)
            self._row = None


def parse_html_table(html: str) -> list[list[str]]:
    """Markup di tabella -> righe di testo. Lista vuota se non parsa niente.

    Le righe sono riempite alla stessa larghezza perché una tabella irregolare
    (colspan, celle mancanti) formi comunque un rettangolo. Riempite e non
    scartate: una cella mancante è un'informazione sull'OCR, non qualcosa da
    nascondere.
    """
    parser = _TableParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []
    rows = parser.rows
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def table_density(rows: list[list[str]]) -> float:
    """Frazione di celle vuote.

    Diagnostica, non estetica: le tabelle LEDGER che il routing sotto-spezza più
    aggressivamente sono anche le più vuote, e un chunk fatto quasi solo di celle
    bianche offre pochissimo a un modello di embedding.
    """
    total = sum(len(r) for r in rows)
    if not total:
        return 0.0
    return sum(1 for r in rows for c in r if not c.strip()) / total
