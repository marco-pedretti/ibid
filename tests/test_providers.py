"""Q-05: la scelta dell'acceleratore ONNX, in un posto solo.

Questi test non possono verificare che DirectML sia veloce — verificano che la
**decisione** sia quella dichiarata, su qualunque insieme di provider la
macchina offra.  È l'unico modo di provare qualcosa sulla portabilità Linux
sviluppando su Windows: non si esegue su ROCm, si controlla che se ROCm ci
fosse verrebbe scelto.
"""

from __future__ import annotations

import pytest

import src.config as cfg
from src import providers


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch):
    """L'ambiente reale non deve decidere l'esito dei test."""
    monkeypatch.setattr(cfg, "ONNX_PROVIDERS", "")


def _offers(monkeypatch, *names: str) -> None:
    monkeypatch.setattr(providers, "available", lambda: list(names))


class TestSelection:
    def test_cpu_is_always_last(self, monkeypatch):
        """Ometterla trasformerebbe un acceleratore assente in un errore."""
        _offers(monkeypatch, "DmlExecutionProvider", providers.CPU)
        assert providers.onnx_providers()[-1] == providers.CPU

    def test_cpu_present_even_when_not_offered(self, monkeypatch):
        _offers(monkeypatch, "DmlExecutionProvider")
        assert providers.CPU in providers.onnx_providers()

    def test_directml_wins_on_windows(self, monkeypatch):
        _offers(monkeypatch, providers.CPU, "DmlExecutionProvider")
        assert providers.onnx_providers()[0] == "DmlExecutionProvider"

    def test_rocm_is_chosen_when_offered(self, monkeypatch):
        """La riga che rende Q-05 la cucitura di U-12.

        Su Linux DirectML non esiste: prima di questo modulo si finiva su CPU
        anche con una GPU capace, perché nessun elenco nominava ROCm.
        """
        _offers(monkeypatch, providers.CPU, "ROCMExecutionProvider")
        assert providers.onnx_providers()[0] == "ROCMExecutionProvider"

    def test_cuda_is_chosen_when_offered(self, monkeypatch):
        _offers(monkeypatch, providers.CPU, "CUDAExecutionProvider")
        assert providers.onnx_providers()[0] == "CUDAExecutionProvider"

    def test_preference_order_is_respected(self, monkeypatch):
        """Con più acceleratori disponibili vince quello dichiarato per primo,
        non quello che onnxruntime elenca per primo."""
        _offers(monkeypatch, "CUDAExecutionProvider", "DmlExecutionProvider", providers.CPU)
        assert providers.onnx_providers()[0] == "DmlExecutionProvider"

    def test_unknown_providers_are_ignored(self, monkeypatch):
        """Un provider che non abbiamo mai valutato non viene usato per caso."""
        _offers(monkeypatch, "TensorrtExecutionProvider", providers.CPU)
        assert providers.onnx_providers() == [providers.CPU]

    def test_no_duplicates(self, monkeypatch):
        _offers(monkeypatch, "DmlExecutionProvider", providers.CPU)
        chosen = providers.onnx_providers()
        assert len(chosen) == len(set(chosen))


class TestFallbackIsDeclared:
    """Il criterio di accettazione: ripiegare su CPU **dichiarandolo**."""

    def test_warns_when_no_accelerator(self, monkeypatch):
        _offers(monkeypatch, providers.CPU)
        with pytest.warns(providers.NoAcceleratorWarning):
            assert providers.onnx_providers() == [providers.CPU]

    def test_does_not_warn_when_accelerated(self, monkeypatch, recwarn):
        _offers(monkeypatch, "DmlExecutionProvider", providers.CPU)
        providers.onnx_providers()
        assert not [w for w in recwarn if w.category is providers.NoAcceleratorWarning]

    def test_warning_can_be_silenced(self, monkeypatch, recwarn):
        """`active_accelerator()` interroga, non esegue: non deve avvisare."""
        _offers(monkeypatch, providers.CPU)
        assert providers.active_accelerator() is None
        assert not [w for w in recwarn if w.category is providers.NoAcceleratorWarning]


class TestEnvOverride:
    def test_env_wins(self, monkeypatch):
        _offers(monkeypatch, "DmlExecutionProvider", providers.CPU)
        monkeypatch.setattr(cfg, "ONNX_PROVIDERS", providers.CPU)
        assert providers.onnx_providers() == [providers.CPU]

    def test_env_accepts_a_list(self, monkeypatch):
        monkeypatch.setattr(cfg, "ONNX_PROVIDERS",
                            "ROCMExecutionProvider, CPUExecutionProvider")
        assert providers.onnx_providers() == ["ROCMExecutionProvider", providers.CPU]

    def test_blank_env_means_decide_normally(self, monkeypatch):
        _offers(monkeypatch, "DmlExecutionProvider", providers.CPU)
        monkeypatch.setattr(cfg, "ONNX_PROVIDERS", "   ")
        assert providers.onnx_providers()[0] == "DmlExecutionProvider"

    def test_describe_says_when_forced(self, monkeypatch):
        monkeypatch.setattr(cfg, "ONNX_PROVIDERS", providers.CPU)
        assert "imposto" in providers.describe()


class TestNobodyPicksProvidersAlone:
    """La duplicazione che Q-05 chiude, con la prova che non è tornata."""

    def test_only_providers_module_names_an_execution_provider(self):
        from pathlib import Path
        root = Path(__file__).parent.parent
        offenders = []
        # `config.py` li nomina negli esempi di come si imposta ONNX_PROVIDERS:
        # documenta il formato, non compie la scelta.
        exempt = {"providers.py", "config.py"}
        for p in list((root / "src").rglob("*.py")) + list((root / "scripts").glob("*.py")):
            if p.name in exempt or "__pycache__" in str(p):
                continue
            if "ExecutionProvider" in p.read_text(encoding="utf-8"):
                offenders.append(str(p.relative_to(root)))
        assert not offenders, (
            "scelgono l'acceleratore per conto proprio invece di chiedere a "
            f"src/providers.py: {offenders}"
        )
