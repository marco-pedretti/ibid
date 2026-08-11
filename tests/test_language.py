"""C-05 — detecting the language of an answer, and whether it uses only one.

The failure this guards against is a false positive: a detector that labels a
formula, a company name or a two-word abstention as "another language" would
report mixed-language answers that do not exist, and C-05 would be chasing its
own instrument.  `unknown` is therefore a first-class answer here.

Validated against the 891 stored generations before being trusted: 873 English,
18 `unknown`, **0 mixed** — no false positives on real data.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.generation.language import (
    MIN_EVIDENCE,
    UNKNOWN,
    detect,
    matches_query,
    profile,
)

EN = "The maximum value is 400ms and the model outperforms the baseline."
IT = "Il valore massimo è di 400ms e il modello supera la linea di base."
ES = "El valor máximo es 400ms y el modelo supera la línea base."
FR = "La valeur maximale est de 400ms et le modèle dépasse les autres."
DE = "Der maximale Wert ist 400ms und das Modell ist besser als die Basis."


class TestDetect:
    def test_english(self):
        assert detect(EN) == "en"

    def test_italian(self):
        assert detect(IT) == "it"

    def test_spanish(self):
        assert detect(ES) == "es"

    def test_french(self):
        assert detect(FR) == "fr"

    def test_german(self):
        assert detect(DE) == "de"

    def test_italian_is_not_stolen_by_french(self):
        """`il` belongs to both. Dropping it outright was the first attempt and
        it cost Italian its most frequent marker; weighting keeps it useful."""
        assert detect("Secondo il contesto, i ricavi del 2017 sono stati elevati.") == "it"


class TestUnknownIsAnAnswer:
    def test_formula(self):
        assert detect(r"$\Psi_{r} \subseteq[0,1]^{p}$") == UNKNOWN

    def test_proper_noun(self):
        # Real case from the corpus: the ASVspoof 2021 "LA" set, which a
        # keyword scan reads as the Italian article.
        assert detect("ASVspoof 2021 LA and DF sets") == UNKNOWN

    def test_numbers_only(self):
        assert detect("Revenue 2017: 14980 million") == UNKNOWN

    def test_empty(self):
        assert detect("") == UNKNOWN

    def test_two_words_without_function_words(self):
        """The abstention phrase itself cannot be language-identified, and
        saying so is more useful than guessing."""
        assert detect("Insufficient information.") == UNKNOWN

    def test_single_stray_marker_is_not_evidence(self):
        assert detect("The die was cast") != "de"


class TestProfile:
    def test_single_language_answer_is_not_mixed(self):
        p = profile(EN + " " + "This confirms the earlier finding of the study.")
        assert not p.is_mixed and p.dominant == "en"

    def test_two_languages_is_mixed(self):
        p = profile(EN + " " + IT)
        assert p.is_mixed and p.languages == {"en", "it"}

    def test_unknown_sentence_does_not_make_an_answer_mixed(self):
        """An unlabelled sentence is missing evidence, not evidence of a second
        language. Counting it as one would flag every answer containing LaTeX."""
        p = profile(EN + r" $x = 400$")
        assert not p.is_mixed and p.n_unknown == 1

    def test_dominant_is_the_majority(self):
        p = profile(f"{EN} {EN} {IT}")
        assert p.dominant == "en"

    def test_newline_separated_list_items_are_sentences(self):
        p = profile(f"- {EN}\n- {IT}")
        assert p.is_mixed

    def test_empty_answer(self):
        p = profile("")
        assert p.dominant == UNKNOWN and not p.is_mixed


class TestMatchesQuery:
    def test_same_language(self):
        assert matches_query(EN, "What is the maximum value of the measured latency?") is True

    def test_different_language(self):
        assert matches_query(EN, "Qual è il valore massimo della latenza misurata?") is False

    def test_none_when_the_question_is_unidentifiable(self):
        """Distinct from a real mismatch: there is nothing to compare."""
        assert matches_query(EN, "EBITDA 2017?") is None

    def test_none_when_the_answer_is_unidentifiable(self):
        assert matches_query("$x=1$", "What is the maximum value of the latency?") is None


class TestThresholds:
    def test_min_evidence_is_above_one_shared_word(self):
        """Two words shared with another language are worth one unshared word,
        so the floor has to sit above a single ambiguous hit."""
        assert MIN_EVIDENCE > 1.0
