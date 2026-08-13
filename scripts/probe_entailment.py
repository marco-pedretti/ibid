#!/usr/bin/env python3
"""C-03 spike — which entailment model can verify attribution on our chunks?

**This is measurement, not product code.**  C-03 was suspended on 2026-08-10
before any of the entailment pipeline was written, because these probes showed
the verifier originally chosen in STACK.md is weak on this corpus.  `compare`
then settled the replacement.  The script is committed so the numbers quoted in
`docs/progress.md` and `STACK.md` can be re-derived rather than believed.

Four probes, each answering a question that had to be settled before designing a
metric on top of a model:

  backend    Is ONNX inference equivalent to the torch reference, and how much
             faster?  (torch-CPU was 1500-5300 ms/pair, which rules it out.)
  length     Does max-pooling P(entail) over windows inflate with chunk length?
             A premise of 512 tokens against chunks with a p90 of 2582 has to be
             split, and every extra window is another chance at a false positive.
  separation Length-matched: can the model tell the chunk a claim was copied from
             out of a chunk from another document?
  compare    The same cases, scored by both models. `separation` answers "is this
             one good enough"; this answers "is that one better", which cannot be
             settled by two independent runs on two different samples.

`length` and `separation` deliberately still run the **superseded** model: their
numbers are what `docs/progress.md` records as the reason for replacing it, and
they have to stay reproducible.  `compare` runs both.

Usage:
    python scripts/probe_entailment.py backend
    python scripts/probe_entailment.py length     [dataset]
    python scripts/probe_entailment.py separation [dataset] [n]
    python scripts/probe_entailment.py compare    [dataset] [n]

Requires Qdrant up and the ingested collections.  `backend` additionally needs
torch + transformers, which are NOT declared dependencies — the whole point of
that probe is that they do not need to be.
"""

from __future__ import annotations

import math
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

# Qui c'era una riga che si toglieva `scripts/` da `sys.path`, perche'
# `scripts/profile.py` faceva ombra al modulo `profile` della standard library --
# che torch importa -- e ogni script di questa cartella che toccasse torch
# falliva con un fuorviante "Could not import module 'GenerationMixin'".
#
# Rimossa in Q-03: lo script si chiama `profile_docs.py` e il conflitto non
# esiste piu'. Curare il sintomo in un file solo lasciava la causa in piedi per
# tutti gli altri.

import src.config as cfg  # noqa: E402
from src.index.store import get_client  # noqa: E402

#: The **superseded** verifier, kept because `length` and `separation` measured
#: it and those numbers are the recorded reason for replacing it.  MIT, and the
#: repo ships its own ONNX export — no third-party conversion in the trust path.
MODEL = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"

#: The model's window.  Not a tunable: `max_position_embeddings` is 512.
MAX_LEN = 512
WINDOW, STRIDE = 400, 200

#: The verifier chosen in STACK.md after `compare`.  MIT, multilingual, ships
#: its own ONNX, 8194-token window, binary entailment/not_entailment head.
#: 99% of our chunks fit in one pass, which removes the multiple-comparison
#: artefact by construction instead of calibrating around it.
ALT_MODEL = "MoritzLaurer/bge-m3-zeroshot-v2.0"

#: Above this the quadratic attention costs more than windowing: measured 123 ms
#: at 758 tokens, 762 ms at 2951, but 19.7 s at 7693.  96% of chunks are under
#: the cap and get a single clean pass; the tail falls back to windows.
ALT_CAP = 4096

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



# --------------------------------------------------------------------------- #

