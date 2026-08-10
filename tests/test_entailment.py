"""C-03 — the entailment verifier: premise construction and the decision rule.

The model itself is not downloaded here; the session and tokenizer are stubbed.
What is worth testing without a GPU is everything the measurement in
`scripts/probe_entailment.py` decided: that a chunk under the cap becomes **one**
premise (the whole reason for the model swap), that a longer one is covered
completely, that pairs go through one at a time, and that the threshold is read
from config rather than baked in.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as cfg
from src.generation import entailment
from src.generation.entailment import (
    Verdict,
    build_premises,
    normalize_premise,
    p_entailment,
    verify,
)


class _FakeTokenizer:
    """Token == word, ids are integers like the real thing.

    A vocabulary is built as tokens are seen, so `decode(encode(x))` round-trips
    and the window arithmetic can be checked exactly.
    """

    def __init__(self):
        self.truncation = None
        self.padding = True
        self._vocab: list[str] = []
        self._ids: dict[str, int] = {}

    def _id(self, word: str) -> int:
        if word not in self._ids:
            self._ids[word] = len(self._vocab)
            self._vocab.append(word)
        return self._ids[word]

    def encode(self, text, pair=None):
        class E:
            pass

        e = E()
        words = text.split() + ([] if pair is None else pair.split())
        ids = [self._id(w) for w in words]
        if self.truncation:
            ids = ids[:self.truncation]
        e.ids = ids
        e.attention_mask = [1] * len(ids)
        return e

    def decode(self, ids):
        return " ".join(self._vocab[i] for i in ids)

    def no_truncation(self):
        self.truncation = None

    def enable_truncation(self, n):
        self.truncation = n

    def no_padding(self):
        self.padding = False

    def enable_padding(self):
        self.padding = True


class _FakeSession:
    """Returns a fixed entailment probability, and records what it was asked."""

    def __init__(self, p_entail=0.9):
        self.p = p_entail
        self.calls = []

    def run(self, _outputs, feed):
        self.calls.append(feed)
        # Logits whose softmax gives self.p at index 0.
        lo = float(np.log(max(self.p, 1e-9)))
        hi = float(np.log(max(1 - self.p, 1e-9)))
        return [np.array([[lo, hi]], dtype=np.float32)]


@pytest.fixture
def stub(monkeypatch):
    tok, sess = _FakeTokenizer(), _FakeSession()
    monkeypatch.setattr(entailment, "_load", lambda name: (tok, sess))
    return tok, sess


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


class TestBuildPremises:
    def test_short_chunk_is_a_single_premise(self, stub):
        """The point of the model swap. 96% of chunks land here, and with one
        premise the max-over-windows artefact cannot arise."""
        assert build_premises(_words(100), cap=4096) == [_words(100)]

    def test_chunk_exactly_at_the_cap_is_not_split(self, stub):
        assert len(build_premises(_words(4096), cap=4096)) == 1

    def test_chunk_over_the_cap_is_windowed(self, stub):
        assert len(build_premises(_words(4097), cap=4096)) > 1

    def test_windows_cover_the_whole_chunk(self, stub):
        """The bug that produced a false below-chance result during the C-03
        spike: a capped window list left the claim outside every premise."""
        text = _words(5000)
        joined = " ".join(build_premises(text, cap=1000))
        for token in ("w0", "w2500", "w4999"):
            assert token in joined

    def test_windows_overlap(self, stub):
        # Stride is half the cap, so a claim straddling a boundary still lands
        # whole inside some window.
        prem = build_premises(_words(3000), cap=1000)
        assert prem[0].split()[500] in prem[1].split()

    def test_original_text_returned_unsplit_not_a_decode_roundtrip(self, stub):
        """A chunk under the cap comes back byte-identical. Round-tripping it
        through decode would silently reformat every premise for no reason."""
        text = "Il  valore\tmassimo\nè 400ms"
        assert build_premises(text, cap=4096) == [text]


class TestPEntailment:
    def test_one_pair_per_forward_pass(self, stub):
        """Batching pads to the longest member and attention is quadratic in
        that length: a batch of 8 at the cap exhausted the DirectML allocator."""
        _, sess = stub
        p_entailment([("a b", "c"), ("d e", "f"), ("g", "h")])
        assert len(sess.calls) == 3
        for feed in sess.calls:
            assert feed["input_ids"].shape[0] == 1

    def test_padding_is_off(self, stub):
        tok, _ = stub
        p_entailment([("a", "b")])
        assert tok.padding is False

    def test_truncation_set_to_the_model_window(self, stub):
        tok, _ = stub
        p_entailment([("a", "b")])
        assert tok.truncation == cfg.ENTAILMENT_MAX_LEN

    def test_reads_the_entailment_logit(self, stub):
        _, sess = stub
        sess.p = 0.73
        assert p_entailment([("a", "b")])[0] == pytest.approx(0.73, abs=1e-5)

    def test_empty_input(self, stub):
        assert p_entailment([]) == []


class TestVerify:
    def test_supported_above_threshold(self, stub):
        _, sess = stub
        sess.p = 0.9
        assert verify("premessa breve", "un claim", threshold=0.5).supported

    def test_not_supported_below_threshold(self, stub):
        _, sess = stub
        sess.p = 0.2
        assert not verify("premessa breve", "un claim", threshold=0.5).supported

    def test_threshold_is_inclusive(self, stub):
        _, sess = stub
        sess.p = 0.5
        assert verify("premessa", "claim", threshold=0.5).supported

    def test_threshold_defaults_to_config(self, stub):
        _, sess = stub
        sess.p = cfg.ENTAILMENT_THRESHOLD + 0.01
        assert verify("premessa", "claim").supported

    def test_n_premises_is_reported(self, stub):
        """Carried so a run whose scores are inflated by chunk length is visible
        rather than inferred."""
        v = verify(_words(100), "claim")
        assert v.n_premises == 1 and not v.windowed

    def test_windowed_flag_on_a_long_chunk(self, stub):
        with patch.object(cfg, "ENTAILMENT_PREMISE_CAP", 50):
            v = verify(_words(500), "claim")
        assert v.n_premises > 1 and v.windowed

    def test_score_is_the_max_over_premises(self, monkeypatch, stub):
        with patch.object(cfg, "ENTAILMENT_PREMISE_CAP", 50):
            monkeypatch.setattr(entailment, "p_entailment",
                                lambda pairs, model_name=None: [0.1, 0.8, 0.3])
            v = verify(_words(500), "claim")
        assert v.score == pytest.approx(0.8)


class TestNormalizePremise:
    def test_collapses_whitespace(self):
        assert normalize_premise("a  \n\n b\t c ") == "a b c"

    def test_keeps_content(self):
        assert normalize_premise("Ricavi 1.234 | Costi 567") == "Ricavi 1.234 | Costi 567"


class TestVerdict:
    def test_single_premise_is_not_windowed(self):
        assert not Verdict(True, 0.9, 1).windowed
