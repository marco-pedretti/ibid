#!/usr/bin/env python3
"""C-03 spike — is mDeBERTa-XNLI a usable attribution verifier on our chunks?

**This is measurement, not product code.**  C-03 was suspended on 2026-08-10
before any of the entailment pipeline was written, because the probes below
showed the verifier chosen in STACK.md is weak on this corpus.  The script is
committed so the numbers quoted in `docs/progress.md` can be re-derived rather
than believed.

Three probes, each answering a question that had to be settled before designing
a metric on top of the model:

  backend    Is ONNX inference equivalent to the torch reference, and how much
             faster?  (torch-CPU was 1500-5300 ms/pair, which rules it out.)
  length     Does max-pooling P(entail) over windows inflate with chunk length?
             A premise of 512 tokens against chunks with a p90 of 2582 has to be
             split, and every extra window is another chance at a false positive.
  separation Length-matched: can the model tell the chunk a claim was copied from
             out of a chunk from another document?

Usage:
    python scripts/probe_entailment.py backend
    python scripts/probe_entailment.py length    [dataset]
    python scripts/probe_entailment.py separation [dataset] [n]

Requires Qdrant up and the ingested collections.  `backend` additionally needs
torch + transformers, which are NOT declared dependencies — the whole point of
that probe is that they do not need to be.
"""

from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Python puts this script's own directory first on sys.path, where
# `scripts/profile.py` shadows the stdlib `profile` module — which torch imports.
# Any script in scripts/ that touches torch fails with a misleading
# "Could not import module 'GenerationMixin'" until this line runs.
sys.path = [p for p in sys.path if Path(p or ".").resolve() != Path(__file__).parent.resolve()]

import src.config as cfg  # noqa: E402
from src.index.store import get_client  # noqa: E402

#: MIT licensed, and the repo ships its own ONNX export — no third-party
#: conversion in the trust path, no new dependency.
MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"

#: The model's window.  Not a tunable: `max_position_embeddings` is 512.
MAX_LEN = 512
WINDOW, STRIDE = 400, 200

_SENT = re.compile(r"(?<=[.!?])\s+")

_tok: Tokenizer | None = None
_sess: ort.InferenceSession | None = None


def _load() -> tuple[Tokenizer, ort.InferenceSession]:
    global _tok, _sess
    if _tok is None:
        _tok = Tokenizer.from_file(hf_hub_download(MODEL, "tokenizer.json"))
        _sess = ort.InferenceSession(
            hf_hub_download(MODEL, "onnx/model.onnx"),
            providers=["DmlExecutionProvider", "CPUExecutionProvider"],
        )
    return _tok, _sess


def p_entail(pairs: list[tuple[str, str]], batch: int = 16) -> np.ndarray:
    """P(entailment) per (premise, hypothesis). Label 0 of the XNLI head."""
    tok, sess = _load()
    tok.enable_truncation(MAX_LEN)
    tok.enable_padding()
    out = []
    for i in range(0, len(pairs), batch):
        encs = tok.encode_batch(pairs[i:i + batch])
        logits = sess.run(None, {
            "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
        })[0]
        e = np.exp(logits - logits.max(-1, keepdims=True))
        out.append((e / e.sum(-1, keepdims=True))[:, 0])
    return np.concatenate(out) if out else np.array([])


def windows(text: str) -> list[str]:
    """Overlapping token windows covering the WHOLE chunk.

    Capping this list is how the first version of the probe produced a
    below-chance result: with 12 windows a 4810-token chunk was covered up to
    token 2600, the sentence under test fell outside it, and the model was being
    asked to entail a claim from text that did not contain it.
    """
    tok, _ = _load()
    tok.no_truncation()
    ids = tok.encode(text).ids
    tok.enable_truncation(MAX_LEN)
    if len(ids) <= WINDOW:
        return [text]
    return [tok.decode(ids[i:i + WINDOW]) for i in range(0, len(ids), STRIDE)]


def n_windows(text: str) -> int:
    return len(windows(text))


def score(chunk: str, claim: str) -> float:
    return float(p_entail([(w, claim) for w in windows(chunk)]).max())


def clean_sentences(text: str) -> list[str]:
    """Prose sentences only.

    The claims a verifier sees in production are sentences of a generated
    answer.  Feeding it LaTeX fragments, table rows and `#### Abstract` headers
    measures the chunk's formatting, not the model.
    """
    out = []
    for s in _SENT.split(text):
        s = s.strip()
        if not (60 < len(s) < 300) or re.search(r"[$\\{}|]|##|\[\d|^\W", s):
            continue
        if sum(c.isdigit() for c in s) / len(s) > 0.12:
            continue
        if s[0].isupper() and s.endswith("."):
            out.append(s)
    return out


def _chunks(dataset: str, limit: int = 1500) -> list[tuple[str, str]]:
    client = get_client(cfg.QDRANT_URL)
    pts = client.scroll(dataset, limit=limit, with_payload=True)[0]
    return [(p.payload["doc_id"], p.payload["text"]) for p in pts]


def _auc(pos: np.ndarray, neg: np.ndarray) -> float:
    allv = np.concatenate([pos, neg])
    r = allv.argsort().argsort() + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


# --------------------------------------------------------------------------- #

