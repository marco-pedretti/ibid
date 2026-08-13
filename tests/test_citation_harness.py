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

import src.config as cfg
import src.eval.citation_harness as citation_harness
from src.eval.citation_harness import (
    GenerationRecord,
    GenerationWriter,
    build_metrics,
    prompt_hash,
    run_citation_eval,
    user_template_hash,
    write_generations,
)
# Il meccanismo di scrittura e' nato qui e Q-02 l'ha estratto in `src/eval/dump`,
# perche' serviva anche agli altri due harness. `GenerationWriter` resta come
# nome importabile da qui: e' quello che `scripts/eval_citations.py` usa.
from src.eval.dump import partial_path
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

    def test_reasoning_effort_changes_the_config_hash(self, golden, monkeypatch):
        """The C-07 arms differ only by this switch.

        Left out of the hash, "reasoning on" and "reasoning off" would be two
        different measurements recorded under the same name — and the name is
        what the dashboard groups by.
        """
        a, _ = _run(golden, ["Vero [1]."] * 3)
        monkeypatch.setattr(cfg, "REASONING_EFFORT", "high")
        b, _ = _run(golden, ["Vero [1]."] * 3)
        assert a.config_hash != b.config_hash

    def test_token_budget_changes_the_config_hash(self, golden, monkeypatch):
        """C-07 raises it to 2048 for both arms, because at 1024 the reasoning
        arm truncates half its answers.  A budget that changes the output and
        not the name is the same defect as a prompt that does."""
        a, _ = _run(golden, ["Vero [1]."] * 3)
        monkeypatch.setattr(cfg, "MAX_NEW_TOKENS", 2048)
        b, _ = _run(golden, ["Vero [1]."] * 3)
        assert a.config_hash != b.config_hash

    def test_user_template_is_part_of_the_prompt_identity(self, golden, monkeypatch):
        """Instructions live on both sides of the prompt.

        Runs 20260810_093723 and 20260810_102617 were recorded under the same
        `config_hash 2878488d` with `SYSTEM` identical and the contiguity
        reminder added to the *user* message in between.  Two prompts, one name.
        """
        before = user_template_hash()
        monkeypatch.setattr(
            citation_harness,
            "build_user_message",
            lambda q, chunks: f"different template: {q}",
        )
        assert user_template_hash() != before

    def test_config_records_the_user_template_hash(self, golden):
        """Its presence is what tells a hash computed under the new rule from
        one computed under the old: pre-C-07 result files do not carry it."""
        run, _ = _run(golden, ["Vero [1]."] * 3)
        assert run.config["user_template_hash"] == user_template_hash()


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
        assert m["latency_p50_s"] == 0.0 and m["completion_tokens_p50"] == 0.0


class TestCostMetrics:
    """What the switch costs, next to what it buys.

    C-07 compares reasoning on against off and C-06 compares model sizes; both
    trade latency for quality, so a result that reports only quality answers
    half the question.
    """

    @staticmethod
    def _rec(latency: float, tokens: int) -> GenerationRecord:
        return GenerationRecord(
            query_id="q", query_text="Q?", chunk_ids=["c"], n_chunks=2,
            answer="Vero [1].", compliant=True, abstained=False, markers=[1],
            finish_reason="stop", latency_s=latency, completion_tokens=tokens,
        )

    def _metrics(self, pairs):
        records = [self._rec(lat, tok) for lat, tok in pairs]
        reports = [check_format(r.answer, 2) for r in records]
        return build_metrics(summarize(reports), records)

    def test_median_ignores_a_single_outlier(self):
        """A mean over 200 queries moves further on one 300-second stall than on
        a real regression, which is why the reported figure is the median."""
        m = self._metrics([(1.0, 10), (1.0, 10), (1.0, 10), (1.0, 10), (300.0, 10)])
        assert m["latency_p50_s"] == 1.0

    def test_p90_reports_the_tail(self):
        m = self._metrics([(1.0, 10)] * 9 + [(50.0, 10)])
        assert m["latency_p90_s"] == 50.0

    def test_reported_values_are_measurements_that_happened(self):
        """Nearest-rank, not interpolated: 1.5 s is not a latency anybody saw."""
        m = self._metrics([(1.0, 10), (2.0, 20)])
        assert m["latency_p50_s"] in (1.0, 2.0)

    def test_completion_tokens_are_reported(self):
        """They include the reasoning tokens, which are generated and paid for
        while never reaching the answer — invisible everywhere but here."""
        m = self._metrics([(1.0, 140), (1.0, 998), (1.0, 998)])
        assert m["completion_tokens_p50"] == 998


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


class TestIncrementalWriting:
    """A run that dies partway must leave its generations behind.

    Before this, nothing reached disk until the last query: a failure at 190 of
    200 lost forty minutes of GPU and 190 usable answers — the exact material
    C-02 is built from.
    """

    def _rec(self, i):
        return GenerationRecord(
            query_id=f"q{i}", query_text="Q?", chunk_ids=["c"], n_chunks=1,
            answer=f"Vero [1]. #{i}", compliant=True, abstained=False, markers=[1],
        )

    def test_records_are_on_disk_before_the_run_ends(self, tmp_path):
        w = GenerationWriter(tmp_path / "g.jsonl", "SYS")
        w.append(self._rec(1))
        w.append(self._rec(2))
        lines = w.tmp.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_partial_name_until_finished(self, tmp_path):
        p = tmp_path / "g.jsonl"
        w = GenerationWriter(p, "SYS")
        w.append(self._rec(1))
        # The final name must not exist yet: its existence is the proof that the
        # run reached the end, and rescore_citations.py relies on that.
        assert not p.exists()
        assert w.tmp.name.endswith(".jsonl.partial")

    def test_finish_promotes_to_the_final_name(self, tmp_path):
        p = tmp_path / "g.jsonl"
        w = GenerationWriter(p, "SYS")
        w.append(self._rec(1))
        assert w.finish() == p
        assert p.exists() and not w.tmp.exists()

    def test_prompt_written_up_front_not_at_the_end(self, tmp_path):
        # A run that dies still leaves its generations interpretable.
        GenerationWriter(tmp_path / "g.jsonl", "SYSTEM TEXT")
        assert (tmp_path / "g.prompt.txt").read_text(encoding="utf-8") == "SYSTEM TEXT"

    def test_partial_path_helper(self, tmp_path):
        assert partial_path(tmp_path / "g.jsonl").name == "g.jsonl.partial"

    def test_harness_appends_as_it_goes(self, golden, tmp_path):
        w = GenerationWriter(tmp_path / "g.jsonl", "SYS")
        _run(golden, ["Vero [1]."] * 3, writer=w)
        assert len(w.tmp.read_text(encoding="utf-8").strip().splitlines()) == 3

    def test_harness_works_without_a_writer(self, golden):
        run, records = _run(golden, ["Vero [1]."] * 3)
        assert len(records) == 3 and run.metrics["format_compliance"] == 1.0

    def test_write_generations_still_produces_a_finished_file(self, tmp_path):
        p = tmp_path / "g.jsonl"
        write_generations(p, [self._rec(1), self._rec(2)], "SYS")
        assert p.exists() and not partial_path(p).exists()
        assert len(p.read_text(encoding="utf-8").strip().splitlines()) == 2
