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
from dataclasses import asdict, dataclass, field
from pathlib import Path

import src.config as cfg
from src.datasets.schema import Chunk, EvalRun
from src.eval.dump import JsonlWriter, write_all
from src.eval.provenance import git_commit, load_golden
from src.retrieval.backends import RETRIEVERS
from src.eval.run_config import build_config, finestra_registrata, make_eval_run
from src.generation.chat import generate_detailed
from src.generation.citation_format import ComplianceSummary, check_format, summarize
from src.generation.prompt import SYSTEM, build_user_message
from src.index import embed
from src.index.store import chunk_from_payload, get_client


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


def prompt_hash(system_prompt: str) -> str:
    """Identity of the prompt under test.

    The prompt is what C-01 measures, so it belongs in the run's configuration.
    Without it, rewording the prompt and re-running would produce two results
    with the same `config_hash` — two different measurements claiming to be the
    same configuration, which is exactly what the hash exists to prevent.

    It covers `SYSTEM` **only**, which is half the prompt.  See
    `user_template_hash` for the half it missed.
    """
    return hashlib.md5(system_prompt.encode("utf-8")).hexdigest()[:8]


#: Fixed input for `user_template_hash`.  Its content is irrelevant and must
#: never change: it is held constant precisely so that any difference in the
#: rendered output comes from the template and nothing else.
_TEMPLATE_PROBE = Chunk(
    chunk_id="probe",
    dataset_id="probe",
    doc_id="probe",
    doc_genre="",
    pipeline="",
    section_path="",
    page=0,
    bbox=None,
    content_type="text",
    text="probe",
    source_uri="probe",
)


def user_template_hash() -> str:
    """Identity of the *user* message template.

    Instructions live on both sides of the prompt.  On 2026-08-10 the contiguity
    rule was added to `build_user_message` — a change to the text the model
    reads, with `SYSTEM` untouched — and runs `093723` and `102617` were recorded
    under the same `config_hash 2878488d` with two different prompts.  That is
    the exact failure `prompt_hash` was written to prevent, one level down.

    Hashing the *rendered* message rather than the function's source keeps
    docstring edits out of the identity: what matters is what the model sees.

    Runs predating this function carry no `user_template_hash` in their config,
    and their `config_hash` was computed under the old rule.  They are left as
    recorded — a hash is a name for a measurement, and renaming measurements
    after the fact is worse than admitting two of them were named ambiguously.
    The field's presence is what tells the two rules apart.
    """
    rendered = build_user_message("probe", [_TEMPLATE_PROBE])
    return hashlib.md5(rendered.encode("utf-8")).hexdigest()[:8]


def _config_hash(
    top_k: int,
    retrieval_mode: str,
    collection: str,
    model: str,
    system_prompt: str,
) -> str:
    """Everything that changes the generation, and nothing that does not.

    `reasoning_effort` and `max_new_tokens` are here because C-07 varies them:
    its two arms are identical in every other parameter, so without these the
    switch being measured would have no effect on the name of the result.

    **`n_queries` is deliberately NOT here, and adding it would be a mistake.**
    The number of queries is *precision*, not configuration: the same setup
    measured over 100 and over 200 queries is one configuration sampled twice.
    C-06 depends on that — its consistency check works precisely because E4B at
    200 queries (C-01) and at 100 (this run) share an identity and can be
    compared as the same system, which is how three days of intervening changes
    were ruled out. Putting `n` in the hash would have made those two runs
    unrelatable.

    The problem `n` seemed to solve is real but lives elsewhere: a three-query
    calibration was written into `eval/results/` under the same name as the real
    measurement. The fix for that is `--no-write` on the CLI — a throwaway run
    should not be archived at all — not a name that makes every sample size a
    different configuration.
    """
    params = {
        "harness": "citation",
        "embedding_model": cfg.EMBEDDING_MODEL,
        "top_k": top_k,
        "retrieval_mode": retrieval_mode,
        "collection": collection,
        "llm_model": model,
        "temperature": cfg.TEMPERATURE,
        "prompt_hash": prompt_hash(system_prompt),
        "user_template_hash": user_template_hash(),
        "reasoning_effort": cfg.REASONING_EFFORT,
        "max_new_tokens": cfg.MAX_NEW_TOKENS,
    }
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]


