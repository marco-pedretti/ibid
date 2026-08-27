"""U-12 / D-10: la logica del controllo di piattaforma, provata dove gira la suite.

Il controllo vero si esegue **sulla macchina che si vuole verificare**, e su
questa non c'e' ne' ROCm ne' CUDA. Quello che si puo' provare qui e' il
ragionamento: che il caso interessante venga riconosciuto, e che frugare dentro
fastembed fallisca in modo pulito invece di sollevare.

**Il caso interessante e' uno solo**, ed e' la ragione per cui lo script guarda
tre cose invece di una: il progetto sceglie un acceleratore, onnxruntime lo
scarta in silenzio perche' non riesce a inizializzarlo, e la sessione finisce su
CPU. Chi guardasse solo `get_available_providers()` leggerebbe «ROCm» e
scriverebbe che funziona.
"""

import pytest
from scripts.verify_platform import _sessione_dell_embedder, verdetto

ROCM = "ROCMExecutionProvider"
CPU = "CPUExecutionProvider"
DML = "DmlExecutionProvider"


class TestVerdetto:
    def test_la_sessione_su_un_acceleratore_e_un_successo(self, capsys):
        codice = verdetto(offerti=[DML, CPU], scelti=[DML, CPU], effettivi=[DML, CPU])
        assert codice == 0
        assert "D-10" in capsys.readouterr().out

    def test_nessun_acceleratore_da_nessuna_parte_non_e_un_guasto(self, capsys):
        """Una macchina senza GPU utilizzabile e' uno stato, non un errore: farlo
        fallire renderebbe il controllo inutilizzabile in CI e sui portatili."""
        codice = verdetto(offerti=[CPU], scelti=[CPU], effettivi=[CPU])
        assert codice == 0
        assert "senza GPU utilizzabile" in capsys.readouterr().out

    def test_scelto_un_acceleratore_e_finita_su_cpu_e_il_caso_che_conta(self, capsys):
        """**Il ripiego silenzioso.** Le prime due domande dicono ROCm, la terza
        dice CPU: senza guardare la terza si scriverebbe che funziona."""
        codice = verdetto(offerti=[ROCM, CPU], scelti=[ROCM, CPU], effettivi=[CPU])
        assert codice == 1
        uscita = capsys.readouterr().out
        assert "ATTENZIONE" in uscita
        assert ROCM in uscita

    def test_due_distribuzioni_insieme_sono_un_ambiente_rotto(self, capsys):
        """**Prima di ogni altra cosa**, perche' rende inaffidabile ogni altra
        cosa: due distribuzioni scrivono lo stesso modulo, e vince chi arriva
        ultimo. Verificato col risolutore di pip in un container Linux:
        `fastembed` + `onnxruntime-rocm` ne installa due."""
        codice = verdetto(
            offerti=[ROCM, CPU],
            scelti=[ROCM, CPU],
            effettivi=[ROCM, CPU],
            distribuzioni=["onnxruntime-rocm 1.22.2", "onnxruntime 1.29.0"],
        )
        assert codice == 1, "un ambiente rotto non e' un successo, neanche con l'acceleratore"
        uscita = capsys.readouterr().out
        assert "ROTTO" in uscita
        assert "pip uninstall" in uscita, "dire cos'e' rotto senza dire come si aggiusta"

    def test_una_distribuzione_sola_non_disturba_il_verdetto(self, capsys):
        assert verdetto([DML, CPU], [DML, CPU], [DML, CPU], ["onnxruntime-directml 1.24"]) == 0

    def test_una_sessione_senza_provider_non_fa_esplodere_il_verdetto(self, capsys):
        """`get_providers()` che torna vuota non deve diventare un IndexError:
        il controllo serve proprio dove le cose non sono normali."""
        assert verdetto(offerti=[], scelti=[CPU], effettivi=[]) == 0


