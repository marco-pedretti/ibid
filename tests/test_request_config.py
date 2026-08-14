"""A-02: la configurazione di una richiesta e' un oggetto, non un modulo.

Il criterio del task parla di due richieste concorrenti che non si contaminano.
Contaminarsi vuol dire una cosa precisa: che la scelta dell'una diventi visibile
all'altra. Qui si verificano le due proprieta' che lo impediscono — la
configurazione e' immutabile, e le costanti globali si leggono in un posto solo.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
import src.config as cfg
from src.config import RequestConfig

ROOT = Path(__file__).parent.parent


class TestCostruzione:
    def test_i_default_vengono_dalle_costanti_del_modulo(self):
        c = RequestConfig.from_defaults()
        assert c.top_k == cfg.TOP_K
        assert c.model == cfg.LLM_MODEL
        assert c.temperature == cfg.TEMPERATURE
        assert c.max_new_tokens == cfg.MAX_NEW_TOKENS
        assert c.reasoning_effort == cfg.REASONING_EFFORT
        assert c.rrf_k == cfg.RRF_K
        assert c.hybrid_fetch_k == cfg.HYBRID_FETCH_K
        assert c.rerank_fetch_k == cfg.RERANK_FETCH_K
        assert c.reranker_model == cfg.RERANKER_MODEL
        assert c.search_exact == cfg.SEARCH_EXACT
        assert c.hnsw_ef == cfg.HNSW_EF

    def test_gli_override_vincono(self):
        c = RequestConfig.from_defaults(top_k=3, retrieval_mode="hybrid", rerank=True)
        assert (c.top_k, c.retrieval_mode, c.rerank) == (3, "hybrid", True)

    def test_una_chiave_sconosciuta_solleva(self):
        """Un parametro scritto male che non ha effetto e' peggio di uno
        rifiutato: la richiesta sembra rispettata e non lo e'."""
        with pytest.raises(TypeError):
            RequestConfig.from_defaults(topk=3)

    def test_nessun_campo_ha_un_default_nella_classe(self):
        """`from_defaults` deve restare l'unico posto che legge le globali.

        Un default scritto sul campo sarebbe una seconda sorgente di verita', e
        la prima cosa che farebbe e' divergere da questa.
        """
        senza_default = [
            f.name for f in dataclasses.fields(RequestConfig)
            if f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
        ]
        assert len(senza_default) == len(dataclasses.fields(RequestConfig))


class TestImmutabilita:
    def test_non_si_puo_modificare(self):
        """E' la garanzia, non uno stile: cio' che nessuno puo' modificare non
        puo' essere modificato da un'altra richiesta."""
        c = RequestConfig.from_defaults()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.top_k = 99  # type: ignore[misc]

    def test_una_variante_e_un_oggetto_nuovo(self):
        c = RequestConfig.from_defaults(top_k=5)
        d = dataclasses.replace(c, top_k=10)
        assert (c.top_k, d.top_k) == (5, 10)


class TestDerivati:
    @pytest.mark.parametrize("effort,atteso", [
        ("none", False), ("", False), ("low", True), ("high", True),
    ])
    def test_reasoning_enabled_e_dedotto(self, effort, atteso):
        assert RequestConfig.from_defaults(reasoning_effort=effort).reasoning_enabled is atteso

    def test_il_modello_di_riscrittura_ripiega_su_quello_di_generazione(self):
        c = RequestConfig.from_defaults(model="gemma4:12b", query_rewrite_model="")
        assert c.rewrite_model == "gemma4:12b"

    def test_il_modello_di_riscrittura_esplicito_vince(self):
        c = RequestConfig.from_defaults(model="gemma4:12b", query_rewrite_model="gemma4:e2b")
        assert c.rewrite_model == "gemma4:e2b"


class TestCosaNonEDentro:
    """Le assenze sono decisioni, e vanno protette come le presenze.

    Un campo aggiunto qui per comodita' — «tanto e' solo il modello di
    embedding» — riaprirebbe un buco che questo test esiste per tenere chiuso.
    """

    NOMI = {f.name for f in dataclasses.fields(RequestConfig)}

    def test_il_modello_di_embedding_non_e_per_richiesta(self):
        """L'indice e' stato costruito con lui: interrogarlo con un altro
        restituisce spazzatura **senza errore**."""
        assert "embedding_model" not in self.NOMI
        assert "sparse_embedding_model" not in self.NOMI

    def test_gli_indirizzi_dei_servizi_non_sono_per_richiesta(self):
        """Una richiesta HTTP non puo' spostare la macchina."""
        assert not {"qdrant_url", "llm_base_url"} & self.NOMI

    def test_le_soglie_calibrate_non_sono_per_richiesta(self):
        """Sono derivate da misure, non preferenze. Lasciarle scegliere a chi
        chiama permetterebbe di tarare la soglia sulla stessa risposta che quella
        soglia deve giudicare."""
        assert not {
            "entailment_threshold", "abstention_thresholds", "abstention_budget",
            "numeric_row_match_ratio",
        } & self.NOMI


class TestUnicoPuntoDiLettura:
    """Il valore di `RequestConfig` non e' che esista: e' che sia l'unica strada.

    Questo test guarda il resto del repo, non la classe. E' la forma che questo
    progetto ha gia' usato in Q-06 per il registro dei dataset, e per la stessa
    ragione: senza, la prossima lettura diretta di `cfg.TOP_K` lungo il percorso
    di servizio arriva e non se ne accorge nessuno.
    """

    def test_from_defaults_e_l_unico_costruttore_in_src(self):
        """Costruire un `RequestConfig` a mano significherebbe scrivere quindici
        valori, e sbagliarne uno in silenzio."""
        colpevoli = []
        for path in (ROOT / "src").rglob("*.py"):
            if path.name == "config.py":
                continue
            for n, riga in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"RequestConfig\(", riga):
                    colpevoli.append(f"{path.relative_to(ROOT)}:{n}: {riga.strip()}")
        assert colpevoli == []
