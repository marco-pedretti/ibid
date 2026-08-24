"""Generation evaluation harness for baselines E-04 (permissive) and E-05 (strict).

Orchestrates: load golden queries -> generate without context -> judge ->
compute rates -> EvalRun.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import src.config as cfg
from src.eval.dump import JsonlWriter
from src.eval.run_config import finestra_registrata, make_eval_run
from src.datasets.schema import EvalRun
from src.eval.provenance import git_commit, load_golden
from src.generation.baseline_prompts import (
    ABSTENTION_PHRASES,
    BASELINE_A_SYSTEM,
    BASELINE_B_SYSTEM,
)
from src.generation.chat import generate
from src.generation.judge import judge_answer

_PROMPTS: dict[str, str] = {
    "A": BASELINE_A_SYSTEM,
    "B": BASELINE_B_SYSTEM,
}

#: ROADMAP §3.3 defines `pipeline_mode` as the binary routing axis, and §3 says
#: `config` exists precisely so it does not become a free-text label.  These
#: baselines do no retrieval at all, so they are not routed; which baseline they
#: are lives in `config["baseline"]`.
#:
#: This module wrote "baseline_a" / "baseline_b" into that field from E-04 until
#: 2026-08-11, and the contract test on disk never caught it because E-04/E-05
#: had never actually been run — no result file existed to check.
_ROUTING_AXIS = "generic"


@dataclass
class BaselineRecord:
    """Cosa il modello ha risposto a una query, e come e' stata giudicata (Q-02).

    Senza questo file il taglio dal 45% al 17% di E-04/E-05 resta **un'inferenza
    dai totali**: due percentuali, e nessun modo di sapere se le risposte
    corrette del baseline permissivo siano *le stesse* di quelle del severo. Con
    i record per query diventa un test appaiato.

    E ha gia' morso una volta: durante E-04/E-05 la diagnosi di tre difetti ha
    richiesto di **rigenerare a mano le risposte**, perche' quelle delle run non
    esistevano piu'. L'harness delle citazioni aveva risolto lo stesso problema
    in C-01, e quella decisione ha poi permesso a C-02 e C-03 di lavorare senza
    rigenerare niente.

    `response` e' salvata verbatim: e' il testo che il giudice ha letto, e un
    verdetto senza la risposta che lo ha prodotto non si puo' rivedere.
    """

    query_id: str
    query_text: str
    response: str
    verdict: str
    abstained: bool
    reference_answer: str
    #: `False` quando il giudice non e' stato interpellato: sull'insieme non
    #: rispondibile non c'e' niente contro cui giudicare, e `wrong` li' e' una
    #: conseguenza logica e non un parere. Distinguerli evita di leggere come
    #: giudizi cose che non lo sono.
    judged: bool


def _config_hash(baseline: str, model: str, queries: str = "answerable") -> str:
    """Identity of the configuration under test.

    `queries` enters the hash only when it is not the default, so the four
    E-04/E-05 runs of 2026-08-11 keep the identity they were recorded with.
    Adding it unconditionally would give the same measurement two names
    depending on when it was taken, which is the opposite of what a config hash
    is for — while leaving it out entirely would give two different measurements
    the same name, which is worse.
    """
    params = {
        "baseline": baseline,
        "model": model,
        "temperature": cfg.TEMPERATURE,
    }
    if queries != "answerable":
        params["queries"] = queries
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def is_abstained(response: str) -> bool:
    """Return True if the response contains an explicit abstention phrase."""
    lower = response.lower()
    return any(phrase in lower for phrase in ABSTENTION_PHRASES)


def run_generation_eval(
    dataset_id: str,
    golden_path: Path,
    baseline: str = "A",
    limit: int | None = None,
    model: str | None = None,
    queries: str = "answerable",
    writer: JsonlWriter | None = None,
) -> EvalRun:
    """Run no-context LLM baseline evaluation and return an EvalRun.

    Args:
        dataset_id: "open_ragbench" | "ledger"
        golden_path: path to eval/golden/{dataset_id}.jsonl
        baseline: "A" (permissive) | "B" (strict)
        limit: evaluate only first N queries
        model: LLM model name (default: cfg.LLM_MODEL)
        queries: "answerable" — the E-04/E-05 criteria, judged against the
            reference answer.  "unanswerable" — the E-02 set, which the Fase 4
            gate compares against the full system.

    Returns:
        EvalRun with metrics: abstention_rate, correct_rate, wrong_rate, which
        always sum to 1.0.

    **On the unanswerable set there is nothing to judge.**  Those queries have no
    reference answer, and without retrieval the model has no context either — so
    any answer at all is invented by construction, and `wrong_rate` is exactly
    `1 - abstention_rate` without an LLM judge being consulted.  Calling the
    judge there would ask a model to compare a response against a reference that
    does not exist, and it would return a verdict anyway.
    """
    if baseline not in _PROMPTS:
        raise ValueError(f"Unknown baseline {baseline!r}. Valid: {list(_PROMPTS)}")
    if model is None:
        model = cfg.LLM_MODEL

    system_prompt = _PROMPTS[baseline]

    # See citation_harness.run_citation_eval: captured before the run.
    commit = git_commit()

    if queries not in ("answerable", "unanswerable"):
        raise ValueError(f"Unknown queries {queries!r}")

    all_queries = load_golden(golden_path)
    if queries == "answerable":
        candidates = [
            q
            for q in all_queries
            if q.answerable and q.dataset_id == dataset_id and q.reference_answer
        ]
    else:
        candidates = [
            q for q in all_queries if not q.answerable and q.dataset_id == dataset_id
        ]
    if limit is not None:
        candidates = candidates[:limit]

    n = len(candidates)
    counts = {"abstained": 0, "correct": 0, "wrong": 0}

    for i, q in enumerate(candidates, 1):
        if i == 1 or i % 10 == 0:
            print(f"  [{i}/{n}] {q.query_id}", flush=True)

        response = generate(
            base_url=cfg.LLM_BASE_URL,
            model=model,
            system=system_prompt,
            user=q.query_text,
            temperature=cfg.TEMPERATURE,
            max_tokens=cfg.MAX_NEW_TOKENS,
            # The system under test follows the config. Until now this argument
            # was omitted and the default silently pinned it to "none", so the
            # baselines could not have been run under C-07's condition even on
            # purpose. The judge below deliberately does not follow it.
            reasoning_effort=cfg.REASONING_EFFORT,
        )

        abstained = is_abstained(response)
        if abstained:
            counts["abstained"] += 1
            verdict = "abstained"
        elif queries == "unanswerable":
            # No reference to judge against, and no context the answer could have
            # come from: whatever this is, the model made it up.
            counts["wrong"] += 1
            verdict = "wrong"
        else:
            verdict = judge_answer(
                query=q.query_text,
                response=response,
                reference=q.reference_answer,
                base_url=cfg.LLM_BASE_URL,
                model=model,
            )
            verdict = verdict if verdict in counts else "wrong"
            counts[verdict] += 1

        if writer is not None:
            writer.append(BaselineRecord(
                query_id=q.query_id,
                query_text=q.query_text,
                response=response,
                verdict=verdict,
                abstained=abstained,
                reference_answer=q.reference_answer or "",
                judged=not abstained and queries == "answerable",
            ))

    metrics: dict[str, float] = {
        "abstention_rate": counts["abstained"] / n if n else 0.0,
        "correct_rate": counts["correct"] / n if n else 0.0,
        "wrong_rate": counts["wrong"] / n if n else 0.0,
    }

    return make_eval_run(
        git_commit=commit,
        config_hash=_config_hash(baseline, model, queries),
        dataset_id=dataset_id,
        llm=model,
        context_window=finestra_registrata(model),
        pipeline_mode=_ROUTING_AXIS,
        config={
            "harness": "generation_baseline",
            "baseline": baseline,
            "queries": queries,
            "n_queries": n,
            "llm_model": model,
            "judge_used": queries == "answerable",
        },
        metrics=metrics,
    )
