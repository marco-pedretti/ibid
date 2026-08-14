"""Tests for dashboard/failure_store.py — batch retrieval ranked worst-first.

The behaviour that matters here is the chunk-vs-document distinction: a routed
collection produces chunk_ids the qrels never mention, so chunk recall is
structurally 0.  Reading that as "retrieval is broken" is exactly the mistake
this module exists to prevent.
"""

from __future__ import annotations

from unittest.mock import patch


from dashboard.failure_store import (
    QueryOutcome,
    chunk_id_mismatch,
    evaluate_queries,
    failure_summary,
    score_outcome,
    sort_by_failure,
)
from dashboard.retrieval_probe import ProbeConfig
from src.datasets.golden import GoldenQrel, GoldenQuery


def _query(qid: str = "q1", chunk_ids: tuple[str, ...] = ("ds:doc1:0",),
           dataset: str = "open_ragbench") -> GoldenQuery:
    return GoldenQuery(
        query_id=qid,
        dataset_id=dataset,
        query_text=f"question {qid}",
        qrels=[GoldenQrel(chunk_id=c, relevance=2) for c in chunk_ids],
    )


def _outcome(retrieved: list[str], golden: tuple[str, ...] = ("ds:doc1:0",),
             qid: str = "q1") -> QueryOutcome:
    return score_outcome(
        QueryOutcome(
            query=_query(qid, golden),
            retrieved_ids=retrieved,
            scores=[0.9] * len(retrieved),
            payloads=[{"chunk_id": c} for c in retrieved],
        )
    )


def _chunk(chunk_id: str, score: float = 0.9) -> dict:
    """Un chunk come l'API lo consegna: un dizionario, non un punto di Qdrant."""
    return {"chunk_id": chunk_id, "score": score, "text": "t"}


# ---------------------------------------------------------------------------
# score_outcome — two granularities that can disagree
# ---------------------------------------------------------------------------

class TestScoreOutcome:
    def test_exact_hit_is_full_recall(self):
        o = _outcome(["ds:doc1:0"])
        assert o.recall == 1.0 and o.doc_recall == 1.0

    def test_miss_is_zero(self):
        o = _outcome(["ds:doc9:0"])
        assert o.recall == 0.0 and o.doc_recall == 0.0

    def test_wrong_chunk_right_document(self):
        """Chunk recall 0, doc recall 1 — a file-list success, a context failure."""
        o = _outcome(["ds:doc1:7"])
        assert o.recall == 0.0
        assert o.doc_recall == 1.0

    def test_routed_id_scheme_still_matches_document(self):
        o = _outcome(["ds:doc1:0042"], golden=("ds:doc1:3",))
        assert o.recall == 0.0
        assert o.doc_recall == 1.0

    def test_partial_recall_with_multiple_qrels(self):
        o = _outcome(["ds:doc1:0"], golden=("ds:doc1:0", "ds:doc2:0"))
        assert o.recall == 0.5

    def test_no_qrels_is_zero_not_crash(self):
        o = score_outcome(QueryOutcome(query=_query(chunk_ids=()), retrieved_ids=["x"]))
        assert o.recall == 0.0

    def test_empty_retrieval(self):
        assert _outcome([]).recall == 0.0

    def test_is_failure_follows_doc_recall(self):
        assert _outcome(["ds:doc9:0"]).is_failure is True
        assert _outcome(["ds:doc1:7"]).is_failure is False

    def test_top_score_of_empty_is_zero(self):
        assert _outcome([]).top_score == 0.0

    def test_golden_docs_derived_from_chunk_ids(self):
        assert _outcome([], golden=("ds:doc1:0", "ds:doc2:5")).golden_docs == {"doc1", "doc2"}


# ---------------------------------------------------------------------------
# sort_by_failure
# ---------------------------------------------------------------------------

