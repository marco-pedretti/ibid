"""Tests for dashboard/retrieval_probe.py — single-query interactive retrieval.

All Qdrant and embedding calls are mocked: these assert the probe's *ordering
semantics* match the eval harness, not that the models work.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import src.config as cfg
from dashboard.retrieval_probe import (
    RETRIEVAL_MODES,
    ProbeConfig,
    ProbeHit,
    compare_hits,
    dataset_of_collection,
    fetch_chunks_by_id,
    list_collections,
    probe,
)

KNOWN = ("open_ragbench", "ledger")


def _point(chunk_id: str, score: float = 0.9, **payload) -> MagicMock:
    p = MagicMock()
    p.payload = {"chunk_id": chunk_id, "text": "t", "doc_id": chunk_id.split(":")[1],
                 **payload}
    p.score = score
    return p


def _hit(chunk_id: str, rank: int = 1, score: float = 0.9) -> ProbeHit:
    return ProbeHit(rank=rank, chunk_id=chunk_id, score=score,
                    payload={"chunk_id": chunk_id})


# ---------------------------------------------------------------------------
# list_collections — the fix for hardcoded dataset names
# ---------------------------------------------------------------------------

class TestListCollections:
    def _client(self, names):
        client = MagicMock()
        client.get_collections.return_value.collections = [
            MagicMock(name=n) for n in names
        ]
        # MagicMock(name=...) sets the mock's repr, not .name — set explicitly.
        for m, n in zip(client.get_collections.return_value.collections, names):
            m.name = n
        return client

    def test_returns_sorted_names(self):
        client = self._client(["open_ragbench", "ledger"])
        assert list_collections(client) == ["ledger", "open_ragbench"]

    def test_includes_routed_collections(self):
        """The whole point: *_routed must be reachable from the dashboard."""
        client = self._client(["ledger", "ledger_routed"])
        assert "ledger_routed" in list_collections(client)

    def test_empty_server(self):
        assert list_collections(self._client([])) == []


class TestDatasetOfCollection:
    def test_exact_match(self):
        assert dataset_of_collection("ledger", KNOWN) == "ledger"

    def test_suffixed_collection(self):
        assert dataset_of_collection("ledger_routed", KNOWN) == "ledger"

    def test_open_ragbench_routed(self):
        assert dataset_of_collection("open_ragbench_routed", KNOWN) == "open_ragbench"

    def test_unknown_returns_itself(self):
        assert dataset_of_collection("mystery", KNOWN) == "mystery"

    def test_longest_match_wins(self):
        known = ("ledger", "ledger_v2")
        assert dataset_of_collection("ledger_v2_routed", known) == "ledger_v2"

    def test_prefix_without_underscore_not_matched(self):
        assert dataset_of_collection("ledgerbook", KNOWN) == "ledgerbook"


# ---------------------------------------------------------------------------
# ProbeConfig
# ---------------------------------------------------------------------------

class TestProbeConfig:
    def test_label_without_rerank(self):
        assert ProbeConfig("ledger", "dense").label() == "ledger · dense"

    def test_label_with_rerank(self):
        assert ProbeConfig("ledger", "hybrid", rerank=True).label() == \
            "ledger · hybrid · rerank"

    def test_all_modes_are_valid_choices(self):
        assert set(RETRIEVAL_MODES) == {"dense", "sparse", "hybrid"}

    def test_hashable(self):
        """frozen=True so it can key a Streamlit cache."""
        assert {ProbeConfig("a"), ProbeConfig("a")} == {ProbeConfig("a")}


# ---------------------------------------------------------------------------
# probe — routes to the right vector and respects top_k
# ---------------------------------------------------------------------------

class TestProbe:
    def _run(self, config, points=None, rerank_out=None):
        if points is None:  # [] is a meaningful input, not "unset"
            points = [_point(f"ds:doc1:{i}", 0.9 - i / 100) for i in range(10)]
        with patch("dashboard.retrieval_probe.encode", return_value=[[0.1] * 1024]), \
             patch("dashboard.retrieval_probe.encode_sparse", return_value=[MagicMock()]), \
             patch("dashboard.retrieval_probe.search", return_value=points) as mock_search, \
             patch("dashboard.retrieval_probe.cross_encode",
                   return_value=rerank_out if rerank_out is not None else []):
            hits = probe(MagicMock(), "q", config)
        return hits, mock_search

    def test_dense_uses_dense_vector(self):
        _, mock_search = self._run(ProbeConfig("ledger", "dense"))
        assert mock_search.call_args.kwargs["using"] == "dense"

    def test_sparse_uses_sparse_vector(self):
        _, mock_search = self._run(ProbeConfig("ledger", "sparse"))
        assert mock_search.call_args.kwargs["using"] == "sparse"

    def test_queries_the_named_collection(self):
        _, mock_search = self._run(ProbeConfig("ledger_routed", "dense"))
        assert mock_search.call_args[0][1] == "ledger_routed"

    def test_truncates_to_top_k(self):
        hits, _ = self._run(ProbeConfig("ledger", "dense", top_k=3))
        assert len(hits) == 3

    def test_ranks_are_one_based_and_contiguous(self):
        hits, _ = self._run(ProbeConfig("ledger", "dense", top_k=4))
        assert [h.rank for h in hits] == [1, 2, 3, 4]

    def test_hybrid_queries_both_vectors(self):
        _, mock_search = self._run(ProbeConfig("ledger", "hybrid"))
        usings = [c.kwargs["using"] for c in mock_search.call_args_list]
        assert set(usings) == {"dense", "sparse"}

    def test_rerank_fetches_deeper_pool(self):
        """A cross-encoder with only top_k candidates has nothing to rerank."""
        _, mock_search = self._run(ProbeConfig("ledger", "dense", rerank=True, top_k=5))
        assert mock_search.call_args.kwargs["top_k"] == max(cfg.RERANK_FETCH_K, 5)

    def test_no_rerank_fetches_exactly_top_k(self):
        _, mock_search = self._run(ProbeConfig("ledger", "dense", top_k=5))
        assert mock_search.call_args.kwargs["top_k"] == 5

    def test_rerank_output_replaces_ranking(self):
        reranked = [_point("ds:doc9:0", 5.0), _point("ds:doc8:0", 4.0)]
        hits, _ = self._run(
            ProbeConfig("ledger", "dense", rerank=True, top_k=2), rerank_out=reranked
        )
        assert [h.chunk_id for h in hits] == ["ds:doc9:0", "ds:doc8:0"]

    def test_payload_carried_through(self):
        pts = [_point("ds:doc1:0", 0.9, section_path="Methods")]
        hits, _ = self._run(ProbeConfig("ledger", "dense", top_k=1), points=pts)
        assert hits[0].payload["section_path"] == "Methods"

    def test_empty_result(self):
        hits, _ = self._run(ProbeConfig("ledger", "dense"), points=[])
        assert hits == []


# ---------------------------------------------------------------------------
# compare_hits — the A/B question
# ---------------------------------------------------------------------------

class TestCompareHits:
    def test_identical_lists_are_fully_shared(self):
        a = [_hit("ds:d1:0", 1), _hit("ds:d2:0", 2)]
        cmp = compare_hits(a, list(a))
        assert cmp.jaccard == 1.0
        assert cmp.only_a == [] and cmp.only_b == []

    def test_disjoint_lists(self):
        cmp = compare_hits([_hit("ds:d1:0")], [_hit("ds:d2:0")])
        assert cmp.jaccard == 0.0
        assert cmp.only_a == ["ds:d1:0"] and cmp.only_b == ["ds:d2:0"]

    def test_partial_overlap(self):
        a = [_hit("ds:d1:0"), _hit("ds:d2:0")]
        b = [_hit("ds:d2:0"), _hit("ds:d3:0")]
        cmp = compare_hits(a, b)
        assert cmp.shared == ["ds:d2:0"]
        assert cmp.jaccard == pytest.approx(1 / 3)

    def test_routed_case_zero_chunk_overlap_but_shared_docs(self):
        """The R-07 shape: same document, incompatible chunk ids."""
        a = [_hit("ledger:doc7:3")]
        b = [_hit("ledger:doc7:0042")]
        cmp = compare_hits(a, b)
        assert cmp.jaccard == 0.0
        assert cmp.doc_jaccard == 1.0
        assert cmp.shared_docs == ["doc7"]

    def test_doc_jaccard_partial(self):
        a = [_hit("ds:d1:0"), _hit("ds:d2:0")]
        b = [_hit("ds:d2:9"), _hit("ds:d3:0")]
        assert compare_hits(a, b).doc_jaccard == pytest.approx(1 / 3)

    def test_both_empty(self):
        cmp = compare_hits([], [])
        assert cmp.jaccard == 0.0 and cmp.doc_jaccard == 0.0

    def test_one_empty(self):
        cmp = compare_hits([_hit("ds:d1:0")], [])
        assert cmp.only_a == ["ds:d1:0"] and cmp.jaccard == 0.0

    def test_shared_preserves_a_order(self):
        a = [_hit("ds:d3:0"), _hit("ds:d1:0")]
        b = [_hit("ds:d1:0"), _hit("ds:d3:0")]
        assert compare_hits(a, b).shared == ["ds:d3:0", "ds:d1:0"]


# ---------------------------------------------------------------------------
# fetch_chunks_by_id — tells "bad retrieval" from "bad label"
# ---------------------------------------------------------------------------

class TestFetchChunksById:
    def test_empty_input_skips_the_call(self):
        client = MagicMock()
        assert fetch_chunks_by_id(client, "ledger", []) == {}
        client.scroll.assert_not_called()

    def test_maps_id_to_payload(self):
        client = MagicMock()
        client.scroll.return_value = ([_point("ds:d1:0")], None)
        out = fetch_chunks_by_id(client, "ledger", ["ds:d1:0"])
        assert out["ds:d1:0"]["chunk_id"] == "ds:d1:0"

    def test_missing_id_simply_absent(self):
        """An id the collection does not contain is the answer, not an error."""
        client = MagicMock()
        client.scroll.return_value = ([_point("ds:d1:0")], None)
        out = fetch_chunks_by_id(client, "ledger", ["ds:d1:0", "ds:d9:0"])
        assert "ds:d9:0" not in out

    def test_queries_the_named_collection(self):
        client = MagicMock()
        client.scroll.return_value = ([], None)
        fetch_chunks_by_id(client, "ledger_routed", ["x"])
        assert client.scroll.call_args.kwargs["collection_name"] == "ledger_routed"
