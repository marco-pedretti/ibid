"""R-11: come si sceglie il modo di cercare, e che di default non si sceglie.

Qdrant cerca con HNSW, che e' approssimato.  R-10 ha misurato che su
`ledger_routed` -- 228.331 punti in una banda di similarita' larga 0,0085 -- la
ricerca esatta recupera 857 query su 10.000 che quella approssimata perdeva.

Questi test fissano due cose: che il parametro arrivi davvero fino alla
chiamata (non e' scontato: passa per due funzioni diverse, e una dimenticanza
non darebbe nessun errore, solo risultati peggiori) e che spento non cambi
niente.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from qdrant_client.models import SparseVector

import src.config as cfg
from src.index.store import search, search_batch, search_params


class TestSearchParams:
    def test_none_by_default(self, monkeypatch):
        """Il default di Qdrant e' lo stato in cui e' stato misurato tutto il
        progetto: non va sostituito con un SearchParams vuoto."""
        monkeypatch.setattr(cfg, "SEARCH_EXACT", False)
        monkeypatch.setattr(cfg, "HNSW_EF", None)
        assert search_params() is None

    def test_exact_when_asked(self, monkeypatch):
        monkeypatch.setattr(cfg, "SEARCH_EXACT", True)
        monkeypatch.setattr(cfg, "HNSW_EF", None)
        assert search_params().exact is True

    def test_ef_when_asked(self, monkeypatch):
        monkeypatch.setattr(cfg, "SEARCH_EXACT", False)
        monkeypatch.setattr(cfg, "HNSW_EF", 512)
        assert search_params().hnsw_ef == 512

    def test_exact_takes_precedence(self, monkeypatch):
        """Chiedere entrambi non e' un errore da segnalare: `exact` e' il caso
        limite di `ef` che cresce, quindi vince e basta."""
        monkeypatch.setattr(cfg, "SEARCH_EXACT", True)
        monkeypatch.setattr(cfg, "HNSW_EF", 512)
        p = search_params()
        assert p.exact is True
        assert p.hnsw_ef is None


class TestParamsReachQdrant:
    """Due percorsi di ricerca, due occasioni di dimenticarselo."""

    @pytest.mark.parametrize("exact,ef", [(True, None), (False, 512)])
    def test_search_passes_params(self, monkeypatch, exact, ef):
        monkeypatch.setattr(cfg, "SEARCH_EXACT", exact)
        monkeypatch.setattr(cfg, "HNSW_EF", ef)
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", [0.1] * 4, top_k=5)

        params = client.query_points.call_args.kwargs["search_params"]
        assert params is not None
        # `exact` non e' None quando non richiesto: Qdrant lo default-a a False.
        assert bool(params.exact) is exact
        assert params.hnsw_ef == ef

    def test_search_batch_passes_params(self, monkeypatch):
        monkeypatch.setattr(cfg, "SEARCH_EXACT", True)
        monkeypatch.setattr(cfg, "HNSW_EF", None)
        client = MagicMock()
        client.query_batch_points.return_value = []

        search_batch(client, "col", [[0.1] * 4, [0.2] * 4], top_k=5)

        requests = client.query_batch_points.call_args.kwargs["requests"]
        assert len(requests) == 2
        assert all(r.params.exact is True for r in requests)

    def test_default_sends_none_not_empty(self, monkeypatch):
        """`SearchParams()` vuoto e `None` si comportano uguale, ma si leggono
        diversamente in un log: il secondo dice "non ho scelto"."""
        monkeypatch.setattr(cfg, "SEARCH_EXACT", False)
        monkeypatch.setattr(cfg, "HNSW_EF", None)
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", [0.1] * 4, top_k=5)

        assert client.query_points.call_args.kwargs["search_params"] is None

    def test_sparse_path_gets_params_too(self, monkeypatch):
        """Il ramo sparso non usa HNSW allo stesso modo, ma passa dalla stessa
        funzione: se un giorno lo usera', il parametro e' gia' collegato."""
        monkeypatch.setattr(cfg, "SEARCH_EXACT", True)
        monkeypatch.setattr(cfg, "HNSW_EF", None)
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", SparseVector(indices=[1], values=[1.0]),
               top_k=5, using="sparse")

        assert client.query_points.call_args.kwargs["search_params"].exact is True