class TestSortByFailure:
    def test_worst_first(self):
        good = _outcome(["ds:doc1:0"], qid="good")
        bad = _outcome(["ds:doc9:0"], qid="bad")
        assert sort_by_failure([good, bad])[0].query.query_id == "bad"

    def test_doc_recall_dominates_chunk_recall(self):
        partial_doc = _outcome(["ds:doc1:7"], qid="doc_ok")     # doc 1.0, chunk 0.0
        total_miss = _outcome(["ds:doc9:0"], qid="miss")        # doc 0.0, chunk 0.0
        assert sort_by_failure([partial_doc, total_miss])[0].query.query_id == "miss"

    def test_chunk_recall_breaks_ties(self):
        a = _outcome(["ds:doc1:7"], qid="a")                     # doc 1, chunk 0
        b = _outcome(["ds:doc1:0"], qid="b")                     # doc 1, chunk 1
        assert sort_by_failure([a, b])[0].query.query_id == "a"

    def test_empty_list(self):
        assert sort_by_failure([]) == []

    def test_does_not_mutate_input(self):
        items = [_outcome(["ds:doc1:0"], qid="a"), _outcome(["ds:doc9:0"], qid="b")]
        sort_by_failure(items)
        assert [o.query.query_id for o in items] == ["a", "b"]


# ---------------------------------------------------------------------------
# failure_summary
# ---------------------------------------------------------------------------

class TestFailureSummary:
    def test_empty_is_all_zero(self):
        s = failure_summary([])
        assert s["n"] == 0 and s["failure_rate"] == 0.0

    def test_counts_failures(self):
        s = failure_summary([_outcome(["ds:doc1:0"]), _outcome(["ds:doc9:0"])])
        assert s["n"] == 2 and s["n_failures"] == 1
        assert s["failure_rate"] == 0.5

    def test_mean_recalls(self):
        s = failure_summary([_outcome(["ds:doc1:0"]), _outcome(["ds:doc9:0"])])
        assert s["mean_recall"] == 0.5
        assert s["mean_doc_recall"] == 0.5

    def test_all_success(self):
        s = failure_summary([_outcome(["ds:doc1:0"])])
        assert s["failure_rate"] == 0.0

    def test_all_failure(self):
        s = failure_summary([_outcome(["ds:doc9:0"])])
        assert s["failure_rate"] == 1.0


# ---------------------------------------------------------------------------
# chunk_id_mismatch — the R-07 diagnostic
# ---------------------------------------------------------------------------

class TestChunkIdMismatch:
    def test_detects_routed_collection(self):
        outcomes = [_outcome(["ds:doc1:0042"], golden=("ds:doc1:3",), qid=f"q{i}")
                    for i in range(3)]
        assert chunk_id_mismatch(outcomes) is True

    def test_normal_collection_is_not_flagged(self):
        outcomes = [_outcome(["ds:doc1:0"], qid=f"q{i}") for i in range(3)]
        assert chunk_id_mismatch(outcomes) is False

    def test_genuine_total_failure_is_not_flagged(self):
        """Everything wrong at both levels is a real failure, not an id mismatch."""
        outcomes = [_outcome(["ds:doc9:0"], qid=f"q{i}") for i in range(3)]
        assert chunk_id_mismatch(outcomes) is False

    def test_one_chunk_hit_disproves_mismatch(self):
        outcomes = [_outcome(["ds:doc1:0042"], golden=("ds:doc1:3",), qid="a"),
                    _outcome(["ds:doc1:0"], qid="b")]
        assert chunk_id_mismatch(outcomes) is False

    def test_empty_is_false(self):
        assert chunk_id_mismatch([]) is False


# ---------------------------------------------------------------------------
# evaluate_queries — batching and mode routing
# ---------------------------------------------------------------------------

