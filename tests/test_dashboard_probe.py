"""Tests for dashboard/retrieval_probe.py — single-query interactive retrieval.

**Questi test si sono accorciati con A-06, ed e' la cosa giusta da notare.**
Prima verificavano che il probe usasse il vettore denso per `dense`, pescasse
piu' a fondo col reranker, fondesse con RRF in `hybrid`: cioe' verificavano una
**copia** della pipeline contro se stessa. Quella copia non c'e' piu', e con
lei quei test -- il comportamento vive ora in `test_service_answer.py` e
`test_index_search_params.py`, dove c'e' una implementazione sola da
verificare.

Quel che resta e' cio' che la dashboard fa davvero: chiedere la cosa giusta al
backend, e trasformare la risposta nella forma che le viste disegnano.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dashboard.retrieval_probe import (
    RETRIEVAL_MODES,
    ProbeConfig,
    ProbeHit,
    compare_hits,
    dataset_of_collection,
    doc_of,
    fetch_chunks_by_id,
    list_collections,
    probe,
)

KNOWN = ("open_ragbench", "ledger")


def _chunk(chunk_id: str, score: float = 0.9, **extra) -> dict:
    """Un chunk come l'API lo consegna: un dizionario, non un punto di Qdrant."""
    return {"chunk_id": chunk_id, "score": score, "text": "t",
            "doc_id": chunk_id.split(":")[1], **extra}


def _hit(chunk_id: str, rank: int = 1, score: float = 0.9) -> ProbeHit:
    return ProbeHit(rank=rank, chunk_id=chunk_id, score=score,
                    payload={"chunk_id": chunk_id})


# ---------------------------------------------------------------------------
# list_collections — the fix for hardcoded dataset names
# ---------------------------------------------------------------------------