def probe_backend(dataset: str = "open_ragbench") -> None:
    """ONNX vs the torch reference: same verdicts, and how much faster."""
    # torch first, on purpose: creating the DirectML session before importing
    # torch makes the transformers import fail on Windows (both load their own
    # native runtime). The order is the fix, not a coincidence.
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = [t for _, t in _chunks(dataset, 60)][:3]
    hyps = ["The output impedance is difficult to estimate.",
            "Paris is the capital of France.",
            "The proposed method improves accuracy over the baseline."]
    pairs = [(t, h) for t in texts for h in hyps]

    htok = AutoTokenizer.from_pretrained(MODEL)
    hmod = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    enc = htok([p[0] for p in pairs], [p[1] for p in pairs],
               truncation=True, max_length=MAX_LEN, padding=True, return_tensors="pt")
    t0 = time.time()
    with torch.inference_mode():
        ref = hmod(**enc).logits.numpy()
    torch_dt = time.time() - t0
    e = np.exp(ref - ref.max(-1, keepdims=True))
    ref_p = (e / e.sum(-1, keepdims=True))[:, 0]

    # Warm up: session creation and DirectML's per-shape compilation are one-off
    # costs that the torch side does not pay inside its timed block. Leaving them
    # in makes ONNX look 9x faster instead of the ~50x it is.
    p_entail(pairs)
    t0 = time.time()
    onnx_p = p_entail(pairs)
    onnx_dt = time.time() - t0

    print(f"{len(pairs)} coppie")
    print(f"  onnx (DirectML) {onnx_dt * 1000:7.0f} ms  -> {onnx_dt / len(pairs) * 1000:6.1f} ms/coppia")
    print(f"  torch (CPU)     {torch_dt * 1000:7.0f} ms  -> {torch_dt / len(pairs) * 1000:6.1f} ms/coppia")
    print(f"  rapporto        {torch_dt / onnx_dt:.0f}x")
    print(f"  max |delta P(entail)| {np.abs(onnx_p - ref_p).max():.2e}")
    print(f"  verdetti concordi     {int(((onnx_p >= .5) == (ref_p >= .5)).sum())}/{len(pairs)}")


def probe_length(dataset: str = "open_ragbench", n: int = 60) -> None:
    """False positives grow with the number of windows.

    One claim, supported by none of the sampled chunks, so every high score is a
    false positive and the only variable left is how many windows the chunk has.
    """
    rng = random.Random(11)
    texts = [t for _, t in _chunks(dataset, 800)]
    claim = "The proposed method improves accuracy over the baseline on all evaluated datasets."
    rows = [(n_windows(t), score(t, claim)) for t in rng.sample(texts, min(n, len(texts)))]

    print(f"{dataset}: {len(rows)} chunk, un claim che nessuno di essi supporta")
    for lo, hi in ((1, 1), (2, 3), (4, 8), (9, 10**6)):
        g = [r for r in rows if lo <= r[0] <= hi]
        if not g:
            continue
        med = float(np.median([r[1] for r in g]))
        print(f"  {lo:2d}-{hi if hi < 10**6 else '+':<3} finestre  n={len(g):2d}  "
              f"P max mediana {med:.3f}  sopra 0.5: {sum(r[1] >= .5 for r in g)}/{len(g)}")
    corr = float(np.corrcoef([r[0] for r in rows], [r[1] for r in rows])[0, 1])
    print(f"  correlazione (n finestre, P max): {corr:.3f}")


def probe_separation(dataset: str = "open_ragbench", n: int = 25) -> None:
    """Length-matched floor test: claim copied verbatim from the chunk.

    Each negative chunk is drawn with the *same window count* as its positive,
    so the comparison cannot be won by length alone.  Without that matching the
    AUC comes out below chance, which is the length artefact and not a signal.
    """
    rng = random.Random(3)
    pool = _chunks(dataset)
    # Window counts once for the whole pool: recomputing them per candidate
    # tokenises 1500 chunks for every case and makes n=60 unaffordable.
    counted = [(d, t, n_windows(t)) for d, t in pool]
    by_count: dict[int, list[tuple[str, str]]] = {}
    for d, t, k in counted:
        by_count.setdefault(k, []).append((d, t))

    cands = [(d, t, k) for d, t, k in counted if clean_sentences(t)]
    rng.shuffle(cands)

    cases = []
    for d, t, k in cands:
        alts = [x for dd, x in by_count[k] if dd != d]
        if not alts:
            continue
        cases.append((rng.choice(clean_sentences(t)), t, rng.choice(alts), k))
        if len(cases) >= n:
            break

    pos = np.array([score(g, c) for c, g, _, _ in cases])
    neg = np.array([score(o, c) for c, _, o, _ in cases])
    print(f"{dataset}: {len(cases)} coppie, finestre appaiate "
          f"(mediana {int(np.median([c[3] for c in cases]))})")
    print(f"  claim verbatim dal chunk  mediana {np.median(pos):.4f}  "
          f"sopra 0.5: {(pos >= .5).sum()}/{len(pos)}")
    print(f"  claim da altro documento  mediana {np.median(neg):.4f}  "
          f"sopra 0.5: {(neg >= .5).sum()}/{len(neg)}")
    print(f"  AUC {_auc(pos, neg):.4f}")


PROBES = {"backend": probe_backend, "length": probe_length, "separation": probe_separation}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROBES:
        raise SystemExit(f"uso: probe_entailment.py {{{'|'.join(PROBES)}}} [dataset] [n]")
    args = [a if not a.isdigit() else int(a) for a in sys.argv[2:]]
    PROBES[sys.argv[1]](*args)
