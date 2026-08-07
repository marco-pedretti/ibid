#!/usr/bin/env python3
"""One-shot backfill of `EvalRun.config` on result files written before it existed.

Runs produced up to 2026-08-06 encoded their retrieval flags inside the
`pipeline_mode` string ("generic_filtered_text", "routed_docagg", ...), which
collided with the ROADMAP §3.3 contract where `pipeline_mode` is the binary
routing axis.  This script splits that string back into structured fields.

What it does NOT touch:
  - `metrics`     — the measurements themselves are unchanged
  - `config_hash` — recomputing it would break comparability with runs already
                    reported in docs/progress.md
The original label is preserved in `config["legacy_pipeline_mode"]`.

`top_k` cannot be recovered from the file (it is only inside the md5) — every
legacy run used the default, so cfg.TOP_K is assumed and the entry is flagged
with `config["_migrated"] = True`.

Usage:
    python scripts/migrate_eval_results.py --dry-run
    python scripts/migrate_eval_results.py
    python scripts/migrate_eval_results.py --rename   # also rename to the new scheme
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import src.config as cfg
from src.eval.run_config import config_slug

RESULTS_DIR = ROOT / "eval" / "results"

#: legacy pipeline_mode base -> (routing axis, retrieval_mode)
_BASE = {
    "generic": ("generic", "dense"),
    "routed": ("routed", "dense"),
    "baseline_c": ("generic", "sparse"),
    "hybrid_rrf": ("generic", "hybrid"),
}

#: legacy suffix -> config key it sets
_SUFFIX_FLAGS = {
    "reranked": "rerank",
    "rewritten": "query_rewrite",
    "docagg": "doc_aggregate",
}


def parse_legacy(pipeline_mode: str, dataset_id: str) -> tuple[str, dict]:
    """Split a legacy pipeline_mode label into (routing_axis, config dict)."""
    # Longest base prefix wins: "baseline_c" must not be read as "baseline" + "c".
    base_key = next(
        (b for b in sorted(_BASE, key=len, reverse=True)
         if pipeline_mode == b or pipeline_mode.startswith(b + "_")),
        None,
    )
    if base_key is None:
        # Generation baselines (baseline_a / baseline_b) and anything unknown:
        # keep the label, record nothing we cannot prove.
        return pipeline_mode, {"legacy_pipeline_mode": pipeline_mode, "_migrated": True}

    axis, retrieval_mode = _BASE[base_key]
    rest = pipeline_mode[len(base_key):].lstrip("_")

    cfg_dict = {
        "retrieval_mode": retrieval_mode,
        "top_k": cfg.TOP_K,
        "rerank": False,
        "query_rewrite": False,
        "filter_content_type": None,
        "doc_aggregate": False,
        "collection": f"{dataset_id}_routed" if axis == "routed" else dataset_id,
        "embedding_model": cfg.EMBEDDING_MODEL,
        "reranker_model": None,
        "query_rewrite_model": None,
        "legacy_pipeline_mode": pipeline_mode,
        "_migrated": True,
    }

    if rest:
        # "filtered_text" carries its value in the following token.
        tokens = rest.split("_")
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok == "filtered" and i + 1 < len(tokens):
                cfg_dict["filter_content_type"] = tokens[i + 1]
                i += 2
                continue
            if tok in _SUFFIX_FLAGS:
                cfg_dict[_SUFFIX_FLAGS[tok]] = True
            i += 1

    if cfg_dict["rerank"]:
        cfg_dict["reranker_model"] = cfg.RERANKER_MODEL
    if cfg_dict["query_rewrite"]:
        cfg_dict["query_rewrite_model"] = cfg.QUERY_REWRITE_MODEL or cfg.LLM_MODEL

    return axis, cfg_dict


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill EvalRun.config on legacy results")
    ap.add_argument("--dry-run", action="store_true", help="Print changes, write nothing")
    ap.add_argument("--rename", action="store_true",
                    help="Also rename files to {ts}_{dataset}_{mode}_{slug}.json")
    args = ap.parse_args()

    n_done = n_skipped = 0
    for path in sorted(RESULTS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "metrics" not in data:
            continue  # noise-floor file, different schema
        if data.get("config"):
            n_skipped += 1
            continue

        old_mode = data["pipeline_mode"]
        axis, cfg_dict = parse_legacy(old_mode, data["dataset_id"])
        data["pipeline_mode"] = axis
        data["config"] = cfg_dict

        target = path
        if args.rename:
            ts = path.name.split("_")[0] + "_" + path.name.split("_")[1]
            target = path.with_name(
                f"{ts}_{data['dataset_id']}_{axis}_{config_slug(cfg_dict)}.json"
            )

        print(f"  {path.name}")
        print(f"    pipeline_mode: {old_mode!r} -> {axis!r}  config: {config_slug(cfg_dict)}")
        if target != path:
            print(f"    rename -> {target.name}")

        if not args.dry_run:
            target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if target != path:
                path.unlink()
        n_done += 1

    verb = "would migrate" if args.dry_run else "migrated"
    print(f"\n{verb} {n_done} file(s); {n_skipped} already had config.")


if __name__ == "__main__":
    main()
