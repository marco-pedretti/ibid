# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

`ROADMAP.md` is the executable source of truth: it defines the repo structure, data contracts, and a phased task list (T-xx, I-xx, E-xx, R-xx, C-xx, U-xx, X-xx) with acceptance criteria. Before writing code, check `ROADMAP.md` for the task ID being implemented and its acceptance criterion — each task is meant to ship with the test that verifies it.

**Current task completion state is tracked in [`docs/progress.md`](docs/progress.md)**, not in this file or in `ROADMAP.md` — check it before assuming what's already implemented.

`ROADMAP.md` and `STACK.md` are written in Italian and are binding for implementation decisions (data schemas, phase gates, dependency choices). `README.md` is the (currently one-line) public-facing description.

## What this project is

`ibid` is a RAG testbed with sentence-level verified citations: every generated claim is traced back to its source chunk, evaluated quantitatively on public benchmark datasets using small local LLMs (Gemma 4 E2B/E4B/12B/26B-MoE via llama.cpp, Vulkan backend on an AMD RX 6750 XT). The name comes from Latin *ibidem* ("in the same place") — the bibliographic abbreviation for citing the same source again.

Three claims the project exists to demonstrate (see ROADMAP.md §0):
1. Sentence-level verified citation precision is measurable, and unverified small models get it systematically wrong.
2. Automatic pipeline routing by document genre beats one generic pipeline — the gain must be reported **per dataset**, never aggregated.
3. With good retrieval, model size matters less than expected (hypothesis to test).

## Architecture (planned — see ROADMAP.md §13 / STACK.md)

```
src/
├── datasets/     # HuggingFace loading, normalization to the Chunk schema
├── profiling/    # document profiler, doc_genre assignment (drives routing)
├── ingestion/    # 3 chunking pipelines: continuous_text, structured_hierarchical, table_heavy
├── index/        # embedding (BGE-M3), upsert to Qdrant (one collection per dataset)
├── retrieval/    # hybrid dense+sparse, RRF fusion, reranking, query rewrite, genre-based routing
├── generation/    # prompting, citation marker parsing/repair, entailment check, abstention
├── api/          # FastAPI, SSE streaming
└── config.py     # all retrieval parameters live here — an ablation is a loop over config, not a code change
eval/
├── contamination/  # pre-implementation contamination-check outputs (already collected)
├── golden/          # queries + qrels per dataset, including unanswerable queries
├── metrics/
└── results/         # one EvalRun JSON per run, tagged with git commit hash
dashboard/        # internal Streamlit app for debugging/comparing retrieval configs (separate from demo UI)
ui/               # React + Vite demo frontend (SSE streaming, PNG page + bbox overlay for citations)
```

Key architectural decisions (do not relitigate without updating STACK.md):
- **No RAG orchestration framework** (no LangChain/LlamaIndex) — the pipeline itself is the deliverable.
- **No message queue / Celery** — ingestion is a one-shot job.
- LLM inference is always reached through an OpenAI-compatible endpoint via `LLM_BASE_URL`, never called directly — keeps the repo runnable on any machine.
- Chunking is hand-written per document genre (~150 lines), not a generic text splitter.
- Two separate UIs: internal Streamlit dashboard (eval/debug) vs. demo frontend — not merged.

## Data contracts (ROADMAP.md §3 — binding, do not rename/add fields without updating ROADMAP.md)

- **`Chunk`**: requires `dataset_id` on every record. Metrics are always reported per `dataset_id`; never averaged across document genres.
- **Citation format is enforced, not suggested**: only contiguous `[n][m]` markers are accepted (e.g. `Il valore massimo è 400ms [2][3].`). Forms like `[2, 3]`, `[2 e 3]`, `[2]-[3]` are rejected; known variants get normalized by the parser, and markers pointing to chunks not in context are discarded.
- **`EvalRun`**: every evaluation run records `git_commit`, `config_hash`, `dataset_id`, `model`, `quantization`, `context_window`, `temperature`, `pipeline_mode` (`generic` | `routed`).
- Evaluation temperature is always **0**, context window **32768**, and both must be annotated in the result.

## Licensing constraints (STACK.md — critical)

The project is **MIT licensed**; no copyleft (GPL/AGPL/LGPL-static) dependency may enter the tree.

- **Never add PyMuPDF** — it's AGPL-3.0 and its network clause would force the whole project (including Docker images) to relicense as AGPL. Use `pypdfium2` (rendering/bbox) and `pdfplumber` (MIT, tables/layout) instead.
- Any new dependency must have its license checked and recorded in the license table in `STACK.md` before being introduced.

## Git workflow (mandatory — do not skip)

**Every ROADMAP task gets its own branch before touching any file.**

```
git checkout -b <task-id>          # e.g. R-01, C-02
# ... implement ...
git commit -m "<task-id>: ..."
git checkout main
git merge --no-ff <task-id>        # preserves branch commits, creates a merge commit
git branch -d <task-id>            # always delete the branch after merging
```

Rules:
- `--no-ff` is mandatory — never fast-forward, never squash. The merge commit marks the task boundary on main.
- Delete the branch immediately after merging with `git branch -d`.
- Small fixes or enhancements to an already-merged task (not a new ROADMAP task) may go directly to main without a branch.

Every commit must include:
```
Co-Authored-By: Elia Dallanoce <eliadallanoce@gmail.com>
```

**Never add Claude as co-author.** Human authors only: Marco (marcopedretti3@gmail.com) and Elia (eliadallanoce@gmail.com).

This rule has been violated on E-01 and E-03 (committed directly to main). It must be followed from every task forward without exception.

## Working rules from ROADMAP.md §12 (apply to coding-agent work in this repo)

- Never measure two changes at once — one change, then a measurement, before the next change.
- No metric without `dataset_id`; never aggregate across document genres.
- The abstention threshold and the citation format are decided in code, never left to the model.
- Don't declare an improvement without comparing it against the noise baseline (task E-07).
