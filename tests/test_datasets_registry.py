"""Q-06: il registro dei dataset.

Il valore di questo modulo non è che funzioni — è che sia **l'unico posto** che
sa quali dataset esistono.  Quindi metà di questi test guarda il registro e
l'altra metà guarda il resto del repo, per accorgersi se qualcuno ricomincia a
scrivere gli identificativi a mano.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.datasets import registry

ROOT = Path(__file__).parent.parent


class TestRegistry:
    def test_both_datasets_present(self):
        assert set(registry.dataset_ids()) == {"open_ragbench", "ledger"}

    def test_cli_choices_include_all(self):
        assert registry.cli_choices() == ["open_ragbench", "ledger", "all"]

    def test_resolve_expands_all(self):
        assert registry.resolve("all") == registry.dataset_ids()

    def test_resolve_single_is_a_list(self):
        assert registry.resolve("ledger") == ["ledger"]

    def test_get_returns_the_spec(self):
        assert registry.get("ledger").repo_id == "artefactory/ledger-long-context-KPI-QA"

    def test_unknown_dataset_names_the_known_ones(self):
        """Un KeyError nudo direbbe solo il nome sbagliato, non quali sono giusti."""
        with pytest.raises(KeyError, match="open_ragbench"):
            registry.get("non_esiste")

    @pytest.mark.parametrize("dataset_id", ["open_ragbench", "ledger"])
    def test_spec_id_matches_its_key(self, dataset_id):
        """Una voce copiata e incollata male è invisibile finché non si ingesta."""
        assert registry.get(dataset_id).dataset_id == dataset_id

    @pytest.mark.parametrize("dataset_id", ["open_ragbench", "ledger"])
    def test_corpus_dir_is_under_the_dataset_dir(self, dataset_id, tmp_path):
        spec = registry.get(dataset_id)
        assert spec.dataset_dir(tmp_path) in spec.corpus_dir(tmp_path).parents

    @pytest.mark.parametrize("dataset_id", ["open_ragbench", "ledger"])
    def test_every_callable_is_callable(self, dataset_id):
        spec = registry.get(dataset_id)
        for field in ("download", "iter_chunks", "iter_chunks_routed", "load_golden"):
            assert callable(getattr(spec, field)), field

    @staticmethod
    def _spy_spec(seen: dict) -> registry.DatasetSpec:
        """Una spec finta. `DatasetSpec` è frozen, quindi non si può sostituire
        un campo su quelle vere — ed è giusto così: sono dichiarazioni."""

        def record(key):
            def f(d):
                seen[key] = d
                return iter([])
            return f

        return registry.DatasetSpec(
            dataset_id="finto", repo_id="x/y", corpus_subpath=("c",),
            download=lambda d: d,
            iter_chunks=record("plain"),
            iter_chunks_routed=record("routed"),
            load_golden=lambda d: [],
        )

    def test_chunks_picks_the_routed_iterator(self, tmp_path):
        seen: dict = {}
        list(self._spy_spec(seen).chunks(tmp_path, pipeline_mode="routed"))
        assert "routed" in seen and "plain" not in seen

    def test_chunks_defaults_to_the_single_pipeline(self, tmp_path):
        seen: dict = {}
        list(self._spy_spec(seen).chunks(tmp_path))
        assert "plain" in seen and "routed" not in seen

    def test_chunks_passes_the_dataset_dir_not_the_data_dir(self, tmp_path):
        """L'errore che questo previene: `iter_chunks(data_dir)` invece di
        `iter_chunks(data_dir / dataset_id)` — trova zero documenti in silenzio."""
        seen: dict = {}
        list(self._spy_spec(seen).chunks(tmp_path))
        assert seen["plain"] == tmp_path / "finto"


class TestNobodyHardcodesTheListAgain:
    """Il difetto che Q-06 chiude, con la prova che non è tornato.

    Prima c'erano **14** `choices=["open_ragbench", "ledger", "all"]` scritti a
    mano.  Senza questo test il quindicesimo arriva alla prossima CLI, e nessuno
    se ne accorge finché non si aggiunge un dataset.
    """

    #: I file dove i nomi *devono* comparire: i loader, il registro, e i test
    #: che verificano proprio quei nomi.
    ALLOWED = {
        Path("src/datasets/registry.py"),
        Path("src/datasets/open_ragbench.py"),
        Path("src/datasets/ledger.py"),
        Path("src/datasets/golden.py"),
        Path("src/datasets/unanswerable.py"),
        Path("src/datasets/schema.py"),
        Path("src/config.py"),
        Path("tests/test_datasets_registry.py"),
        # Debito dichiarato, non dimenticanza: `fetch_dataset.py` accetta
        # `--dataset` e poi lo ignora, usando open_ragbench ovunque. Collegarlo
        # al registro gli fa guadagnare il supporto per ledger, che e' un
        # cambiamento di comportamento e non entra nel commit di un refactor.
        # Va tolto da questa lista nel commit che lo sistema.
        Path("scripts/fetch_dataset.py"),
    }

    def _sources(self):
        for d in ("scripts", "src"):
            for p in (ROOT / d).rglob("*.py"):
                rel = p.relative_to(ROOT)
                if rel not in self.ALLOWED and "__pycache__" not in str(rel):
                    yield rel, p.read_text(encoding="utf-8")

    def test_no_script_hardcodes_the_choices_list(self):
        pattern = re.compile(r"choices\s*=\s*\[[^\]]*open_ragbench", re.S)
        offenders = [str(rel) for rel, text in self._sources() if pattern.search(text)]
        assert not offenders, (
            "questi file scrivono la lista dei dataset a mano invece di leggerla "
            f"dal registro: {offenders}"
        )

    def test_no_module_branches_on_the_dataset_name(self):
        """`if dataset_id == "open_ragbench"` era la catena in ingest.py."""
        pattern = re.compile(r"==\s*[\"']open_ragbench[\"']|[\"']open_ragbench[\"']\s*==")
        offenders = [str(rel) for rel, text in self._sources() if pattern.search(text)]
        assert not offenders, f"ramificano sul nome del dataset: {offenders}"
