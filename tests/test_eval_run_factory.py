"""Q-01: `EvalRun` si costruisce in un posto solo.

Erano cinque siti con lo stesso preambolo. Quattro deducevano
`reasoning_enabled` dalla configurazione, il quinto lo scriveva `False` a mano
— che è la forma che prende una duplicazione quando invecchia: la correzione
arriva ad alcune copie e non a tutte.

Come in Q-05 e Q-06, metà dei test guarda la fabbrica e metà guarda il resto
del repo, perché la proprietà da difendere non è «la funzione funziona» ma
«nessun altro lo fa per conto suo».
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import src.config as cfg
from src.eval.run_config import make_eval_run, reasoning_enabled

ROOT = Path(__file__).parent.parent


def _run(**kw):
    base = dict(
        git_commit="abc1234",
        config_hash="deadbeef",
        dataset_id="open_ragbench",
        pipeline_mode="generic",
        config={},
        metrics={},
        llm=None,
    )
    return make_eval_run(**{**base, **kw})


class TestReasoningIsDerived:
    @pytest.mark.parametrize("effort,expected", [
        ("none", False), ("", False), (None, False),
        ("low", True), ("medium", True), ("high", True), ("max", True),
    ])
    def test_follows_the_config(self, monkeypatch, effort, expected):
        monkeypatch.setattr(cfg, "REASONING_EFFORT", effort)
        assert reasoning_enabled() is expected

    def test_a_run_with_an_llm_records_it(self, monkeypatch):
        monkeypatch.setattr(cfg, "REASONING_EFFORT", "high")
        assert _run(llm="gemma4:e4b").reasoning_enabled is True

    def test_a_run_without_an_llm_cannot_be_reasoning(self, monkeypatch):
        """Nessun modello ha girato: `False` qui non è una dichiarazione, è
        l'unica cosa che può essere vera."""
        monkeypatch.setattr(cfg, "REASONING_EFFORT", "high")
        assert _run(llm=None).reasoning_enabled is False


class TestTheLlmFieldsFollowTheLlm:
    def test_no_llm_says_so_in_every_field(self):
        run = _run(llm=None)
        assert run.model == "retrieval_only"
        assert run.quantization == "none"
        assert run.context_window == 0
        assert run.temperature == 0.0

    def test_with_llm_the_fields_come_from_config(self, monkeypatch):
        monkeypatch.setattr(cfg, "CONTEXT_WINDOW", 32768)
        monkeypatch.setattr(cfg, "TEMPERATURE", 0.0)
        run = _run(llm="gemma4:12b")
        assert run.model == "gemma4:12b"
        assert run.quantization == cfg.LLM_QUANTIZATION
        assert run.context_window == 32768


class TestProvenance:
    def test_git_commit_is_passed_in_not_computed(self):
        """Gli harness lo catturano **prima** della run, di proposito: una run
        lunga può finire dopo un commit, e il valore che serve è quello del
        codice che ha girato. Calcolarlo dentro la fabbrica avrebbe cambiato
        quella semantica senza che nessun test se ne accorgesse — quindi ecco il
        test che se ne accorgerebbe."""
        assert _run(git_commit="0123456").git_commit == "0123456"

    def test_each_run_gets_its_own_id(self):
        assert _run().run_id != _run().run_id

    def test_timestamp_is_timezone_aware(self):
        assert _run().timestamp.tzinfo is not None


class TestNobodyBuildsEvalRunAlone:
    """Il difetto che Q-01 chiude, con la prova che non è tornato."""

    ALLOWED = {
        Path("src/eval/run_config.py"),      # la fabbrica
        Path("src/datasets/schema.py"),      # la definizione
    }

    def test_only_the_factory_constructs_an_evalrun(self):
        pattern = re.compile(r"\bEvalRun\(")
        offenders = []
        for d in ("src", "scripts", "dashboard"):
            for p in (ROOT / d).rglob("*.py"):
                rel = p.relative_to(ROOT)
                if rel in self.ALLOWED or "__pycache__" in str(rel):
                    continue
                if pattern.search(p.read_text(encoding="utf-8")):
                    offenders.append(str(rel))
        assert not offenders, (
            "costruiscono un EvalRun invece di chiedere a "
            f"run_config.make_eval_run: {offenders}"
        )

    def test_nobody_derives_reasoning_enabled_on_their_own(self):
        pattern = re.compile(r"REASONING_EFFORT\s+not\s+in")
        offenders = []
        for d in ("src", "scripts", "dashboard"):
            for p in (ROOT / d).rglob("*.py"):
                rel = p.relative_to(ROOT)
                if rel in self.ALLOWED or "__pycache__" in str(rel):
                    continue
                if pattern.search(p.read_text(encoding="utf-8")):
                    offenders.append(str(rel))
        assert not offenders, f"deducono reasoning_enabled per conto proprio: {offenders}"