class TestListCollections:
    """Le collection arrivano dal backend, non da un elenco scritto a mano.

    La dashboard aveva `["open_ragbench", "ledger"]` cablato, il che rendeva le
    collection `*_routed` di R-07 irraggiungibili dall'unico strumento
    costruito per ispezionarle.
    """

    def _caps(self, nomi):
        from dashboard.api_client import Capabilities
        return Capabilities(
            datasets=[], collections=[{"name": n} for n in nomi],
            retrieval_modes=[], baseline_prompts=[],
        )

    def test_restituisce_quelle_del_backend(self):
        with patch("dashboard.api_client.capabilities",
                   return_value=self._caps(["ledger", "open_ragbench"])):
            assert list_collections() == [{"name": "ledger"}, {"name": "open_ragbench"}]

    def test_comprende_le_routed(self):
        """Sono lo stesso dataset indicizzato da un'altra pipeline: senza, R-07
        non e' ispezionabile."""
        with patch("dashboard.api_client.capabilities",
                   return_value=self._caps(["ledger", "ledger_routed"])):
            nomi = [c["name"] for c in list_collections()]
        assert "ledger_routed" in nomi

    def test_server_vuoto(self):
        with patch("dashboard.api_client.capabilities", return_value=self._caps([])):
            assert list_collections() == []


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
    """Cosa la dashboard chiede, e cosa fa della risposta.

    Non c'e' piu' un `client` fra i parametri: chi interroga Qdrant e' il
    servizio. E' la differenza fra uno strumento che *usa* il sistema e uno che
    lo **reimplementa** — ed e' il criterio di A-06 in una firma.
    """

    def _run(self, config, chunks=None):
        if chunks is None:  # [] e' un input che significa qualcosa
            chunks = [_chunk(f"ds:doc1:{i}", 0.9 - i / 100) for i in range(config.top_k)]
        with patch("dashboard.api_client.retrieve", return_value=[chunks]) as chiamata:
            hits = probe("q", config)
        return hits, chiamata

    def test_la_modalita_arriva_al_backend(self):
        _, chiamata = self._run(ProbeConfig("ledger", "sparse"))
        assert chiamata.call_args.kwargs["retrieval_mode"] == "sparse"

    def test_la_collection_arriva_al_backend(self):
        _, chiamata = self._run(ProbeConfig("ledger_routed", "dense"))
        assert chiamata.call_args.kwargs["collection"] == "ledger_routed"

    def test_il_rerank_arriva_al_backend(self):
        _, chiamata = self._run(ProbeConfig("ledger", "dense", rerank=True))
        assert chiamata.call_args.kwargs["rerank"] is True

    def test_una_query_sola_ma_l_interfaccia_e_a_lista(self):
        """`/retrieve` accetta molte query. Chiamarlo con una non e' un caso
        speciale: e' una lista di uno, e la risposta e' una lista di uno."""
        _, chiamata = self._run(ProbeConfig("ledger", "dense"))
        assert chiamata.call_args[0][0] == ["q"]

    def test_i_ranghi_sono_1_based_e_contigui(self):
        """Il rango non arriva dal filo: e' la posizione nella lista. L'API
        restituisce i chunk in ordine, e numerarli qui evita di dover credere a
        un campo che potrebbe contraddire quell'ordine."""
        hits, _ = self._run(ProbeConfig("ledger", "dense", top_k=4))
        assert [h.rank for h in hits] == [1, 2, 3, 4]

    def test_il_payload_arriva_intero(self):
        chunks = [_chunk("ds:doc1:0", 0.9, section_path="Methods")]
        hits, _ = self._run(ProbeConfig("ledger", "dense", top_k=1), chunks=chunks)
        assert hits[0].payload["section_path"] == "Methods"

    def test_risultato_vuoto(self):
        hits, _ = self._run(ProbeConfig("ledger", "dense"), chunks=[])
        assert hits == []

    def test_la_profondita_la_decide_il_backend(self):
        """`top_k` viaggia nella richiesta e non viene ri-tagliato qui: due
        troncamenti sono due posti in cui sbagliare, e il secondo nasconde il
        primo."""
        chunks = [_chunk(f"ds:doc1:{i}") for i in range(3)]
        hits, chiamata = self._run(ProbeConfig("ledger", "dense", top_k=3), chunks=chunks)
        assert chiamata.call_args.kwargs["top_k"] == 3
        assert len(hits) == 3


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
    def test_input_vuoto_non_chiama_niente(self):
        with patch("dashboard.api_client.chunk") as chiamata:
            assert fetch_chunks_by_id("ledger", []) == {}
        chiamata.assert_not_called()

    def test_mappa_id_a_payload(self):
        with patch("dashboard.api_client.chunk", return_value=_chunk("ds:d1:0")):
            out = fetch_chunks_by_id("ledger", ["ds:d1:0"])
        assert out["ds:d1:0"]["chunk_id"] == "ds:d1:0"

    def test_un_id_assente_semplicemente_non_c_e(self):
        """Un `chunk_id` d'oro che la collection non contiene **e' il dato**: e'
        la differenza fra un retrieval sbagliato e un'etichetta sbagliata, e le
        due chiedono correzioni opposte."""
        def _chunk_o_niente(cid, collection=None):
            return _chunk(cid) if cid == "ds:d1:0" else None

        with patch("dashboard.api_client.chunk", side_effect=_chunk_o_niente):
            out = fetch_chunks_by_id("ledger", ["ds:d1:0", "ds:d9:0"])
        assert "ds:d9:0" not in out and "ds:d1:0" in out

    def test_la_collection_arriva_al_backend(self):
        with patch("dashboard.api_client.chunk", return_value=None) as chiamata:
            fetch_chunks_by_id("ledger_routed", ["x"])
        assert chiamata.call_args[0][1] == "ledger_routed"


class TestDocOf:
    """Il documento si legge dall'id, che e' il contratto del §3."""

    def test_estrae_il_documento(self):
        assert doc_of("ledger:NASDAQ_AAPL_2022:0031") == "NASDAQ_AAPL_2022"

    def test_un_doc_id_con_i_due_punti_sopravvive(self):
        assert doc_of("ds:doc:con:due:punti") == "doc"

    def test_resta_d_accordo_con_l_implementazione_del_servizio(self):
        """Due implementazioni della stessa regola devono dire la stessa cosa.

        La dashboard non importa quella di `src.retrieval` — sarebbe l'unica
        riga di pipeline rimasta — ma un test le lega, cosi' che se una cambia
        l'altra non resti indietro in silenzio.
        """
        from src.retrieval.doc_aggregation import doc_id_from_chunk_id

        for cid in ("ledger:NASDAQ_AAPL_2022:0031", "ds:doc:con:due:punti",
                    "senza_due_punti", "a:b"):
            assert doc_of(cid) == doc_id_from_chunk_id(cid), cid