class TestModuloRotto:
    """Lo stato in cui `import onnxruntime` riesce e non c'e' niente dentro.

    **Successo davvero**, su Arch, il 2026-08-27: dopo `pip uninstall -y
    onnxruntime` con due distribuzioni installate, la cartella condivisa se n'e'
    andata con la seconda arrivata. Lo script rispondeva con un `AttributeError`
    a meta' pagina, cioe' con un traceback al posto della diagnosi, proprio nel
    caso per cui esiste.
    """

    def test_dice_cosa_e_rotto_e_come_si_aggiusta(self, monkeypatch, capsys):
        import importlib.metadata as meta
        import sys as sistema
        import types

        from scripts import verify_platform

        guscio = types.ModuleType("onnxruntime")  # senza get_available_providers
        monkeypatch.setitem(sistema.modules, "onnxruntime", guscio)
        monkeypatch.setattr(
            meta, "version", lambda nome: "9.9.9" if nome == "onnxruntime-rocm" else _assente(nome)
        )

        with pytest.raises(SystemExit) as uscita:
            verify_platform.onnx()
        assert uscita.value.code == 1

        stampato = capsys.readouterr().out
        assert "ROTTO" in stampato
        assert "force-reinstall" in stampato, "dire cos'e' rotto senza dire come si aggiusta"
        assert "onnxruntime-rocm" in stampato, "il comando deve nominare la distribuzione giusta"


def _assente(nome):
    from importlib.metadata import PackageNotFoundError

    raise PackageNotFoundError(nome)


class TestSessioneDellEmbedder:
    """Frugare dentro fastembed e' fragile per costruzione, quindi deve fallire
    restituendo `None`: il chiamante ripiega sul verificatore NLI, che e' codice
    nostro. Una catena cambiata deve costare una riga in piu' nell'output, non
    un traceback."""

    class _Sessione:
        def get_providers(self):
            return [DML, CPU]

    def test_trova_la_sessione_dove_sta_oggi(self):
        modello = type("M", (), {"model": type("N", (), {"model": self._Sessione()})()})()
        assert _sessione_dell_embedder(modello) is not None

    def test_catena_interrotta_torna_none(self):
        assert _sessione_dell_embedder(type("M", (), {})()) is None

    def test_oggetto_finale_senza_get_providers_torna_none(self):
        """Il caso peggiore: la catena c'e' ma in fondo non c'e' una sessione."""
        modello = type("M", (), {"model": type("N", (), {"model": object()})()})()
        assert _sessione_dell_embedder(modello) is None


class TestSuQuestaMacchina:
    """Che lo script giri davvero qui, qualunque sia questa macchina."""

    def test_l_ambiente_si_legge_senza_caricare_niente(self, capsys):
        from scripts.verify_platform import la_macchina, la_scelta, le_variabili, onnx

        la_macchina()
        le_variabili()
        _, offerti = onnx()
        scelti = la_scelta()
        uscita = capsys.readouterr().out

        assert "python" in uscita
        assert "HSA_OVERRIDE_GFX_VERSION" in uscita, "la condizione abilitante va stampata"
        assert CPU in offerti, "onnxruntime offre sempre la CPU"
        assert scelti[-1] == CPU, "la CPU resta l'ultima risorsa, sempre"

    def test_una_distribuzione_sola_di_onnxruntime(self):
        """Si escludono a vicenda: due insieme e l'import prende quella che
        capita. Qui la suite gira, quindi qui deve essercene una."""
        from importlib.metadata import PackageNotFoundError, version

        from scripts.verify_platform import DISTRIBUZIONI

        installate = []
        for nome in DISTRIBUZIONI:
            try:
                version(nome)
            except PackageNotFoundError:
                continue
            installate.append(nome)
        assert len(installate) == 1, f"distribuzioni onnxruntime insieme: {installate}"


@pytest.mark.parametrize("nome", ["HSA_OVERRIDE_GFX_VERSION", "ONNX_PROVIDERS"])
def test_le_variabili_abilitanti_sono_dichiarate(nome):
    """Una misura di cui non si registra la condizione abilitante non si ripete."""
    from scripts.verify_platform import ABILITANTI

    assert nome in ABILITANTI
