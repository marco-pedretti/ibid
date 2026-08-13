"""Does a cited chunk support a claim?  (C-03)

The verifier behind `citation_precision`.  STACK.md picks an NLI model over an
LLM judge deliberately: it is deterministic, and the metric must not depend on
the model being evaluated.

**Why this model.**  The original choice, mDeBERTa-v3 NLI, was measured before
anything was built on it and replaced — see STACK.md and `docs/progress.md` §C-03.
The deciding property is not accuracy in the abstract, it is the **window**:
mDeBERTa reads 512 tokens against chunks whose p90 is ~2900, so the premise had
to be split and the score taken as a max over N windows.  A max over N is a
multiple-comparison problem — every extra window is another chance at a false
positive — and it was measured: correlation 0.46-0.54 between window count and
peak P(entailment) on claims that *no* sampled chunk supports.  `citation_precision`
would have partly measured the length of the cited chunk.

`bge-m3-zeroshot-v2.0` reads 8194 tokens, so 99% of our chunks arrive whole and
N is 1.  The artefact does not get calibrated away; it does not arise.  Paired
floor test, same cases for both models: AUC 0.661 -> 0.939 on open_ragbench and
0.742 -> 0.910 on ledger, with unrelated chunks passing threshold falling from
23/60 to 2/60 and from 13/60 to 0/60.  That second number is the one that
matters — a verifier which *approves* wrong citations inflates the metric, which
is far worse than one that is pessimistic.

Reproduce with `python scripts/probe_entailment.py compare {dataset}`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import onnxruntime
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

import src.config as cfg
from src.ingestion.ocr_tables import parse_html_table
from src.ingestion.pipeline_table_heavy import _split_segments

from src.providers import onnx_providers

#: Index of the entailment logit.  The head is binary — entailment /
#: not_entailment — which is the distinction the metric needs; a three-way NLI
#: head would spend capacity separating neutral from contradiction, and nothing
#: here reads that difference.
_ENTAILMENT = 0


@dataclass(frozen=True)
class Verdict:
    """One (chunk, claim) judgement, with the evidence behind it.

    `n_premises` is carried because it is the artefact the model choice exists
    to avoid: any run where it is routinely above 1 is a run whose scores are
    inflated by chunk length, and that has to be visible rather than inferred.
    """

    supported: bool
    score: float
    n_premises: int

    @property
    def windowed(self) -> bool:
        return self.n_premises > 1


@lru_cache(maxsize=4)
def _load(model_name: str) -> tuple[Tokenizer, onnxruntime.InferenceSession]:
    """Tokenizer and ONNX session, loaded once per process.

    The ONNX export is shipped by the model repository itself, so no third-party
    conversion enters the trust path and no dependency is added — `onnxruntime`
    and `tokenizers` are already in the tree via fastembed.
    """
    path = hf_hub_download(model_name, "onnx/model.onnx")
    try:
        # Exports above 2 GB keep their weights beside the graph; onnxruntime
        # resolves the sibling by name when the session is created.
        hf_hub_download(model_name, "onnx/model.onnx_data")
    except Exception:
        pass
    tok = Tokenizer.from_file(hf_hub_download(model_name, "tokenizer.json"))
    sess = onnxruntime.InferenceSession(path, providers=onnx_providers())
    return tok, sess


def build_premises(
    text: str,
    model_name: str | None = None,
    cap: int | None = None,
) -> list[str]:
    """The chunk as one premise when it fits, overlapping windows when it does not.

    The cap is a cost boundary, not a capability one: the model reads 8194 tokens,
    but attention is quadratic and measured cost runs 123 ms at 758 tokens, 762 ms
    at 2951 and **19.7 s at 7693**.  Above the cap, windowing is cheaper than one
    long pass — and it reintroduces the multiple-comparison artefact, which is why
    the cap is set where it leaves 96% of chunks in a single window.
    """
    model_name = model_name or cfg.ENTAILMENT_MODEL
    cap = cap or cfg.ENTAILMENT_PREMISE_CAP
    tok, _ = _load(model_name)
    tok.no_truncation()
    ids = tok.encode(text).ids
    if len(ids) <= cap:
        return [text]
    stride = max(1, cap // 2)
    return [tok.decode(ids[i:i + cap]) for i in range(0, len(ids), stride)]


def p_entailment(
    pairs: list[tuple[str, str]],
    model_name: str | None = None,
) -> list[float]:
    """P(entailment) for each (premise, hypothesis) pair.

    One pair per forward pass.  Batching would pad every sequence up to the
    longest in the batch and attention is quadratic in that length, so a batch of
    8 at the premise cap asks for roughly 8 GB of attention matrices and the
    DirectML allocator refuses outright — measured, not feared.  At batch 1 there
    is also no padding to pay for, and the whole comparison run on ledger came in
    *faster* than the 512-token model it replaced.
    """
    model_name = model_name or cfg.ENTAILMENT_MODEL
    tok, sess = _load(model_name)
    tok.enable_truncation(cfg.ENTAILMENT_MAX_LEN)
    tok.no_padding()
    out: list[float] = []
    for premise, hypothesis in pairs:
        enc = tok.encode(premise, hypothesis)
        logits = sess.run(None, {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        })[0][0]
        e = np.exp(logits - logits.max())
        out.append(float((e / e.sum())[_ENTAILMENT]))
    return out


def verify(
    chunk_text: str,
    claim: str,
    model_name: str | None = None,
    threshold: float | None = None,
) -> Verdict:
    """Does `chunk_text` support `claim`?

    The score is the maximum over premises: if any part of the chunk entails the
    claim, the chunk does.  For 96% of chunks there is exactly one premise and
    the max is not a max at all.
    """
    threshold = cfg.ENTAILMENT_THRESHOLD if threshold is None else threshold
    premises = build_premises(chunk_text, model_name)
    scores = p_entailment([(p, claim) for p in premises], model_name)
    best = max(scores) if scores else 0.0
    return Verdict(supported=best >= threshold, score=best, n_premises=len(premises))


_WHITESPACE = re.compile(r"\s+")


def render_tables(text: str) -> str:
    """Table markup -> readable rows, prose left alone.

    A LEDGER premise is Mathpix OCR: prose with `<table>` blocks inline.  The
    markup was going to the verifier as-is, and it is not a small share —
    measured over the 117 chunks cited in the C-03 ledger run, the median premise
    is **26.5% markup tokens**, the third quartile 62.5%, the worst 77.2%.

    Two costs, and the second is the one that matters.  The tokens count against
    `ENTAILMENT_PREMISE_CAP` while carrying nothing a claim could be entailed by
    — that is only budget.  The real problem is that an NLI model trained on
    prose is out of distribution on `<td rowspan="2">`, while **96.7% of the
    ledger claims are numeric** (three digits or more): both sides of the pair
    are unlike anything the model was trained on.  It is why `citation_precision`
    on ledger is recorded as not interpretable — see `docs/progress.md`, C-03.

    Rendering rows as `cell | cell | cell` is the smallest change that removes
    the markup without removing the table: the numbers a claim asserts stay, and
    so does which row and column they sat in.

    **Misurato il 2026-08-12, e l'ipotesi era sbagliata.** Sulle stesse 331
    coppie della run C-03, rendere le tabelle porta `citation_precision` da
    0,3656 a 0,3263: 35 citazioni perse contro 22 guadagnate, McNemar esatto
    **p = 0,1112**, cioe' indistinguibile dal caso. La variazione di
    P(entailment) e' simmetrica — mediana +0,0000, 132 punteggi scesi e 125
    saliti — quindi il verificatore e' sostanzialmente **indifferente** alla
    forma superficiale della tabella.

    Ne segue che il markup non e' la causa dell'inutilizzabilita' di
    `citation_precision` su LEDGER. Resta l'altra meta' della diagnosi, che
    questa misura non tocca: il 96,7% dei claim e' numerico, e un modello NLI
    addestrato su prosa non verifica un'asserzione numerica contro una tabella
    a prescindere da come la tabella e' scritta. E' una limitazione del modello,
    non della sua formattazione — vedi `docs/open-questions.md`, OQ-05.

    Il flag resta spento di default: il punto stimato peggiora, anche se non in
    modo significativo, e non si accende un interruttore per un guadagno che non
    c'e'. Resta acceso solo il fatto che la verifica costa il 40% in meno (78 s
    contro 129), che non e' una ragione sufficiente.
    """
    out: list[str] = []
    for kind, segment in _split_segments(text):
        if kind != "table":
            out.append(segment)
            continue
        rows = parse_html_table(segment)
        # Never silently drop content: an unparseable table goes through whole,
        # markup and all, exactly as before. A verifier that judges a claim
        # against a premise that quietly lost its table is worse than one reading
        # tags.
        out.append(_row_join(rows) if rows else segment)
    return "\n\n".join(out)


def _row_join(rows: list[list[str]]) -> str:
    """Rows as `cell | cell`, one per line."""
    return "\n".join(" | ".join(row) for row in rows)


def normalize_premise(text: str, render: bool | None = None) -> str:
    """Prepare a chunk to be read as a premise.

    Collapses whitespace so a chunk's formatting does not eat its token budget,
    and — when `cfg.ENTAILMENT_RENDER_TABLES` is on — turns table markup into
    rows first.

    `render` is a parameter rather than a constant so the two variants can be
    scored on the *same* stored generations: ROADMAP §3.4 wants an ablation to be
    a loop over config, and comparing two verifiers by checking out two commits
    is not that.
    """
    if render is None:
        render = cfg.ENTAILMENT_RENDER_TABLES
    if render:
        text = render_tables(text)
    return _WHITESPACE.sub(" ", text).strip()
