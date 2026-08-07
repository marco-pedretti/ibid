"""Tests for E-04: generation baseline (prompts, judge, harness).

All LLM calls are mocked — no server required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.datasets.golden import GoldenQrel, GoldenQuery
from src.datasets.schema import EvalRun
from src.generation.baseline_prompts import (
    ABSTENTION_PHRASES,
    BASELINE_A_SYSTEM,
    BASELINE_B_SYSTEM,
)
from src.generation.judge import judge_answer
from src.eval.generation_harness import is_abstained, run_generation_eval


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _answerable_query(qid: str = "q1", ref: str = "42") -> GoldenQuery:
    return GoldenQuery(
        query_id=qid,
        dataset_id="open_ragbench",
        query_text="What is the answer?",
        qrels=[GoldenQrel(chunk_id="c1", relevance=2)],
        reference_answer=ref,
    )


def _write_golden(tmp_path: Path, queries: list[GoldenQuery]) -> Path:
    p = tmp_path / "test.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(q.model_dump_json() + "\n")
    return p


# ---------------------------------------------------------------------------
# Baseline prompts
# ---------------------------------------------------------------------------

class TestBaselinePrompts:
    def test_baseline_a_does_not_mention_insufficient_information(self):
        assert "Insufficient information" not in BASELINE_A_SYSTEM

    def test_baseline_b_contains_abstention_instruction(self):
        assert "cannot answer without more information" in BASELINE_B_SYSTEM

    def test_baseline_b_different_from_a(self):
        assert BASELINE_A_SYSTEM != BASELINE_B_SYSTEM

    def test_abstention_phrases_non_empty(self):
        assert len(ABSTENTION_PHRASES) > 0


# ---------------------------------------------------------------------------
# is_abstained
# ---------------------------------------------------------------------------

class TestIsAbstained:
    def test_i_dont_know(self):
        assert is_abstained("I don't know the answer.") is True

    def test_i_do_not_know(self):
        assert is_abstained("I do not know.") is True

    def test_cannot_answer(self):
        assert is_abstained("I cannot answer without more information.") is True

    def test_insufficient_information(self):
        assert is_abstained("Insufficient information.") is True

    def test_non_so(self):
        assert is_abstained("Non so rispondere.") is True

    def test_non_posso_rispondere(self):
        assert is_abstained("Non posso rispondere senza maggiori informazioni.") is True

    def test_answered_not_abstained(self):
        assert is_abstained("The maximum value is 400ms.") is False

    def test_empty_string(self):
        assert is_abstained("") is False

    def test_case_insensitive(self):
        assert is_abstained("I DON'T KNOW.") is True


# ---------------------------------------------------------------------------
# judge_answer
# ---------------------------------------------------------------------------

class TestJudgeAnswer:
    def _call(self, verdict: str) -> str:
        with patch("src.generation.judge.generate", return_value=verdict):
            return judge_answer("Q?", "Response.", "Reference.", "http://x", "model")

    def test_correct_verdict(self):
        assert self._call("CORRECT") == "correct"

    def test_wrong_verdict(self):
        assert self._call("WRONG") == "wrong"

    def test_abstained_verdict(self):
        assert self._call("ABSTAINED") == "abstained"

    def test_correct_with_trailing_text(self):
        # Judge sometimes adds explanation after the word
        assert self._call("CORRECT: the values match") == "correct"

    def test_unknown_falls_back_to_wrong(self):
        assert self._call("UNCERTAIN") == "wrong"

    def test_lowercase_correct(self):
        # strip().upper() normalises before matching
        assert self._call("correct") == "correct"


# ---------------------------------------------------------------------------
# run_generation_eval
# ---------------------------------------------------------------------------

class TestRunGenerationEval:
    def test_returns_evalrun(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="The answer is 42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run = run_generation_eval("open_ragbench", path, baseline="A", limit=1)
        assert isinstance(run, EvalRun)

    def test_correct_rate_all_correct(self, tmp_path):
        queries = [_answerable_query(qid=f"q{i}") for i in range(3)]
        path = _write_golden(tmp_path, queries)
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run = run_generation_eval("open_ragbench", path, baseline="A")
        assert run.metrics["correct_rate"] == pytest.approx(1.0)
        assert run.metrics["wrong_rate"] == pytest.approx(0.0)
        assert run.metrics["abstention_rate"] == pytest.approx(0.0)

    def test_abstention_via_heuristic(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="I don't know."):
            run = run_generation_eval("open_ragbench", path, baseline="A", limit=1)
        assert run.metrics["abstention_rate"] == pytest.approx(1.0)

    def test_wrong_rate_all_wrong(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="The answer is 999."), \
             patch("src.eval.generation_harness.judge_answer", return_value="wrong"):
            run = run_generation_eval("open_ragbench", path, baseline="A", limit=1)
        assert run.metrics["wrong_rate"] == pytest.approx(1.0)

    def test_rates_sum_to_one(self, tmp_path):
        queries = [_answerable_query(qid=f"q{i}") for i in range(5)]
        path = _write_golden(tmp_path, queries)

        responses = ["I don't know.", "42.", "42.", "999.", "42."]
        judge_verdicts = ["correct", "correct", "wrong", "correct"]
        response_iter = iter(responses)
        judge_iter = iter(judge_verdicts)

        with patch("src.eval.generation_harness.generate", side_effect=lambda **kw: next(response_iter)), \
             patch("src.eval.generation_harness.judge_answer", side_effect=lambda **kw: next(judge_iter)):
            run = run_generation_eval("open_ragbench", path, baseline="A")

        total = sum(run.metrics.values())
        assert total == pytest.approx(1.0)

    def test_limit_respected(self, tmp_path):
        queries = [_answerable_query(qid=f"q{i}") for i in range(10)]
        path = _write_golden(tmp_path, queries)
        call_count = {"n": 0}

        def fake_generate(**kw):
            call_count["n"] += 1
            return "The answer."

        with patch("src.eval.generation_harness.generate", side_effect=fake_generate), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run_generation_eval("open_ragbench", path, baseline="A", limit=3)

        assert call_count["n"] == 3

    def test_invalid_baseline_raises(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with pytest.raises(ValueError, match="Unknown baseline"):
            run_generation_eval("open_ragbench", path, baseline="Z")

    def test_pipeline_mode_baseline_a(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run = run_generation_eval("open_ragbench", path, baseline="A", limit=1)
        assert run.pipeline_mode == "baseline_a"

    def test_skips_unanswerable_queries(self, tmp_path):
        unanswerable = GoldenQuery(
            query_id="uq1",
            dataset_id="open_ragbench",
            query_text="Unanswerable?",
            qrels=[],
            answerable=False,
        )
        answerable = _answerable_query("aq1")
        path = _write_golden(tmp_path, [unanswerable, answerable])

        call_count = {"n": 0}

        def fake_generate(**kw):
            call_count["n"] += 1
            return "42."

        with patch("src.eval.generation_harness.generate", side_effect=fake_generate), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run_generation_eval("open_ragbench", path, baseline="A")

        assert call_count["n"] == 1

    def test_skips_queries_without_reference_answer(self, tmp_path):
        no_ref = GoldenQuery(
            query_id="nref",
            dataset_id="open_ragbench",
            query_text="No reference?",
            qrels=[GoldenQrel(chunk_id="c1", relevance=2)],
            reference_answer=None,
        )
        path = _write_golden(tmp_path, [no_ref])

        call_count = {"n": 0}

        def fake_generate(**kw):
            call_count["n"] += 1
            return "42."

        with patch("src.eval.generation_harness.generate", side_effect=fake_generate):
            run = run_generation_eval("open_ragbench", path, baseline="A")

        assert call_count["n"] == 0
        assert run.metrics["correct_rate"] == pytest.approx(0.0)

    def test_config_hash_deterministic(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run1 = run_generation_eval("open_ragbench", path, baseline="A", model="m1", limit=1)
            run2 = run_generation_eval("open_ragbench", path, baseline="A", model="m1", limit=1)
        assert run1.config_hash == run2.config_hash

    def test_different_models_different_hash(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run_a = run_generation_eval("open_ragbench", path, baseline="A", model="m1", limit=1)
            run_b = run_generation_eval("open_ragbench", path, baseline="A", model="m2", limit=1)
        assert run_a.config_hash != run_b.config_hash


# ---------------------------------------------------------------------------
# E-05 — Baseline B (strict prompt)
# ---------------------------------------------------------------------------

class TestBaselineB:
    def test_pipeline_mode_is_baseline_b(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run = run_generation_eval("open_ragbench", path, baseline="B", limit=1)
        assert run.pipeline_mode == "baseline_b"

    def test_baseline_b_exact_abstention_phrase_detected(self):
        # The phrase from BASELINE_B_SYSTEM must be detected by is_abstained
        phrase = "I cannot answer without more information."
        assert is_abstained(phrase) is True

    def test_baseline_b_all_abstained(self, tmp_path):
        queries = [_answerable_query(qid=f"q{i}") for i in range(4)]
        path = _write_golden(tmp_path, queries)
        with patch("src.eval.generation_harness.generate",
                   return_value="I cannot answer without more information."):
            run = run_generation_eval("open_ragbench", path, baseline="B")
        assert run.metrics["abstention_rate"] == pytest.approx(1.0)
        assert run.metrics["correct_rate"] == pytest.approx(0.0)
        assert run.metrics["wrong_rate"] == pytest.approx(0.0)

    def test_baseline_b_mixed_abstained_and_correct(self, tmp_path):
        # 2 abstain, 1 correct, 1 wrong  →  rates = 0.5, 0.25, 0.25
        queries = [_answerable_query(qid=f"q{i}") for i in range(4)]
        path = _write_golden(tmp_path, queries)

        responses = [
            "I cannot answer without more information.",
            "I cannot answer without more information.",
            "The answer is 42.",
            "The answer is 999.",
        ]
        judge_verdicts = ["correct", "wrong"]
        resp_iter = iter(responses)
        judge_iter = iter(judge_verdicts)

        with patch("src.eval.generation_harness.generate",
                   side_effect=lambda **_: next(resp_iter)), \
             patch("src.eval.generation_harness.judge_answer",
                   side_effect=lambda **_: next(judge_iter)):
            run = run_generation_eval("open_ragbench", path, baseline="B")

        assert run.metrics["abstention_rate"] == pytest.approx(0.5)
        assert run.metrics["correct_rate"] == pytest.approx(0.25)
        assert run.metrics["wrong_rate"] == pytest.approx(0.25)

    def test_baseline_b_different_hash_from_a(self, tmp_path):
        path = _write_golden(tmp_path, [_answerable_query()])
        with patch("src.eval.generation_harness.generate", return_value="42."), \
             patch("src.eval.generation_harness.judge_answer", return_value="correct"):
            run_a = run_generation_eval("open_ragbench", path, baseline="A", model="m", limit=1)
            run_b = run_generation_eval("open_ragbench", path, baseline="B", model="m", limit=1)
        assert run_a.config_hash != run_b.config_hash

    def test_baseline_b_contains_abstention_instruction(self):
        assert "cannot answer without more information" in BASELINE_B_SYSTEM
