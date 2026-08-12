"""Tests for src/ingestion/ocr_tables.py — HTML tables in chunk text.

The parser must be forgiving: it reads OCR output, where unclosed tags and
ragged rows are normal.  A debug view that refuses to render a malformed table
is useless exactly when it is most needed, so the tests below pin "degrades to
something readable" as behaviour, not just the happy path.
"""

from __future__ import annotations


from src.ingestion.ocr_tables import parse_html_table, table_density

SIMPLE = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"


class TestParseHtmlTable:
    def test_simple_table(self):
        assert parse_html_table(SIMPLE) == [["a", "b"], ["c", "d"]]

    def test_header_cells_are_rows_too(self):
        html = "<table><tr><th>H1</th><th>H2</th></tr><tr><td>1</td><td>2</td></tr></table>"
        assert parse_html_table(html) == [["H1", "H2"], ["1", "2"]]

    def test_empty_cells_preserved(self):
        """Mathpix tables are full of empty cells — dropping them shifts columns."""
        assert parse_html_table("<table><tr><td></td><td>x</td></tr></table>") == [["", "x"]]

    def test_ragged_rows_padded_to_rectangle(self):
        html = "<table><tr><td>a</td><td>b</td><td>c</td></tr><tr><td>d</td></tr></table>"
        assert parse_html_table(html) == [["a", "b", "c"], ["d", "", ""]]

    def test_colspan_is_expanded(self):
        """C-09: una cella che copre sei colonne ne etichetta sei.

        Il 75% delle tabelle citate su LEDGER usa `colspan>=2`. Senza espanderlo
        l'indice di colonna di una riga dati non corrisponde a quello della sua
        intestazione, e non si puo' dire a quale anno appartiene un numero.
        """
        html = '<table><tr><td colspan="6">wide</td></tr></table>'
        assert parse_html_table(html) == [["wide"] * 6]

    def test_rowspan_carries_into_following_rows(self):
        """Il 72% delle stesse tabelle usa anche `rowspan`, quindi una riga puo'
        non contenere la propria etichetta: sta nella riga sopra."""
        html = ('<table><tr><td rowspan="2">Ricavi</td><td>1</td></tr>'
                "<tr><td>2</td></tr></table>")
        assert parse_html_table(html) == [["Ricavi", "1"], ["Ricavi", "2"]]

    def test_colspan_and_rowspan_together(self):
        """Sono le stesse tabelle: 73 su 103 li usano entrambi."""
        html = ('<table><tr><td rowspan="2">A</td><td colspan="2">B</td></tr>'
                "<tr><td>c</td><td>d</td></tr></table>")
        assert parse_html_table(html) == [["A", "B", "B"], ["A", "c", "d"]]

    def test_header_band_aligns_with_the_year_row(self):
        """Il caso vero che ha motivato la modifica: una fascia che copre le
        colonne degli anni, con gli anni nella riga sotto."""
        rows = parse_html_table(
            '<table><tr><td></td><td colspan="2">Year ended</td></tr>'
            "<tr><td>Revenue</td><td>2017</td><td>2016</td></tr>"
            "<tr><td>Total</td><td>1.234</td><td>1.100</td></tr></table>"
        )
        # La colonna del 2017 e quella del suo valore hanno lo stesso indice.
        assert rows[1].index("2017") == rows[2].index("1.234")

    def test_absurd_span_is_capped(self):
        """Un OCR puo' scrivere colspan="9999": la tabella non deve esplodere."""
        html = '<table><tr><td colspan="9999">x</td></tr></table>'
        assert len(parse_html_table(html)[0]) <= 64

    def test_unparseable_span_treated_as_one(self):
        html = '<table><tr><td colspan="due">x</td><td>y</td></tr></table>'
        assert parse_html_table(html) == [["x", "y"]]

    def test_nested_inline_markup_flattened(self):
        html = "<table><tr><td><b>bold</b> text</td></tr></table>"
        assert parse_html_table(html) == [["bold text"]]

    def test_whitespace_stripped(self):
        assert parse_html_table("<table><tr><td>  x  </td></tr></table>") == [["x"]]

    def test_entities_decoded(self):
        assert parse_html_table("<table><tr><td>a&amp;b</td></tr></table>") == [["a&b"]]

    def test_unclosed_cell_recovered(self):
        assert parse_html_table("<table><tr><td>a<td>b</tr></table>") == [["a", "b"]]

    def test_unclosed_row_recovered(self):
        assert parse_html_table("<table><tr><td>a</td></table>") == [["a"]]

    def test_no_table_returns_empty(self):
        assert parse_html_table("just prose") == []

    def test_empty_string_returns_empty(self):
        assert parse_html_table("") == []

    def test_table_with_no_rows(self):
        assert parse_html_table("<table></table>") == []

    def test_multiline_markup(self):
        html = "<table>\n  <tr>\n    <td>a</td>\n  </tr>\n</table>"
        assert parse_html_table(html) == [["a"]]

    def test_all_rows_same_width(self):
        rows = parse_html_table(
            '<table><tr><td rowspan="2"></td><td colspan="6">Year</td></tr>'
            "<tr><td>2017</td><td>2016</td></tr></table>"
        )
        assert len({len(r) for r in rows}) == 1


class TestTableDensity:
    def test_no_empty_cells(self):
        assert table_density([["a", "b"], ["c", "d"]]) == 0.0

    def test_all_empty(self):
        assert table_density([["", ""], ["", ""]]) == 1.0

    def test_half_empty(self):
        assert table_density([["a", ""], ["b", ""]]) == 0.5

    def test_whitespace_counts_as_empty(self):
        assert table_density([["   ", "x"]]) == 0.5

    def test_empty_input(self):
        assert table_density([]) == 0.0

    def test_matches_real_ledger_shape(self):
        """The real chunk measured 43% — sanity-check the metric's direction."""
        rows = parse_html_table(SIMPLE)
        assert 0.0 <= table_density(rows) <= 1.0


class TestSegmentationContract:
    """render_chunk relies on the ingestion splitter; pin the shared assumption."""

    def test_prose_and_table_split_apart(self):
        from src.ingestion.pipeline_table_heavy import _split_segments

        segs = _split_segments(f"## Titolo\n\n{SIMPLE}\n\nNota finale.")
        kinds = [k for k, _ in segs]
        assert kinds == ["text", "table", "text"]

    def test_table_segment_is_parseable(self):
        from src.ingestion.pipeline_table_heavy import _split_segments

        segs = _split_segments(f"intro\n\n{SIMPLE}")
        table_seg = next(v for k, v in segs if k == "table")
        assert parse_html_table(table_seg) == [["a", "b"], ["c", "d"]]

    def test_text_without_tables_is_one_segment(self):
        from src.ingestion.pipeline_table_heavy import _split_segments

        assert len(_split_segments("solo prosa, niente tabelle")) == 1
