"""R-11: come si sceglie il modo di cercare, e che di default non si sceglie.

Qdrant cerca con HNSW, che e' approssimato.  R-10 ha misurato che su
`ledger_routed` -- 228.331 punti in una banda di similarita' larga 0,0085 -- la
ricerca esatta recupera 857 query su 10.000 che quella approssimata perdeva.

Questi test fissano due cose: che il parametro arrivi davvero fino alla
chiamata (non e' scontato: passa per due funzioni diverse, e una dimenticanza
non darebbe nessun errore, solo risultati peggiori) e che spento non cambi
niente.

**A-02 ha cambiato da dove arriva.** Non piu' da `cfg` letto dentro
`search_params()`, ma dalla configurazione della richiesta: e' un parametro che
non tocca l'indice e cambia a ogni chiamata, quindi due richieste concorrenti
possono legittimamente volerlo diverso. Il percorso da verificare e' percio' piu'
lungo di prima — config → backend → store → Qdrant — e i test lo seguono tutto.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.models import SparseVector
from src.config import RequestConfig
from src.index.store import search, search_batch, search_params
from src.retrieval.backends import RETRIEVERS


class TestSearchParams:
    def test_none_by_default(self):
        """Il default di Qdrant e' lo stato in cui e' stato misurato tutto il
        progetto: non va sostituito con un SearchParams vuoto."""
        assert search_params(exact=False, hnsw_ef=None) is None

    def test_exact_when_asked(self):
        assert search_params(exact=True, hnsw_ef=None).exact is True

    def test_ef_when_asked(self):
        assert search_params(exact=False, hnsw_ef=512).hnsw_ef == 512

    def test_exact_takes_precedence(self):
        """Chiedere entrambi non e' un errore da segnalare: `exact` e' il caso
        limite di `ef` che cresce, quindi vince e basta."""
        p = search_params(exact=True, hnsw_ef=512)
        assert p.exact is True
        assert p.hnsw_ef is None


class TestParamsReachQdrant:
    """Due percorsi di ricerca, due occasioni di dimenticarselo."""

    @pytest.mark.parametrize("exact,ef", [(True, None), (False, 512)])
    def test_search_passes_params(self, exact, ef):
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", [0.1] * 4, top_k=5,
               params=search_params(exact=exact, hnsw_ef=ef))

        params = client.query_points.call_args.kwargs["search_params"]
        assert params is not None
        # `exact` non e' None quando non richiesto: Qdrant lo default-a a False.
        assert bool(params.exact) is exact
        assert params.hnsw_ef == ef

    def test_search_batch_passes_params(self):
        client = MagicMock()
        client.query_batch_points.return_value = []

        search_batch(client, "col", [[0.1] * 4, [0.2] * 4], top_k=5,
                     params=search_params(exact=True, hnsw_ef=None))

        requests = client.query_batch_points.call_args.kwargs["requests"]
        assert len(requests) == 2
        assert all(r.params.exact is True for r in requests)

    def test_default_sends_none_not_empty(self):
        """`SearchParams()` vuoto e `None` si comportano uguale, ma si leggono
        diversamente in un log: il secondo dice "non ho scelto"."""
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", [0.1] * 4, top_k=5)

        assert client.query_points.call_args.kwargs["search_params"] is None

    def test_sparse_path_gets_params_too(self):
        """Il ramo sparso non usa HNSW allo stesso modo, ma passa dalla stessa
        funzione: se un giorno lo usera', il parametro e' gia' collegato."""
        client = MagicMock()
        client.query_points.return_value.points = []

        search(client, "col", SparseVector(indices=[1], values=[1.0]),
               top_k=5, using="sparse", params=search_params(exact=True, hnsw_ef=None))

        assert client.query_points.call_args.kwargs["search_params"].exact is True


class TestDallaConfigurazioneFinoAQdrant:
    """Il percorso intero, che e' quello che A-02 ha allungato.

    I test sopra verificano i due estremi. Questo verifica che siano collegati:
    una dimenticanza in mezzo non darebbe nessun errore, solo una ricerca
    approssimata dove ne era stata chiesta una esatta — cioe' esattamente il
    guasto silenzioso che R-11 esiste per rendere controllabile.
    """

    def _cattura(self, config, mode="dense"):
        client = MagicMock()
        with patch("src.retrieval.backends.encode", return_value=[[0.1] * 4]), \
             patch("src.retrieval.backends.encode_sparse_query",
                   return_value=[SparseVector(indices=[1], values=[1.0])]), \
             patch("src.retrieval.backends.search_batch", return_value=[[]]) as sb:
            RETRIEVERS[mode](client, "col", ["q"], 5, None, config)
        return sb.call_args.kwargs["params"]

    def test_esatta_se_la_richiesta_la_chiede(self):
        params = self._cattura(RequestConfig.from_defaults(search_exact=True))
        assert params.exact is True

    def test_hnsw_ef_se_la_richiesta_lo_chiede(self):
        params = self._cattura(RequestConfig.from_defaults(hnsw_ef=512))
        assert params.hnsw_ef == 512

    def test_niente_se_la_richiesta_non_chiede(self):
        assert self._cattura(RequestConfig.from_defaults()) is None

    @pytest.mark.parametrize("mode", ["dense", "sparse"])
    def test_ogni_modalita_lo_inoltra(self, mode):
        """Tre backend, tre occasioni di scordarselo in uno solo."""
        params = self._cattura(RequestConfig.from_defaults(search_exact=True), mode=mode)
        assert params.exact is True

    def test_hybrid_lo_inoltra_a_entrambi_i_rami(self):
        """Il ramo denso e quello sparso sono due chiamate: una sola con i
        parametri giusti darebbe una fusione fra due ricerche diverse."""
        client = MagicMock()
        with patch("src.retrieval.backends.encode", return_value=[[0.1] * 4]), \
             patch("src.retrieval.backends.encode_sparse_query",
                   return_value=[SparseVector(indices=[1], values=[1.0])]), \
             patch("src.retrieval.backends.search_batch", return_value=[[]]) as sb:
            RETRIEVERS["hybrid"](
                client, "col", ["q"], 5, None,
                RequestConfig.from_defaults(search_exact=True),
            )
        assert len(sb.call_args_list) == 2
        assert all(c.kwargs["params"].exact is True for c in sb.call_args_list)
