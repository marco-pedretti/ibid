"""Citation-format evaluation harness (C-01).

Retrieve → prompt → generate → check the raw answer against ROADMAP §3.2.

Different from `generation_harness.py` (E-04/E-05) in the one way that matters:
those baselines generate *without* context to see what the model invents, this
one generates *with* retrieved chunks to see whether the prompt obtains the
citation format.  Different question, so a different harness rather than a flag
on the old one.

Every run writes the generations to a JSONL alongside the EvalRun.  That file is
the deliverable for C-02 ("test sugli output malformati reali"): the parser has
to be built against outputs this model actually produced, not against variants
imagined while writing the parser.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import src.config as cfg
from src.datasets.schema import Chunk, EvalRun
from src.eval.provenance import git_commit, load_golden
from src.eval.retrieval_backends import RETRIEVERS
from src.eval.run_config import build_config
from src.generation.chat import generate_detailed
from src.generation.citation_format import ComplianceSummary, check_format, summarize
from src.generation.prompt import SYSTEM, build_user_message
from src.index.store import get_client


@dataclass
class GenerationRecord:
    """One query's raw generation and its verdict.

    `answer` is stored verbatim, never normalised — the malformed text is the
    point of the file.
    """

    query_id: str
    query_text: str
    chunk_ids: list[str]
    n_chunks: int
    answer: str
    compliant: bool
    abstained: bool
    markers: list[int]
    violations: list[dict] = field(default_factory=list)
    latency_s: float = 0.0
    finish_reason: str = ""
    completion_tokens: int = 0


def _payload_to_chunk(p: dict) -> Chunk:
    return Chunk(
        chunk_id=p["chunk_id"],
        dataset_id=p["dataset_id"],
        doc_id=p["doc_id"],
        doc_genre=p.get("doc_genre", ""),
        pipeline=p.get("pipeline", ""),
        section_path=p.get("section_path", ""),
        page=p.get("page", 0),
        bbox=None,
        content_type=p.get("content_type", "text"),
        text=p["text"],
        source_uri=p["source_uri"],
    )


def prompt_hash(system_prompt: str) -> str:
    """Identity of the prompt under test.

    The prompt is what C-01 measures, so it belongs in the run's configuration.
    Without it, rewording the prompt and re-running would produce two results
    with the same `config_hash` — two different measurements claiming to be the
    same configuration, which is exactly what the hash exists to prevent.
    """
    return hashlib.md5(system_prompt.encode("utf-8")).hexdigest()[:8]


def _config_hash(
    top_k: int,
    retrieval_mode: str,
    collection: str,
    model: str,
    system_prompt: str,
) -> str:
    params = {
        "harness": "citation",
        "embedding_model": cfg.EMBEDDING_MODEL,
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
        "collection": collection,
        "llm_model": model,
        "temperature": cfg.TEMPERATURE,
        "prompt_hash": prompt_hash(system_prompt),
    }
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def build_metrics(
    summary: ComplianceSummary, records: list[GenerationRecord]
) -> dict[str, float]:
    """Flatten a ComplianceSummary into the EvalRun metrics dict.

    `format_compliance` is the C-01 acceptance criterion (≥0.95).  It is
    reported next to `abstention_rate` because it is computed over non-abstained
    answers only and cannot be read without knowing how many those were.

    `truncation_rate` is reported for the same reason and is the more dangerous
    of the two: a cut-off answer has no citation because it never got to write
    one, and counting that as a format defect blames the prompt for a token
    budget.  In the first C-01 run it accounted for most of the failures.
    """
    n = len(records)
    metrics: dict[str, float] = {
        "format_compliance": summary.rate,
        "format_compliance_lower95": summary.rate_lower95,
        "abstention_rate": summary.n_abstained / summary.n_total if summary.n_total else 0.0,
        "truncation_rate": sum(1 for r in records if r.finish_reason == "length") / n if n else 0.0,
        "empty_answer_rate": sum(1 for r in records if not r.answer) / n if n else 0.0,
        "markers_per_answer": summary.markers_per_answer,
    }
    for kind, rate in summary.kind_rates.items():
        metrics[f"violation_{kind}"] = rate
    return metrics


def write_generations(path: Path, records: list[GenerationRecord], system_prompt: str) -> None:
    """Write the raw generations (JSONL) and the prompt that produced them.

    The prompt goes in a sibling `.prompt.txt` rather than into every record:
    the JSONL is read line by line by C-02, and repeating a 600-character system
    prompt on every line would bury the outputs it exists to show.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    path.with_suffix(".prompt.txt").write_text(system_prompt, encoding="utf-8")


