"""Tests for src/generation/numeric_verify.py (C-09).

Il verificatore numerico esiste perché l'NLI di C-03 accetta solo il 28% dei
claim i cui numeri sono dimostrabilmente nel chunk citato, contro il 58,6% sulla
prosa. Qui si fissa la regola di decisione, che è tutta stabilibile senza
inferenza — ed è il motivo per cui questi test non hanno bisogno di un modello.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as cfg
from src.generation.numeric_verify import (
    Outcome,
    numbers,
    table_cells,
    verify_numeric,
    words,
    years,
)

TABLE = """Consolidated results.
<table>
<tr><td></td><td colspan="2">Year ended September 30,</td></tr>
<tr><td></td><td>2017</td><td>2016</td></tr>
<tr><td>Cost of goods sold</td><td>8,265.0</td><td>7,100.5</td></tr>
<tr><td>Capital expenditures</td><td>222.8</td><td>210.1</td></tr>
</table>
Footnote text."""


class TestNumbers:
    def test_years_are_not_distinctive(self):
        """Gli anni compaiono in ogni tabella di bilancio: usarli come prova di
        supporto darebbe corrispondenze gratuite. Servono per la colonna."""
        assert numbers("revenue in 2017") == set()
        assert years("revenue in 2017") == {"2017"}

    def test_commas_normalised(self):
        assert numbers("was $8,265.0 million") == {"8265.0"}

    def test_short_integers_ignored(self):
        """`5` o `12` in una frase non identificano niente."""
        assert numbers("the top 5 items and 12 others") == set()

    def test_four_digit_integers_kept(self):
        assert "1234" in numbers("a value of 1234")

    def test_decimals_kept_even_if_short(self):
        assert "3.40" in numbers("a dividend of $3.40 per share")


class TestTableCells:
    def test_number_located_with_row_and_column(self):
        cells = table_cells(TABLE)
        assert "8265.0" in cells
        cell = cells["8265.0"][0]
        assert cell.row_label == "Cost of goods sold"
        assert cell.column == "2017"

    def test_second_year_column_resolves(self):
        """Il valore del 2016 deve risultare nella colonna del 2016: è il caso
        che l'espansione di `colspan` ha reso possibile."""
        assert table_cells(TABLE)["7100.5"][0].column == "2016"

    def test_prose_numbers_are_not_cells(self):
        assert table_cells("Revenue grew to 1234.5 last year.") == {}


class TestDecisionRule:
    def _outcome(self, claim: str) -> Outcome:
        return verify_numeric(claim, TABLE).outcome

    def test_number_row_and_year_all_match(self):
        assert self._outcome(
            "The cost of goods sold in 2017 was $8,265.0 million."
        ) is Outcome.SUPPORTED

    def test_absent_number_is_the_only_certain_negative(self):
        v = verify_numeric("Revenue was $9,999.9 million.", TABLE)
        assert v.outcome is Outcome.UNSUPPORTED
        assert v.missing == ("9999.9",)

    def test_wrong_year_is_unsupported(self):
        """Il numero c'è e la riga è giusta, ma appartiene a un altro esercizio."""
        assert self._outcome(
            "The cost of goods sold in 2016 was $8,265.0 million."
        ) is Outcome.UNSUPPORTED

    def test_wrong_row_is_unsupported(self):
        assert self._outcome(
            "Capital expenditures in 2017 were $8,265.0 million."
        ) is Outcome.UNSUPPORTED

    def test_silence_on_the_year_is_not_punished(self):
        """L'89,8% dei claim corretti nomina l'anno; il restante 10% no.
        Rifiutarli sarebbe un falso negativo dello strumento, non un errore del
        generatore — la regola penalizza la contraddizione, non il silenzio."""
        assert self._outcome(
            "The cost of goods sold was $8,265.0 million."
        ) is Outcome.SUPPORTED


class TestNotApplicableIsNotUnsupported:
    """La distinzione che C-09 esiste per introdurre.

    Confondere «non lo so misurare» con «è falso» è il difetto che rendeva
    `citation_precision` illeggibile su LEDGER.
    """

    def test_claim_without_numbers_goes_to_the_nli(self):
        v = verify_numeric("The company performed well this year.", TABLE)
        assert v.outcome is Outcome.NOT_APPLICABLE

    def test_number_in_prose_goes_to_the_nli(self):
        """Sono 35 casi su 161 nel campione di riferimento: numeri veri, ma senza
        etichette di riga su cui questo strumento possa ragionare."""
        chunk = "Revenue reached 1234.5 million during the period."
        v = verify_numeric("Revenue was 1234.5 million.", chunk)
        assert v.outcome is Outcome.NOT_APPLICABLE

    def test_not_applicable_is_not_supported(self):
        v = verify_numeric("The company performed well.", TABLE)
        assert v.supported is False


class TestRowMatchRatio:
    def test_ratio_comes_from_config(self, monkeypatch):
        """Una soglia in `config.py` e non nel modulo: §3.4, e perché il suo
        effetto si possa esplorare senza toccare il codice."""
        claim = "Goods figures for 2017 include $8,265.0 million."
        monkeypatch.setattr(cfg, "NUMERIC_ROW_MATCH_RATIO", 1.0)
        assert verify_numeric(claim, TABLE).outcome is Outcome.UNSUPPORTED
        monkeypatch.setattr(cfg, "NUMERIC_ROW_MATCH_RATIO", 0.3)
        assert verify_numeric(claim, TABLE).outcome is Outcome.SUPPORTED

    def test_stopwords_do_not_carry_a_match(self):
        """Un'etichetta fatta solo di parole comuni non può far combaciare
        niente: senza questo, `Total` combacerebbe con qualunque claim."""
        assert words("Total of the year") == set()


class TestVerdictCarriesEvidence:
    def test_supported_verdict_names_row_and_column(self):
        v = verify_numeric("Cost of goods sold in 2017 was 8,265.0.", TABLE)
        assert v.row_label == "Cost of goods sold"
        assert v.column == "2017"
        assert v.reason

    def test_every_outcome_has_a_reason(self):
        for claim in ("no numbers here", "value 9999.9", "Cost of goods sold 8,265.0"):
            assert verify_numeric(claim, TABLE).reason


@pytest.mark.parametrize("chunk", ["", "no table", "<table></table>", "<table><tr></tr></table>"])
def test_degenerate_chunks_do_not_raise(chunk):
    assert verify_numeric("value 1234.5", chunk).outcome in tuple(Outcome)
