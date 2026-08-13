"""Unit tests for src/index/embed.py — encode() and encode_sparse()."""

from __future__ import annotations

import pytest

from src.index.embed import encode, encode_sparse, encode_sparse_query

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


# ---------------------------------------------------------------------------
# Sparse, query side (R-09)
# ---------------------------------------------------------------------------

class TestEncodeSparseQuery:
    """In BM25 the query and the document are not symmetric.

    The query says *which* terms to score; the document says how much each one
    is worth.  These tests pin the asymmetry, because it is invisible at the
    call site — both functions take a list of strings and return SparseVectors,
    so passing a question to the wrong one produces no error at all.
    """

    def test_all_weights_are_one(self):
        """The whole point: no term weighting on the query side."""
        sv = encode_sparse_query([TEXTS[0]], SPARSE_MODEL)[0]
        assert all(v == pytest.approx(1.0) for v in sv.values)

    def test_document_path_weights_depend_on_length(self):
        """The defect R-09 removes, in one assertion.

        Send a question through the document path and its terms are scaled by
        `b · len / avg_len` — the ratio between the length of the *question* and
        the average length of a *chunk*, two quantities with nothing to do with
        each other.  So the identical word scores differently depending on how
        long the question around it happens to be.  On the query side it is 1.0
        either way.
        """
        short = encode_sparse(["margine"], SPARSE_MODEL)[0]
        long = encode_sparse(
            ["qual e' il margine operativo consolidato del gruppo nel 2023"], SPARSE_MODEL
        )[0]
        assert short.values[0] != pytest.approx(long.values[0])

        q_short = encode_sparse_query(["margine"], SPARSE_MODEL)[0]
        q_long = encode_sparse_query(
            ["qual e' il margine operativo consolidato del gruppo nel 2023"], SPARSE_MODEL
        )[0]
        assert q_short.values[0] == pytest.approx(q_long.values[0]) == 1.0

    def test_differs_from_the_document_encoding(self):
        q = encode_sparse_query([TEXTS[0]], SPARSE_MODEL)[0]
        d = encode_sparse([TEXTS[0]], SPARSE_MODEL)[0]
        assert set(q.indices) == set(d.indices)  # stessi token
        assert q.values != pytest.approx(d.values)  # pesi diversi

    def test_repeated_terms_counted_once(self):
        """`query_embed` de-duplicates through a set; `embed` does not.

        A user who types the same word twice is not asking for it twice as
        much.
        """
        once = encode_sparse_query(["margine"], SPARSE_MODEL)[0]
        thrice = encode_sparse_query(["margine margine margine"], SPARSE_MODEL)[0]
        assert set(once.indices) == set(thrice.indices)
        assert len(thrice.indices) == len(once.indices)

    def test_document_path_does_react_to_repetition(self):
        once = encode_sparse(["margine"], SPARSE_MODEL)[0]
        thrice = encode_sparse(["margine margine margine"], SPARSE_MODEL)[0]
        assert once.values != pytest.approx(thrice.values)

    def test_returns_one_vector_per_text(self):
        assert len(encode_sparse_query(TEXTS, SPARSE_MODEL)) == len(TEXTS)

    def test_indices_and_values_same_length(self):
        for sv in encode_sparse_query(TEXTS, SPARSE_MODEL):
            assert len(sv.indices) == len(sv.values)

    def test_indices_are_ints(self):
        sv = encode_sparse_query(TEXTS[:1], SPARSE_MODEL)[0]
        assert all(isinstance(i, int) for i in sv.indices)

    def test_empty_input_returns_empty_list(self):
        assert encode_sparse_query([], SPARSE_MODEL) == []

    def test_same_text_identical_output(self):
        a = encode_sparse_query([TEXTS[0]], SPARSE_MODEL)[0]
        b = encode_sparse_query([TEXTS[0]], SPARSE_MODEL)[0]
        assert set(a.indices) == set(b.indices)
