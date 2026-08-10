"""Tests for src/eval/citation_harness.py (C-01).

All LLM and Qdrant calls are mocked: the harness is tested for what it records
and how it aggregates, not for what a model happens to answer today.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.eval.citation_harness import (
    GenerationRecord,
    build_metrics,
    prompt_hash,
    run_citation_eval,
    write_generations,
)
from src.eval.retrieval_backends import Candidates
from src.generation.chat import Completion
from src.generation.citation_format import VIOLATION_KINDS, check_format, summarize


def _payload(i: int) -> dict:
    return {
        "chunk_id": f"open_ragbench:doc{i}:0001",
        "dataset_id": "open_ragbench",
        "doc_id": f"doc{i}",
        "doc_genre": "academic_pdf",
        "pipeline": "structured_hierarchical",
        "section_path": "Methods",
        "page": 1,
        "content_type": "text",
        "text": f"Chunk number {i} body text.",
        "source_uri": f"http://example.org/doc{i}",
    }


@pytest.fixture
def golden(tmp_path: Path) -> Path:
    rows = [
        {
            "query_id": f"q{i}",
            "query_text": f"Question {i}?",
            "dataset_id": "open_ragbench",
            "answerable": True,
            "qrels": [{"chunk_id": f"open_ragbench:doc{i}:0001", "relevance": 2}],
        }
        for i in range(1, 4)
    ]
    # An unanswerable query the harness must skip.
    rows.append({
        "query_id": "u1", "query_text": "Unanswerable?",
        "dataset_id": "open_ragbench", "answerable": False, "qrels": [],
    })
    p = tmp_path / "open_ragbench.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def _completion(answer, finish_reason="stop", tokens=42):
    return Completion(content=answer, finish_reason=finish_reason, completion_tokens=tokens)


def _run(golden_path, answers, finish_reasons=None, **kw):
    """Run the harness with a canned answer sequence.

    `answers` may be plain strings (assumed to have finished normally) or
    Completion objects when the test is about how the generation ended.
    """
    cands = [Candidates(
        chunk_ids=[_payload(i)["chunk_id"] for i in (1, 2)],
        scores=[0.9, 0.8],
        payloads=[_payload(1), _payload(2)],
    ) for _ in range(3)]
    reasons = finish_reasons or ["stop"] * len(answers)
    completions = [
        a if isinstance(a, Completion) else _completion(a, r)
        for a, r in zip(answers, reasons)
    ]
    with patch("src.eval.citation_harness.get_client"), \
         patch("src.eval.citation_harness.RETRIEVERS",
               {"dense": lambda *a, **k: cands}), \
         patch("src.eval.citation_harness.generate_detailed", side_effect=completions):
        return run_citation_eval(
            dataset_id="open_ragbench", golden_path=golden_path, top_k=2, **kw
        )


class TestRunCitationEval:
    def test_returns_evalrun_and_records(self, golden):
        run, records = _run(golden, ["Vero [1]."] * 3)
        assert run.dataset_id == "open_ragbench"
        assert len(records) == 3

    def test_unanswerable_queries_are_skipped(self, golden):
        _, records = _run(golden, ["Vero [1]."] * 3)
        assert "u1" not in {r.query_id for r in records}

    def test_limit_truncates(self, golden):
        _, records = _run(golden, ["Vero [1]."] * 3, limit=2)
        assert len(records) == 2

    def test_compliance_of_clean_output(self, golden):
        run, _ = _run(golden, ["Vero [1][2]."] * 3)
        assert run.metrics["format_compliance"] == 1.0

    def test_compliance_of_malformed_output(self, golden):
        run, _ = _run(golden, ["Vero [1, 2].", "Vero [1].", "Vero [1]."])
        assert run.metrics["format_compliance"] == pytest.approx(2 / 3)
        assert run.metrics["violation_comma_list"] == pytest.approx(1 / 3)

    def test_raw_answer_is_stored_unrepaired(self, golden):
        _, records = _run(golden, ["Vero [1, 2]."] * 3)
        # Not "[1][2]" — C-02 needs the malformed text to build the parser on.
        assert records[0].answer == "Vero [1, 2]."

    def test_out_of_range_uses_actual_context_size(self, golden):
        # top_k=2, so [3] points outside the context.
        run, _ = _run(golden, ["Vero [3]."] * 3)
        assert run.metrics["violation_out_of_range"] == 1.0

    def test_record_carries_the_chunk_ids_in_context(self, golden):
        _, records = _run(golden, ["Vero [1]."] * 3)
        assert records[0].chunk_ids == [
            "open_ragbench:doc1:0001", "open_ragbench:doc2:0001",
        ]

    def test_abstention_leaves_the_denominator(self, golden):
        run, _ = _run(golden, ["Insufficient information.", "Vero [1].", "Vero [1]."])
        assert run.metrics["format_compliance"] == 1.0
        assert run.metrics["abstention_rate"] == pytest.approx(1 / 3)

    def test_empty_dataset_raises(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError):
            _run(p, [])

    def test_latency_recorded_per_answer(self, golden):
        _, records = _run(golden, ["Vero [1]."] * 3)
        assert all(r.latency_s >= 0 for r in records)


class TestEvalRunContract:
    def test_pipeline_mode_stays_binary(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.pipeline_mode == "generic"
        run2, _ = _run(golden, ["Vero [1]."] * 3, pipeline_mode="routed")
        assert run2.pipeline_mode == "routed"

    def test_config_records_the_prompt_hash(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3, system_prompt="PROMPT A")
        assert run.config["prompt_hash"] == prompt_hash("PROMPT A")

    def test_config_marks_the_harness(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.config["harness"] == "citation"

    def test_n_queries_is_what_ran(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3, limit=2)
        assert run.config["n_queries"] == 2

    def test_temperature_is_zero(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.temperature == 0.0

    def test_git_commit_recorded(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.git_commit

    def test_changing_the_prompt_changes_the_config_hash(self, golden):
        """Two prompts must never share a config_hash.

        The prompt is the variable under test in C-01.  If it stayed out of the
        hash, a reworded prompt would produce a second measurement claiming to
        be the same configuration as the first.
        """
        a, _ = _run(golden, ["Vero [1]."] * 3, system_prompt="PROMPT A")
        b, _ = _run(golden, ["Vero [1]."] * 3, system_prompt="PROMPT B")
        assert a.config_hash != b.config_hash

    def test_same_prompt_same_hash(self, golden):
        a, _ = _run(golden, ["Vero [1]."] * 3, system_prompt="P")
        b, _ = _run(golden, ["Vero [2]."] * 3, system_prompt="P")
        assert a.config_hash == b.config_hash


class TestTruncation:
    """A cut-off answer must not be blamed on the prompt.

    In the first C-01 run the model spent its whole token budget on invisible
    reasoning: 3% of answers came back empty and were scored as `no_citation`,
    which reads as a prompt defect and is not one.
    """

    def test_finish_reason_recorded(self, golden):
        _, records = _run(golden, ["Vero [1].", "Tronc", "Vero [1]."],
                          finish_reasons=["stop", "length", "stop"])
        assert [r.finish_reason for r in records] == ["stop", "length", "stop"]

    def test_truncation_rate_reported(self, golden):
        run, _ = _run(golden, ["Vero [1].", "Tronc", "Vero [1]."],
                      finish_reasons=["stop", "length", "stop"])
        assert run.metrics["truncation_rate"] == pytest.approx(1 / 3)

    def test_truncation_rate_is_zero_not_missing_on_a_clean_run(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.metrics["truncation_rate"] == 0.0

    def test_empty_answer_rate(self, golden):
        run, _ = _run(golden, ["", "Vero [1].", "Vero [1]."],
                      finish_reasons=["length", "stop", "stop"])
        assert run.metrics["empty_answer_rate"] == pytest.approx(1 / 3)

    def test_completion_tokens_recorded(self, golden):
        _, records = _run(golden, [_completion("Vero [1].", tokens=267)] * 3)
        assert records[0].completion_tokens == 267

    def test_reasoning_enabled_follows_config(self, golden, monkeypatch):
        import src.config as cfg
        monkeypatch.setattr(cfg, "REASONING_EFFORT", "none")
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.reasoning_enabled is False
        monkeypatch.setattr(cfg, "REASONING_EFFORT", "high")
        run2, _ = _run(golden, ["Vero [1]."] * 3)
        assert run2.reasoning_enabled is True

    def test_config_records_the_token_budget(self, golden):
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert "reasoning_effort" in run.config
        assert "max_new_tokens" in run.config


class TestBuildMetrics:
    @staticmethod
    def _rec(answer, finish_reason="stop"):
        return GenerationRecord(
            query_id="q", query_text="Q?", chunk_ids=["c"], n_chunks=2,
            answer=answer, compliant=True, abstained=False, markers=[1],
            finish_reason=finish_reason,
        )

    def test_every_violation_kind_is_a_key(self):
        m = build_metrics(summarize([check_format("Vero [1].", 2)]), [self._rec("Vero [1].")])
        for kind in VIOLATION_KINDS:
            assert f"violation_{kind}" in m

    def test_compliance_and_abstention_reported_together(self):
        m = build_metrics(
            summarize([check_format("Vero [1].", 2),
                       check_format("Insufficient information.", 2)]),
            [self._rec("Vero [1]."), self._rec("Insufficient information.")],
        )
        assert m["format_compliance"] == 1.0
        assert m["abstention_rate"] == 0.5

    def test_all_metrics_are_floats(self):
        m = build_metrics(summarize([check_format("Vero [1].", 2)]), [self._rec("Vero [1].")])
        assert all(isinstance(v, float) for v in m.values())

    def test_no_records_does_not_divide_by_zero(self):
        m = build_metrics(summarize([]), [])
        assert m["truncation_rate"] == 0.0 and m["empty_answer_rate"] == 0.0


class TestWriteGenerations:
    def _records(self):
        return [GenerationRecord(
            query_id="q1", query_text="Q?", chunk_ids=["c1"], n_chunks=1,
            answer="Vero [1, 2].", compliant=False, abstained=False,
            markers=[1, 2], violations=[{"kind": "comma_list", "snippet": "[1, 2]"}],
        )]

    def test_jsonl_one_record_per_line(self, tmp_path):
        p = tmp_path / "gen.jsonl"
        write_generations(p, self._records() * 3, "SYS")
        assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 3

    def test_record_roundtrips(self, tmp_path):
        p = tmp_path / "gen.jsonl"
        write_generations(p, self._records(), "SYS")
        row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
        assert row["answer"] == "Vero [1, 2]."
        assert row["violations"][0]["kind"] == "comma_list"

    def test_prompt_written_beside_it(self, tmp_path):
        p = tmp_path / "gen.jsonl"
        write_generations(p, self._records(), "SYSTEM PROMPT TEXT")
        assert (tmp_path / "gen.prompt.txt").read_text(encoding="utf-8") == "SYSTEM PROMPT TEXT"

    def test_creates_missing_directory(self, tmp_path):
        p = tmp_path / "nested" / "gen.jsonl"
        write_generations(p, self._records(), "SYS")
        assert p.exists()

    def test_non_ascii_survives(self, tmp_path):
        recs = self._records()
        recs[0].answer = "Il valore è 400ms [1]."
        p = tmp_path / "gen.jsonl"
        write_generations(p, recs, "SYS")
        assert "400ms" in json.loads(p.read_text(encoding="utf-8"))["answer"]


class TestPromptHash:
    def test_stable(self):
        assert prompt_hash("abc") == prompt_hash("abc")

    def test_differs_on_whitespace(self):
        # Prompt edits are often whitespace-only; they still change the run.
        assert prompt_hash("a b") != prompt_hash("a  b")

    def test_short(self):
        assert len(prompt_hash("x")) == 8
