"""Generation evaluation harness for baselines E-04 (permissive) and E-05 (strict).

Orchestrates: load golden queries -> generate without context -> judge ->
compute rates -> EvalRun.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import src.config as cfg
from src.datasets.golden import GoldenQuery
from src.datasets.schema import EvalRun
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

_PIPELINE_MODES: dict[str, str] = {
    "A": "baseline_a",
    "B": "baseline_b",
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _config_hash(baseline: str, model: str) -> str:
    params = {
        "baseline": baseline,
        "model": model,
        "temperature": cfg.TEMPERATURE,
    }
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def _load_golden(path: Path) -> list[GoldenQuery]:
    queries: list[GoldenQuery] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(GoldenQuery.model_validate_json(line))
    return queries


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
) -> EvalRun:
    """Run no-context LLM baseline evaluation and return an EvalRun.

    Args:
        dataset_id: "open_ragbench" | "ledger"
        golden_path: path to eval/golden/{dataset_id}.jsonl
        baseline: "A" (permissive) | "B" (strict)
        limit: evaluate only first N answerable queries that have a reference answer
        model: LLM model name (default: cfg.LLM_MODEL)

    Returns:
        EvalRun with metrics: abstention_rate, correct_rate, wrong_rate.
        The three rates always sum to 1.0.
    """
    if baseline not in _PROMPTS:
        raise ValueError(f"Unknown baseline {baseline!r}. Valid: {list(_PROMPTS)}")
    if model is None:
        model = cfg.LLM_MODEL

    system_prompt = _PROMPTS[baseline]

    all_queries = _load_golden(golden_path)
    candidates = [
        q
        for q in all_queries
        if q.answerable and q.dataset_id == dataset_id and q.reference_answer
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
        )

        if is_abstained(response):
            counts["abstained"] += 1
            continue

        verdict = judge_answer(
            query=q.query_text,
            response=response,
            reference=q.reference_answer,
            base_url=cfg.LLM_BASE_URL,
            model=model,
        )
        counts[verdict if verdict in counts else "wrong"] += 1

    metrics: dict[str, float] = {
        "abstention_rate": counts["abstained"] / n if n else 0.0,
        "correct_rate": counts["correct"] / n if n else 0.0,
        "wrong_rate": counts["wrong"] / n if n else 0.0,
    }

    return EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=_git_commit(),
        config_hash=_config_hash(baseline, model),
        dataset_id=dataset_id,
        model=model,
        quantization=cfg.LLM_QUANTIZATION,
        context_window=cfg.CONTEXT_WINDOW,
        temperature=cfg.TEMPERATURE,
        reasoning_enabled=False,
        pipeline_mode=_PIPELINE_MODES[baseline],
        metrics=metrics,
    )
