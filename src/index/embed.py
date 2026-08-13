"""Dense and sparse embedding via fastembed + ONNX Runtime DirectML (AMD GPU on Windows).

Dense model: intfloat/multilingual-e5-large (1024-dim, multilingual, Apache 2.0)
  - fastembed routes ONNX inference to AMD RX 6750 XT via DmlExecutionProvider (DirectX 12)
  - Falls back to CPU if DirectML is not available
  - Target: BAAI/bge-m3 when fastembed PR #602 merges

Sparse model: Qdrant/bm25 (statistical, multilingual, Apache 2.0, ~1 MB)
  - CPU-only — no GPU needed for statistical BM25
  - Used in R-01 hybrid RRF alongside dense vectors
"""

from __future__ import annotations

import onnxruntime
import src.config as cfg
from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client.models import SparseVector

_PROVIDERS = (
    ["DmlExecutionProvider", "CPUExecutionProvider"]
    if "DmlExecutionProvider" in onnxruntime.get_available_providers()
    else ["CPUExecutionProvider"]
)

_dense_cache: dict[str, TextEmbedding] = {}
_sparse_cache: dict[str, SparseTextEmbedding] = {}


def _dense_model(name: str) -> TextEmbedding:
    if name not in _dense_cache:
        _dense_cache[name] = TextEmbedding(
            model_name=name, providers=_PROVIDERS, cache_dir=cfg.FASTEMBED_CACHE
        )
    return _dense_cache[name]


def _sparse_model(name: str) -> SparseTextEmbedding:
    if name not in _sparse_cache:
        _sparse_cache[name] = SparseTextEmbedding(model_name=name, cache_dir=cfg.FASTEMBED_CACHE)
    return _sparse_cache[name]


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

    Queries go through here too, and should not: fastembed's `Bm25.query_embed`
    exists because a query must be hashed to weight 1.0 per token, while this
    path applies the document-length normalization `b · doc_len / avg_len` and so
    scores the question as if it were a passage of the corpus.

    This is the half of OQ-03 that is **still open** (R-09). The other half —
    the sparse index created without `modifier=IDF` — was fixed by R-08 in
    `store.ensure_collection`; the two were kept apart on purpose, because the
    IDF lives in the index and the query encoding in the client, and correcting
    both before measuring would have made the delta unattributable (§14).
    """
    results = list(_sparse_model(model_name).embed(texts))
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in results
    ]


def vector_size(model_name: str) -> int:
    dummy = list(_dense_model(model_name).embed(["x"]))
    return len(dummy[0])