def run_citation_eval(
    dataset_id: str,
    golden_path: Path,
    top_k: int | None = None,
    retrieval_mode: str = "dense",
    collection: str | None = None,
    limit: int | None = None,
    model: str | None = None,
    pipeline_mode: str = "generic",
    system_prompt: str = SYSTEM,
) -> tuple[EvalRun, list[GenerationRecord]]:
    """Generate cited answers over golden queries and measure format compliance.

    Args:
        dataset_id: "open_ragbench" | "ledger"
        golden_path: path to eval/golden/{dataset_id}.jsonl
        top_k: chunks put in context (default cfg.TOP_K).  This is serving
            depth, not evaluation depth: unlike the retrieval harness there is
            no metric cutoff to satisfy, and a deeper context would change the
            thing being measured.
        retrieval_mode: "dense" | "sparse" | "hybrid"
        collection: Qdrant collection (default: dataset_id)
        limit: first N answerable queries only
        model: LLM name (default cfg.LLM_MODEL)
        pipeline_mode: "generic" | "routed" — the ingestion axis, per §3.3
        system_prompt: the prompt under test; its hash enters config_hash

    Returns:
        (EvalRun, records).  The caller persists both — the records are C-02's
        input and are not reconstructable from the metrics.
    """
    if top_k is None:
        top_k = cfg.TOP_K
    if model is None:
        model = cfg.LLM_MODEL
    qdrant_collection = collection or dataset_id

    all_queries = load_golden(golden_path)
    answerable = [q for q in all_queries if q.answerable and q.dataset_id == dataset_id]
    if limit is not None:
        answerable = answerable[:limit]
    n = len(answerable)
    if n == 0:
        raise ValueError(f"No answerable queries for dataset {dataset_id!r}")

    client = get_client(cfg.QDRANT_URL)
    retrieve = RETRIEVERS[retrieval_mode]
    all_candidates = retrieve(
        client, qdrant_collection, [q.query_text for q in answerable], top_k, None
    )

    print(f"  Generating {n} answers with {model}...", flush=True)
    records: list[GenerationRecord] = []
    reports = []
    t0 = time.time()
    for i, (query, cand) in enumerate(zip(answerable, all_candidates), 1):
        chunks = [_payload_to_chunk(p) for p in cand.payloads[:top_k]]
        t_q = time.time()
        completion = generate_detailed(
            base_url=cfg.LLM_BASE_URL,
            model=model,
            system=system_prompt,
            user=build_user_message(query.query_text, chunks),
            temperature=cfg.TEMPERATURE,
            max_tokens=cfg.MAX_NEW_TOKENS,
            reasoning_effort=cfg.REASONING_EFFORT,
        )
        answer = completion.content
        report = check_format(answer, len(chunks))
        reports.append(report)
        records.append(GenerationRecord(
            query_id=query.query_id,
            query_text=query.query_text,
            chunk_ids=[c.chunk_id for c in chunks],
            n_chunks=len(chunks),
            answer=answer,
            compliant=report.compliant,
            abstained=report.abstained,
            markers=report.markers,
            violations=[asdict(v) for v in report.violations],
            latency_s=round(time.time() - t_q, 2),
            finish_reason=completion.finish_reason,
            completion_tokens=completion.completion_tokens,
        ))
        if i == 1 or i % 10 == 0 or i == n:
            elapsed = time.time() - t0
            eta = (n - i) * elapsed / i
            print(f"  [{i}/{n}] elapsed {elapsed:.0f}s  ETA {eta:.0f}s", flush=True)

    summary = summarize(reports)

    run = EvalRun(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        git_commit=git_commit(),
        config_hash=_config_hash(top_k, retrieval_mode, qdrant_collection, model, system_prompt),
        dataset_id=dataset_id,
        model=model,
        quantization=cfg.LLM_QUANTIZATION,
        context_window=cfg.CONTEXT_WINDOW,
        temperature=cfg.TEMPERATURE,
        # Derived, not asserted: before this was tied to config, every run
        # claimed reasoning was off while the model was reasoning through the
        # whole token budget.
        reasoning_enabled=cfg.REASONING_EFFORT not in ("none", "", None),
        pipeline_mode=pipeline_mode,
        config={
            **build_config(
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                collection=qdrant_collection,
                eval_depth=top_k,
                n_queries=n,
            ),
            "harness": "citation",
            "llm_model": model,
            "prompt_hash": prompt_hash(system_prompt),
            "reasoning_effort": cfg.REASONING_EFFORT,
            "max_new_tokens": cfg.MAX_NEW_TOKENS,
        },
        metrics=build_metrics(summary, records),
    )
    return run, records