class Scorer:
    """One model behind one interface: (chunk, claim) -> P(entailment).

    `compare` needs two models alive in the same run, which the module-level
    `_load` cache cannot express.  Both heads put entailment at index 0 —
    three-way for XNLI, binary for the zero-shot model — so the same column is
    read in both cases.
    """

    def __init__(self, model: str, max_len: int, window: int, stride: int, batch: int = 8):
        self.max_len, self.window, self.stride = max_len, window, stride
        # Attention is quadratic in sequence length and padding fills the batch
        # up to its longest member, so 8 sequences at 4096 tokens ask for ~8 GB
        # of attention matrices and the DirectML allocator refuses outright.
        # The long-context model runs one at a time; that also stops it paying
        # for padding it does not need.
        self.batch = batch
        path = hf_hub_download(model, "onnx/model.onnx")
        try:
            # Exports above 2 GB keep their weights in a sibling file, which
            # onnxruntime resolves by name at session creation.
            hf_hub_download(model, "onnx/model.onnx_data")
        except Exception:
            pass
        self.tok = Tokenizer.from_file(hf_hub_download(model, "tokenizer.json"))
        self.sess = ort.InferenceSession(
            path, providers=["DmlExecutionProvider", "CPUExecutionProvider"])

    def close(self) -> None:
        """Drop the session: 1.1 GB and 2.3 GB of weights resident at once on a
        12 GB card is avoidable pressure for no benefit."""
        self.sess = None

    def _p(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        self.tok.enable_truncation(self.max_len)
        if self.batch > 1:
            self.tok.enable_padding()
        else:
            self.tok.no_padding()
        out = []
        for i in range(0, len(pairs), self.batch):
            encs = self.tok.encode_batch(pairs[i:i + self.batch])
            logits = self.sess.run(None, {
                "input_ids": np.array([e.ids for e in encs], dtype=np.int64),
                "attention_mask": np.array([e.attention_mask for e in encs], dtype=np.int64),
            })[0]
            e = np.exp(logits - logits.max(-1, keepdims=True))
            out.append((e / e.sum(-1, keepdims=True))[:, 0])
        return np.concatenate(out) if out else np.array([])

    def _windows(self, text: str) -> list[str]:
        self.tok.no_truncation()
        ids = self.tok.encode(text).ids
        self.tok.enable_truncation(self.max_len)
        if len(ids) <= self.window:
            return [text]
        return [self.tok.decode(ids[i:i + self.window])
                for i in range(0, len(ids), self.stride)]

    def score(self, chunk: str, claim: str) -> float:
        return float(self._p([(w, claim) for w in self._windows(chunk)]).max())


def _se_auc(a: float, n1: int, n2: int) -> float:
    """Hanley-McNeil standard error of an AUC."""
    return math.sqrt((a * (1 - a) + (n1 - 1) * (a / (2 - a) - a * a)
                      + (n2 - 1) * (2 * a * a / (1 + a) - a * a)) / (n1 * n2))


def _mcnemar(b: int, c: int) -> float:
    """Two-sided exact McNemar on discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def probe_compare(dataset: str = "open_ragbench", n: int = 60) -> None:
    """The same floor test, the same cases, two models.

    Case construction is deliberately model-independent: negatives are matched on
    token count under one fixed reference tokenizer, not on window count, because
    "window count" means different things to a 512-token model and an 8192-token
    one and would hand each model a different sample.
    """
    rng = random.Random(3)
    pool = _chunks(dataset)
    tok, _ = _load()
    tok.no_truncation()
    counts = [len(tok.encode(t).ids) for _, t in pool]
    tok.enable_truncation(MAX_LEN)

    def bucket(k: int) -> int:
        return min(k // 500, 8)

    by_bucket: dict[int, list[tuple[str, str]]] = {}
    for (d, t), k in zip(pool, counts):
        by_bucket.setdefault(bucket(k), []).append((d, t))

    cands = [(d, t, k) for (d, t), k in zip(pool, counts) if clean_sentences(t)]
    rng.shuffle(cands)
    cases = []
    for d, t, k in cands:
        alts = [x for dd, x in by_bucket[bucket(k)] if dd != d]
        if not alts:
            continue
        cases.append((rng.choice(clean_sentences(t)), t, rng.choice(alts)))
        if len(cases) >= n:
            break

    print(f"{dataset}: {len(cases)} coppie, identiche per entrambi i modelli")
    res = {}
    for name, build in (
        ("mDeBERTa-512", lambda: Scorer(MODEL, MAX_LEN, WINDOW, STRIDE)),
        ("bge-m3-8192", lambda: Scorer(ALT_MODEL, 8192, ALT_CAP, ALT_CAP // 2, batch=1)),
    ):
        sc = build()
        t0 = time.time()
        pos = np.array([sc.score(g, c) for c, g, _ in cases])
        neg = np.array([sc.score(o, c) for c, _, o in cases])
        sc.close()
        auc = _auc(pos, neg)
        se = _se_auc(auc, len(pos), len(neg))
        res[name] = (pos, neg)
        print(f"\n  {name}   ({time.time() - t0:.0f}s)")
        print(f"    claim verbatim   mediana {np.median(pos):.4f}   "
              f"sopra 0.5: {(pos >= .5).sum()}/{len(pos)}")
        print(f"    altro documento  mediana {np.median(neg):.4f}   "
              f"sopra 0.5: {(neg >= .5).sum()}/{len(neg)}")
        print(f"    AUC {auc:.4f}   IC95 [{auc - 1.96 * se:.3f}, {auc + 1.96 * se:.3f}]")

    # Paired: the same cases, so per-case verdicts compare directly and the
    # difference cannot come from one model having drawn an easier sample.
    a, b = res["mDeBERTa-512"], res["bge-m3-8192"]
    a_ok = (a[0] >= 0.5) & (a[1] < 0.5)
    b_ok = (b[0] >= 0.5) & (b[1] < 0.5)
    only_b, only_a = int((~a_ok & b_ok).sum()), int((a_ok & ~b_ok).sum())
    print("\n  appaiato (coppia risolta = claim vero sopra 0.5 E estraneo sotto)")
    print(f"    risolte da entrambi      {int((a_ok & b_ok).sum())}/{len(cases)}")
    print(f"    solo da bge-m3           {only_b}")
    print(f"    solo da mDeBERTa         {only_a}")
    print(f"    McNemar esatto  p = {_mcnemar(only_b, only_a):.4f}")


PROBES = {"backend": probe_backend, "length": probe_length,
          "separation": probe_separation, "compare": probe_compare}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in PROBES:
        raise SystemExit(f"uso: probe_entailment.py {{{'|'.join(PROBES)}}} [dataset] [n]")
    args = [a if not a.isdigit() else int(a) for a in sys.argv[2:]]
    PROBES[sys.argv[1]](*args)
