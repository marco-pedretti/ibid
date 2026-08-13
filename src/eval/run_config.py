"""Structured description of a retrieval evaluation configuration.

Why this exists: before this module, every retrieval flag (rerank, query rewrite,
metadata filter, doc aggregation, collection override) was squashed into the
`EvalRun.pipeline_mode` string — producing values like "generic_filtered_text"
and "routed_docagg".  That broke the ROADMAP §3.3 contract, which defines
`pipeline_mode` as the binary routing axis ("generic" | "routed"), and made it
impossible to answer "show me every routed run" or "which two runs differ by
exactly one flag" (ROADMAP §14: never measure two changes at once).

`build_config()` returns the flags as data.  `EvalRun.config` carries it.

`config_hash` is deliberately NOT computed from this dict — see `_config_hash`
in `harness.py`.  Changing the hash function would make already-measured runs
non-comparable, which ROADMAP §3 forbids after Fase 2.
"""

from __future__ import annotations

from typing import Any

import src.config as cfg

#: Keys that are always present in a config dict, in display order.
CONFIG_KEYS: tuple[str, ...] = (
    "retrieval_mode",
    "top_k",
    "eval_depth",
    "rerank",
    "query_rewrite",
    "filter_content_type",
    "doc_aggregate",
    "collection",
    "n_queries",
)


def build_config(
    *,
    top_k: int,
    retrieval_mode: str,
    rerank: bool = False,
    query_rewrite: bool = False,
    filter_content_type: str | None = None,
    doc_aggregate: bool = False,
    collection: str,
    eval_depth: int | None = None,
    n_queries: int | None = None,
) -> dict[str, Any]:
    """Build the descriptive config dict stored in EvalRun.config.

    Every key is always present (unlike the hash input, which omits inactive
    flags) so the dashboard can render runs as a dense flag matrix.

    `n_queries` is the count actually evaluated, not the requested `--limit`.
    Runs before 2026-08-07 recorded neither, which made a 50-query smoke test
    indistinguishable from a 3045-query full run in the result file — the R-07
    numbers came from smoke tests and nothing said so.
    """
    return {
        "retrieval_mode": retrieval_mode,
        "top_k": top_k,
        "eval_depth": eval_depth,
        "rerank": rerank,
        "query_rewrite": query_rewrite,
        "filter_content_type": filter_content_type,
        "doc_aggregate": doc_aggregate,
        "collection": collection,
        "n_queries": n_queries,
        "embedding_model": cfg.EMBEDDING_MODEL,
        # R-11: sempre presenti, anche spenti. Nell'hash compaiono solo se
        # accesi (per non spostare le identita' gia' misurate), ma qui servono
        # sempre: un run che non dice come ha cercato non e' interpretabile, e
        # R-10 ha mostrato che su questo corpus la differenza vale 8 punti.
        "search_exact": cfg.SEARCH_EXACT,
        "hnsw_ef": cfg.HNSW_EF,
        "reranker_model": cfg.RERANKER_MODEL if rerank else None,
        "query_rewrite_model": (
            (cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL) if query_rewrite else None
        ),
    }


def config_slug(config: dict[str, Any]) -> str:
    """Compact human-readable label for a config, e.g. "hybrid-rerank-docagg".

    Used in result filenames and dashboard legends.  Only active flags appear,
    so the baseline config collapses to just its retrieval mode ("dense").
    """
    if not config:
        return "unknown"
    parts = [str(config.get("retrieval_mode", "dense"))]
    if config.get("query_rewrite"):
        parts.append("rewrite")
    if config.get("rerank"):
        parts.append("rerank")
    if config.get("filter_content_type"):
        parts.append(f"filter_{config['filter_content_type']}")
    if config.get("doc_aggregate"):
        parts.append("docagg")
    return "-".join(parts)


def differing_keys(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Config keys whose values differ between two runs.

    The dashboard uses this to enforce ROADMAP §14: a delta between two runs is
    only attributable to a single change when exactly one key differs.
    """
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))
