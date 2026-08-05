"""E-02: unanswerable query generation for abstention measurement.

Strategy (ROADMAP §6):
  - Cross-dataset: 25 queries from dataset A posed against corpus B (automatically unanswerable).
  - Handwritten: 10 per dataset, plausible topics absent from the corpus.

Output: appended to eval/golden/{dataset_id}.jsonl with answerable=False, qrels=[].
"""

from __future__ import annotations

import random
from pathlib import Path

from .golden import GoldenQuery

# ---------------------------------------------------------------------------
# Handwritten unanswerable queries
# These are plausible questions whose answers are structurally absent from
# the target corpus (financial KPIs asked of arxiv papers; NLP theory asked
# of annual reports).
# ---------------------------------------------------------------------------

_HANDWRITTEN_OPEN_RAGBENCH: list[str] = [
    "What is the quarterly dividend per share declared by Apple Inc. in Q3 2023?",
    "What are the total assets reported by Tesla Inc. at the end of fiscal year 2022?",
    "What is the operating cash flow disclosed by Microsoft in their 2021 annual report?",
    "What percentage of revenue did Amazon allocate to R&D expenses in fiscal year 2020?",
    "What is the net income margin for JPMorgan Chase in fiscal year 2019?",
    "How many full-time employees did Alphabet Inc. report at the end of 2022?",
    "What was the total debt-to-equity ratio reported by Boeing in their 2020 financial statements?",
    "What is the earnings per share reported by Meta Platforms for fiscal year 2021?",
    "What percentage of Walmart's net sales came from international operations in fiscal year 2022?",
    "What was the capital expenditure of ExxonMobil in fiscal year 2021?",
]

_HANDWRITTEN_LEDGER: list[str] = [
    "What is the time complexity of the Transformer self-attention mechanism with respect to sequence length?",
    "How does the BERT model handle out-of-vocabulary tokens during wordpiece tokenization?",
    "What is the theoretical upper bound on recall achievable with BM25 on sparse retrieval tasks?",
    "Explain the mathematical relationship between perplexity and cross-entropy loss in language models.",
    "What are the key architectural differences between a cross-encoder reranker and a bi-encoder?",
    "How does contrastive learning with in-batch negatives differ from supervised fine-tuning for embeddings?",
    "What is the role of the [CLS] token in sentence-level representations from BERT-style models?",
    "How does the BM25 algorithm handle term-frequency saturation differently from plain TF-IDF?",
    "What is the effect of temperature scaling on the sharpness of the softmax distribution in neural LMs?",
    "Describe how reciprocal rank fusion combines ranked lists from heterogeneous retrieval systems.",
]

# ---------------------------------------------------------------------------
# Samplers
# ---------------------------------------------------------------------------

def _load_lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def build_unanswerable_for_open_ragbench(
    golden_dir: Path,
    n_cross: int = 25,
    seed: int = 42,
) -> list[GoldenQuery]:
    """Return unanswerable GoldenQuery objects for the open_ragbench corpus.

    Cross-dataset source: LEDGER queries (financial KPIs → unresolvable against arxiv papers).
    """
    ledger_path = golden_dir / "ledger.jsonl"
    lines = _load_lines(ledger_path)
    rng = random.Random(seed)
    sampled = rng.sample(lines, min(n_cross, len(lines)))

    result: list[GoldenQuery] = []
    for i, line in enumerate(sampled):
        src = GoldenQuery.model_validate_json(line)
        result.append(GoldenQuery(
            query_id=f"unanswerable_orb_cross_{i:04d}",
            dataset_id="open_ragbench",
            query_text=src.query_text,
            qrels=[],
            answerable=False,
            meta={"source": "cross_dataset_ledger", "original_query_id": src.query_id},
        ))

    for i, text in enumerate(_HANDWRITTEN_OPEN_RAGBENCH):
        result.append(GoldenQuery(
            query_id=f"unanswerable_orb_manual_{i:04d}",
            dataset_id="open_ragbench",
            query_text=text,
            qrels=[],
            answerable=False,
            meta={"source": "manual"},
        ))

    return result


def build_unanswerable_for_ledger(
    golden_dir: Path,
    n_cross: int = 25,
    seed: int = 42,
) -> list[GoldenQuery]:
    """Return unanswerable GoldenQuery objects for the ledger corpus.

    Cross-dataset source: open_ragbench queries (arxiv science → unresolvable against annual reports).
    """
    orb_path = golden_dir / "open_ragbench.jsonl"
    lines = _load_lines(orb_path)
    rng = random.Random(seed)
    sampled = rng.sample(lines, min(n_cross, len(lines)))

    result: list[GoldenQuery] = []
    for i, line in enumerate(sampled):
        src = GoldenQuery.model_validate_json(line)
        result.append(GoldenQuery(
            query_id=f"unanswerable_ledger_cross_{i:04d}",
            dataset_id="ledger",
            query_text=src.query_text,
            qrels=[],
            answerable=False,
            meta={"source": "cross_dataset_open_ragbench", "original_query_id": src.query_id},
        ))

    for i, text in enumerate(_HANDWRITTEN_LEDGER):
        result.append(GoldenQuery(
            query_id=f"unanswerable_ledger_manual_{i:04d}",
            dataset_id="ledger",
            query_text=text,
            qrels=[],
            answerable=False,
            meta={"source": "manual"},
        ))

    return result