class TestEvaluateQueries:
    """Cosa resta a questa funzione dopo A-06: il **punteggio**, non il recupero.

    I test che verificavano il vettore usato, la profondita' del bacino e la
    fusione RRF sono spariti insieme alla copia della pipeline che li
    giustificava. Quel comportamento vive ora in `test_service_answer.py`, dove
    c'e' una implementazione sola da verificare invece di due che devono
    ricordarsi di essere d'accordo.
    """

    def _run(self, config, queries, per_query=None, batch=64):
        risultati = per_query if per_query is not None else [
            [_chunk("ds:doc1:0"), _chunk("ds:doc2:0")] for _ in queries
        ]

        def _retrieve(testi, **kwargs):
            # Il finto backend risponde per la fetta che ha ricevuto, cosi' il
            # batching e' osservabile invece che assunto.
            n = len(testi)
            fuori, self._offset = risultati[self._offset:self._offset + n], self._offset + n
            return fuori

        self._offset = 0
        with patch("dashboard.api_client.retrieve", side_effect=_retrieve) as chiamata:
            out = evaluate_queries(queries, config, batch=batch)
        return out, chiamata

    def test_nessuna_query_non_chiama_il_backend(self):
        with patch("dashboard.api_client.retrieve") as chiamata:
            assert evaluate_queries([], ProbeConfig("ledger")) == []
        chiamata.assert_not_called()

    def test_un_esito_per_query(self):
        queries = [_query(f"q{i}") for i in range(3)]
        out, _ = self._run(ProbeConfig("ledger", "dense"), queries)
        assert len(out) == 3

    def test_un_solo_viaggio_per_batch_non_uno_per_query(self):
        """E' la ragione per cui `/retrieve` accetta una lista: 20 viaggi di
        rete con 20 passate di embedding renderebbero la pagina inusabile."""
        queries = [_query(f"q{i}") for i in range(20)]
        _, chiamata = self._run(ProbeConfig("ledger", "dense"), queries)
        assert chiamata.call_count == 1
        assert len(chiamata.call_args[0][0]) == 20

    def test_batch_grandi_si_spezzano(self):
        """Due ragioni che vanno insieme: l'avanzamento diventa visibile mentre
        gira, e un blocco che fallisce non porta via i precedenti."""
        queries = [_query(f"q{i}") for i in range(10)]
        _, chiamata = self._run(ProbeConfig("ledger", "dense"), queries, batch=4)
        assert chiamata.call_count == 3
        assert [len(c[0][0]) for c in chiamata.call_args_list] == [4, 4, 2]

    def test_la_configurazione_arriva_al_backend(self):
        _, chiamata = self._run(
            ProbeConfig("ledger_routed", "sparse", rerank=True, top_k=7), [_query()]
        )
        kw = chiamata.call_args.kwargs
        assert kw["collection"] == "ledger_routed"
        assert kw["retrieval_mode"] == "sparse"
        assert kw["rerank"] is True
        assert kw["top_k"] == 7

    def test_il_recall_viene_calcolato(self):
        out, _ = self._run(ProbeConfig("ledger", "dense"), [_query()])
        assert out[0].recall == 1.0

    def test_le_query_restano_appaiate_ai_loro_risultati(self):
        """Un risultato vuoto occupa comunque il suo posto: saltarlo farebbe
        scivolare ogni query successiva sul risultato di un'altra."""
        queries = [_query("q0", ("ds:doc1:0",)), _query("q1", ("ds:doc2:0",))]
        out, _ = self._run(
            ProbeConfig("ledger", "dense"), queries,
            per_query=[[], [_chunk("ds:doc2:0")]],
        )
        assert out[0].query.query_id == "q0" and out[0].retrieved_ids == []
        assert out[1].query.query_id == "q1" and out[1].recall == 1.0

    def test_l_avanzamento_si_vede(self):
        queries = [_query(f"q{i}") for i in range(6)]
        visti = []
        self._offset = 0
        risultati = [[_chunk("ds:doc1:0")] for _ in queries]

        def _retrieve(testi, **kwargs):
            n = len(testi)
            fuori, self._offset = risultati[self._offset:self._offset + n], self._offset + n
            return fuori

        with patch("dashboard.api_client.retrieve", side_effect=_retrieve):
            evaluate_queries(queries, ProbeConfig("ledger"), batch=2,
                             on_progress=lambda i, n: visti.append((i, n)))
        assert visti == [(2, 6), (4, 6), (6, 6)]