def _percentile(sorted_values: list[float], q: float) -> float:
    """Nearest-rank percentile of an already-sorted list; 0.0 when empty.

    Nearest-rank rather than interpolated: every value it returns is a
    measurement that actually happened, which is what a latency report should
    contain.
    """
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, int(q * len(sorted_values)))
    return float(sorted_values[idx])


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

    **Cost is a metric, not a footnote.**  C-07 asks what extended reasoning is
    worth, and C-06 asks the same of model size; neither question can be
    answered by quality alone, because both switches buy quality with time.  The
    median is reported rather than the mean: a single 300-second outlier moves a
    mean over 200 queries by more than a real regression would.  `p90` is there
    because the tail is what a user waits through.

    `completion_tokens` counts the reasoning tokens too — they are generated and
    paid for even though they never reach `message.content`, which is precisely
    what makes them visible here and invisible in the answer.
    """
    n = len(records)
    latencies = sorted(r.latency_s for r in records)
    tokens = sorted(r.completion_tokens for r in records)
    metrics: dict[str, float] = {
        "format_compliance": summary.rate,
        "format_compliance_lower95": summary.rate_lower95,
        "abstention_rate": summary.n_abstained / summary.n_total if summary.n_total else 0.0,
        "truncation_rate": sum(1 for r in records if r.finish_reason == "length") / n if n else 0.0,
        "empty_answer_rate": sum(1 for r in records if not r.answer) / n if n else 0.0,
        "markers_per_answer": summary.markers_per_answer,
        "latency_p50_s": _percentile(latencies, 0.50),
        "latency_p90_s": _percentile(latencies, 0.90),
        "completion_tokens_p50": _percentile(tokens, 0.50),
    }
    for kind, rate in summary.kind_rates.items():
        metrics[f"violation_{kind}"] = rate
    return metrics


#: Il meccanismo (append incrementale, suffisso `.partial`, rinomina solo alla
#: fine) e' nato qui per C-01 ed e' stato estratto in `src/eval/dump.py` da Q-02,
#: che ne aveva bisogno per gli altri due harness.  Questi nomi restano perche'
#: sono quelli che C-02 e `rescore_citations.py` importano.
GenerationWriter = JsonlWriter


def write_generations(path: Path, records: list[GenerationRecord], system_prompt: str) -> None:
    """Write generations in one shot — used by tests and by re-scoring tools."""
    write_all(path, records, sidecar=system_prompt)


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
    writer: GenerationWriter | None = None,
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
        writer: when given, each generation is appended to disk as it is
            produced, so a run that dies partway still leaves its answers.

    Returns:
        (EvalRun, records).  The caller persists both — the records are C-02's
        input and are not reconstructable from the metrics.
    """
    if top_k is None:
        top_k = cfg.TOP_K
    if model is None:
        model = cfg.LLM_MODEL
    qdrant_collection = collection or dataset_id

    # Captured before anything runs, not when the EvalRun is built: the code
    # that produces the answers is the code loaded at the start, and a commit
    # made during the 40 minutes in between would otherwise be recorded as the
    # one that generated them.
    commit = git_commit()

    all_queries = load_golden(golden_path)
    answerable = [q for q in all_queries if q.answerable and q.dataset_id == dataset_id]
    if limit is not None:
        answerable = answerable[:limit]
    n = len(answerable)
    if n == 0:
        raise ValueError(f"No answerable queries for dataset {dataset_id!r}")

    client = get_client(cfg.QDRANT_URL)
    # Come per l'harness di retrieval: una configurazione per tutta la run,
    # costruita dai flag e mai piu' toccata.
    config = cfg.RequestConfig.from_defaults(
        top_k=top_k, retrieval_mode=retrieval_mode, model=model
    )
    retrieve = RETRIEVERS[retrieval_mode]
    all_candidates = retrieve(
        client, qdrant_collection, [q.query_text for q in answerable], top_k, None, config
    )

    # **Il recupero e' finito qui, e la sessione ONNX no.** Da questo punto la
    # run parla solo col modello via HTTP, ma l'embedder resterebbe in memoria
    # per tutta la generazione -- su una scheda da 12 GB sono i ~2,3 GB che
    # decidono se il 12B ci sta o se il driver ne sposta quattro nella memoria
    # condivisa. Misurato il 2026-08-22: con l'embedder in memoria il decode del
    # 12B sta a 4,7 tok/s contro i 33 a scheda libera, perche' il motore di
    # copia satura e quelli di calcolo aspettano.
    #
    # Sta **dopo** il recupero e non dentro `encode()`: chi ha finito lo sa il
    # chiamante, e l'ingestione embedda a lotti per decine di minuti.
    embed.unload()

    print(f"  Generating {n} answers with {model}...", flush=True)
    records: list[GenerationRecord] = []
    reports = []
    t0 = time.time()
    for i, (query, cand) in enumerate(zip(answerable, all_candidates), 1):
        chunks = [chunk_from_payload(p) for p in cand.payloads[:top_k]]
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
        record = GenerationRecord(
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
        )
        records.append(record)
        if writer is not None:
            writer.append(record)
        if i == 1 or i % 10 == 0 or i == n:
            elapsed = time.time() - t0
            eta = (n - i) * elapsed / i
            print(f"  [{i}/{n}] elapsed {elapsed:.0f}s  ETA {eta:.0f}s", flush=True)

    summary = summarize(reports)

    run = make_eval_run(
        git_commit=commit,
        config_hash=_config_hash(top_k, retrieval_mode, qdrant_collection, model, system_prompt),
        dataset_id=dataset_id,
        llm=model,
        context_window=finestra_registrata(model),
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
            "user_template_hash": user_template_hash(),
            "reasoning_effort": cfg.REASONING_EFFORT,
            "max_new_tokens": cfg.MAX_NEW_TOKENS,
        },
        metrics=build_metrics(summary, records),
    )
    return run, records
