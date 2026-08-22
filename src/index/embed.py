"""Dense and sparse embedding via fastembed + ONNX Runtime.

Dense model: intfloat/multilingual-e5-large (1024-dim, multilingual, Apache 2.0)
  - which accelerator runs the ONNX graph is decided by `src/providers.py`, not
    here: it was the same three lines copied in three modules (Q-05)
  - Target: BAAI/bge-m3 when fastembed PR #602 merges

Sparse model: Qdrant/bm25 (statistical, multilingual, Apache 2.0, ~1 MB)
  - CPU-only — no GPU needed for statistical BM25
  - Used in R-01 hybrid RRF alongside dense vectors
"""

from __future__ import annotations

import gc

import src.config as cfg
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client.models import SparseVector
from src.providers import onnx_providers

_dense_cache: dict[str, TextEmbedding] = {}
_sparse_cache: dict[str, SparseTextEmbedding] = {}


def _dense_model(name: str) -> TextEmbedding:
    if name not in _dense_cache:
        _dense_cache[name] = TextEmbedding(
            model_name=name, providers=onnx_providers(), cache_dir=cfg.FASTEMBED_CACHE
        )
    return _dense_cache[name]


def _sparse_model(name: str) -> SparseTextEmbedding:
    if name not in _sparse_cache:
        _sparse_cache[name] = SparseTextEmbedding(model_name=name, cache_dir=cfg.FASTEMBED_CACHE)
    return _sparse_cache[name]


def unload() -> None:
    """Drop the cached ONNX sessions, releasing whatever device memory they hold.

    **This exists because of an accelerator, not because of memory hygiene.**
    The eval harnesses embed every query up front and then spend the rest of the
    run talking to the LLM over HTTP: on a 12 GB card the dense session keeps
    ~2.3 GB that nothing will read again, and that is the difference between the
    12B fitting in dedicated memory and the driver spilling ~4 GB into shared
    (system) memory.  When that happens the copy engine saturates, the compute
    engines idle, and decode drops from 33 tok/s to 4.7 -- a seven-fold cost
    paid to hold a session that has already done its job.

    **Safe by construction, because the caches are lazy.**  Anything that asks
    for a model after this simply builds it again; the worst case is paying the
    load twice, never a wrong answer.  That is why this is a plain function and
    not a context manager: the callers are linear (embed everything, then
    generate), and a `with` block around half a harness would suggest a
    lifetime that the code does not actually have.

    Not called from `encode()` itself: ingestion embeds in batches for tens of
    minutes, and dropping the session between them would reload it every time.
    Who is finished is the caller's knowledge, not this module's.
    """
    _dense_cache.clear()
    _sparse_cache.clear()
    # Le sessioni ONNX liberano la memoria del dispositivo quando l'oggetto
    # viene distrutto, non quando perde l'ultimo riferimento: senza questa
    # riga il rilascio arriva a discrezione del GC, cioe' magari dopo che il
    # modello grande ha gia' provato a entrare.
    gc.collect()


def encode(texts: list[str], model_name: str, batch_size: int = 32) -> list[list[float]]:
    """Return dense vectors for each text.

    **Not L2-normalized**, which this docstring used to claim: `PooledEmbedding`
    (the fastembed class serving multilingual-e5-large) does not normalize, and
    the vectors come back with a norm around 27.  Nothing is broken by that today
    — Qdrant normalizes on upsert for a cosine collection, and the stored vectors
    do have norm 1.0 — but anything computing a similarity on this output
    directly would have believed the docstring and been wrong.

    **The E5 prefixes are not applied here.**  The model card requires `query: `
    and `passage: `, fastembed leaves them to the caller, and this function never
    adds them.  See `docs/open-questions.md` OQ-02: it is a documented deviation
    with an unmeasured cost, and correcting it means re-ingesting.
    """
    vecs = list(_dense_model(model_name).embed(texts, batch_size=batch_size))
    return [v.tolist() for v in vecs]


def encode_sparse(texts: list[str], model_name: str) -> list[SparseVector]:
    """Return BM25 sparse vectors for each text, as *documents*.

    **For the corpus only.** Queries go through `encode_sparse_query` (R-09):
    this path applies the BM25 document weighting, including the length
    normalization `b · doc_len / avg_len`, which is meaningless for a question.
    """
    results = list(_sparse_model(model_name).embed(texts))
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in results
    ]


def encode_sparse_query(texts: list[str], model_name: str) -> list[SparseVector]:
    """Return BM25 sparse vectors for each text, as *queries* (R-09).

    In BM25 the query and the document are not symmetric, and fastembed says so
    in `Bm25.query_embed`:

        "To emulate BM25 behaviour, we don't need to use weights in the query,
        and it's enough to just hash the tokens and assign a weight of 1.0."

    The query selects *which* terms are scored; the document decides *how much*
    each one is worth.  Sending a question through `embed()` gives it document
    weights it has no business having — a term repeated twice in the question
    counts double, and the whole vector gets scaled by how long the question is
    relative to the average *chunk*, which is a ratio between two unrelated
    things.

    This is the second half of OQ-03.  The first half was R-08 (`modifier=IDF`
    on the index), deliberately corrected and measured before this one: the IDF
    lives in the index and this lives in the client, and fixing both before
    measuring would have made the delta unattributable (§15).

    Note the third difference, which the docstring above does not mention:
    `query_embed` de-duplicates tokens through a `set`, so a word repeated in
    the question is counted once.  `embed` does not.
    """
    results = list(_sparse_model(model_name).query_embed(texts))
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in results
    ]


def vector_size(model_name: str) -> int:
    dummy = list(_dense_model(model_name).embed(["x"]))
    return len(dummy[0])
