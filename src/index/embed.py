"""Dense embedding via fastembed + ONNX Runtime DirectML (AMD GPU on Windows).

fastembed uses ONNX Runtime under the hood. With onnxruntime-directml installed,
DmlExecutionProvider routes inference to the GPU via DirectX 12 — no ROCm needed.
Falls back to CPU if DirectML is not available.

Current model: intfloat/multilingual-e5-large (1024-dim, multilingual, Apache 2.0)
Target model: BAAI/bge-m3 — switch when fastembed adds it to its model catalogue.
"""

from __future__ import annotations

import onnxruntime
from fastembed import TextEmbedding

_PROVIDERS = (
    ["DmlExecutionProvider", "CPUExecutionProvider"]
    if "DmlExecutionProvider" in onnxruntime.get_available_providers()
    else ["CPUExecutionProvider"]
)

_cache: dict[str, TextEmbedding] = {}


def _model(name: str) -> TextEmbedding:
    if name not in _cache:
        _cache[name] = TextEmbedding(model_name=name, providers=_PROVIDERS)
    return _cache[name]


def encode(texts: list[str], model_name: str, batch_size: int = 32) -> list[list[float]]:
    """Return L2-normalized dense vectors for each text."""
    vecs = list(_model(model_name).embed(texts, batch_size=batch_size))
    return [v.tolist() for v in vecs]


def vector_size(model_name: str) -> int:
    dummy = list(_model(model_name).embed(["x"]))
    return len(dummy[0])
