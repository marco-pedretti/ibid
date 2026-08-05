"""Unit tests for src/index/embed.py — encode() and encode_sparse()."""

from __future__ import annotations

import pytest

from src.index.embed import encode, encode_sparse

# These tests download ONNX models on first run (~500 MB for dense, ~1 MB for sparse).
# Subsequent runs use the fastembed cache under ~/.cache/fastembed.

DENSE_MODEL = "intfloat/multilingual-e5-large"
SPARSE_MODEL = "Qdrant/bm25"

TEXTS = [
    "The quick brown fox jumps over the lazy dog.",
    "Annual revenue increased by 12% year-over-year.",
    "Il modello ha ottenuto un punteggio F1 di 0.87.",
]


# ---------------------------------------------------------------------------
# Dense
# ---------------------------------------------------------------------------

class TestEncode:
    def test_returns_one_vector_per_text(self):
        vecs = encode(TEXTS, DENSE_MODEL)
        assert len(vecs) == len(TEXTS)

    def test_vector_is_1024_dim(self):
        vecs = encode(TEXTS[:1], DENSE_MODEL)
        assert len(vecs[0]) == 1024

    def test_vectors_are_float_lists(self):
        vecs = encode(TEXTS[:1], DENSE_MODEL)
        assert all(isinstance(v, float) for v in vecs[0])

    def test_different_texts_produce_different_vectors(self):
        vecs = encode(TEXTS, DENSE_MODEL)
        assert vecs[0] != vecs[1]

    def test_same_text_produces_identical_vectors(self):
        v1 = encode([TEXTS[0]], DENSE_MODEL)[0]
        v2 = encode([TEXTS[0]], DENSE_MODEL)[0]
        assert v1 == v2

    def test_batch_size_does_not_change_output(self):
        vecs_b1 = encode(TEXTS, DENSE_MODEL, batch_size=1)
        vecs_b3 = encode(TEXTS, DENSE_MODEL, batch_size=3)
        # Tolerating fp32 accumulation variance across different batch sizes (~3e-6 max on DirectML)
        for v1, v3 in zip(vecs_b1, vecs_b3):
            assert v1 == pytest.approx(v3, abs=1e-5)

    def test_empty_input_returns_empty_list(self):
        assert encode([], DENSE_MODEL) == []

    def test_multilingual_texts(self):
        multilingual = [
            "Ceci est un test en français.",
            "これは日本語のテストです。",
            "هذا اختبار باللغة العربية.",
        ]
        vecs = encode(multilingual, DENSE_MODEL)
        assert len(vecs) == 3
        assert all(len(v) == 1024 for v in vecs)


# ---------------------------------------------------------------------------
# Sparse
# ---------------------------------------------------------------------------

class TestEncodeSparse:
    def test_returns_one_vector_per_text(self):
        svecs = encode_sparse(TEXTS, SPARSE_MODEL)
        assert len(svecs) == len(TEXTS)

    def test_each_has_indices_and_values(self):
        svecs = encode_sparse(TEXTS[:1], SPARSE_MODEL)
        sv = svecs[0]
        assert hasattr(sv, "indices")
        assert hasattr(sv, "values")

    def test_indices_and_values_same_length(self):
        svecs = encode_sparse(TEXTS, SPARSE_MODEL)
        for sv in svecs:
            assert len(sv.indices) == len(sv.values)

    def test_indices_are_ints(self):
        svecs = encode_sparse(TEXTS[:1], SPARSE_MODEL)
        assert all(isinstance(i, int) for i in svecs[0].indices)

    def test_values_are_positive_floats(self):
        svecs = encode_sparse(TEXTS[:1], SPARSE_MODEL)
        assert all(isinstance(v, float) and v >= 0 for v in svecs[0].values)

    def test_non_empty_vectors(self):
        svecs = encode_sparse(TEXTS, SPARSE_MODEL)
        for sv in svecs:
            assert len(sv.indices) > 0

    def test_different_texts_different_index_sets(self):
        svecs = encode_sparse(TEXTS[:2], SPARSE_MODEL)
        # Two unrelated texts should not share the exact same index set
        assert set(svecs[0].indices) != set(svecs[1].indices)

    def test_same_text_identical_output(self):
        sv1 = encode_sparse([TEXTS[0]], SPARSE_MODEL)[0]
        sv2 = encode_sparse([TEXTS[0]], SPARSE_MODEL)[0]
        assert sv1.indices == sv2.indices
        assert sv1.values == pytest.approx(sv2.values)

    def test_empty_input_returns_empty_list(self):
        assert encode_sparse([], SPARSE_MODEL) == []

    def test_multilingual_texts(self):
        multilingual = [
            "Ceci est un test en français.",
            "Il fatturato annuale è aumentato del 12%.",
        ]
        svecs = encode_sparse(multilingual, SPARSE_MODEL)
        assert len(svecs) == 2
        assert all(len(sv.indices) > 0 for sv in svecs)
