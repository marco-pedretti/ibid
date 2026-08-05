"""I-02: unit tests for doc_genre classifier."""

import random

import pytest

from src.profiling.genre import (
    ACADEMIC_SECTION_LEN_THRESHOLD,
    TABLE_HEAVY_THRESHOLD,
    assign_genre,
)


# --- assign_genre boundary tests ---

def test_table_heavy_at_threshold():
    assert assign_genre(TABLE_HEAVY_THRESHOLD, 0) == "table_heavy"


def test_table_heavy_above_threshold():
    assert assign_genre(0.5, 5000) == "table_heavy"


def test_table_heavy_full_density():
    assert assign_genre(1.0, 100) == "table_heavy"


def test_below_threshold_long_sections_is_academic():
    assert assign_genre(TABLE_HEAVY_THRESHOLD - 0.01, ACADEMIC_SECTION_LEN_THRESHOLD) == "academic_pdf"


def test_below_threshold_very_long_sections_is_academic():
    assert assign_genre(0.0, 10000) == "academic_pdf"


def test_below_threshold_short_sections_is_continuous():
    assert assign_genre(0.0, ACADEMIC_SECTION_LEN_THRESHOLD - 1) == "continuous_text"


def test_zero_density_short_is_continuous():
    assert assign_genre(0.0, 0.0) == "continuous_text"


def test_just_below_table_threshold_long_is_academic():
    # typical open_ragbench: table_density ~0.10, long sections
    assert assign_genre(0.10, 5000) == "academic_pdf"


def test_just_above_table_threshold_is_table_heavy():
    # typical ledger: table_density ~0.41
    assert assign_genre(0.41, 3674) == "table_heavy"


# --- accuracy verification on real data (I-02 acceptance criterion) ---
# Requires downloaded datasets; skipped if not available.

@pytest.mark.skipif(
    not __import__("pathlib").Path("data/open_ragbench/pdf/arxiv/corpus").exists()
    or not __import__("pathlib").Path("data/ledger/eval/mmd").exists(),
    reason="requires downloaded datasets",
)
def test_genre_accuracy_50_docs():
    """I-02 gate: ≥90% correct on 50 sampled documents (25 per dataset).

    Ground truth:
      open_ragbench docs → "academic_pdf"  (all are arxiv papers)
      ledger docs        → "table_heavy"   (all are annual reports)
    """
    from pathlib import Path

    from src.datasets import ledger, open_ragbench
    from src.profiling.profiler import profile_from_chunks

    data_dir = Path("data")

    orb_chunks = list(open_ragbench.iter_chunks(data_dir / "open_ragbench"))
    led_chunks = list(ledger.iter_chunks(data_dir / "ledger"))

    orb_profiles = profile_from_chunks(orb_chunks)
    led_profiles = profile_from_chunks(led_chunks)

    rng = random.Random(42)
    sample_orb = rng.sample(orb_profiles, min(25, len(orb_profiles)))
    sample_led = rng.sample(led_profiles, min(25, len(led_profiles)))

    correct = 0
    total = len(sample_orb) + len(sample_led)

    for p in sample_orb:
        if p.doc_genre == "academic_pdf":
            correct += 1

    for p in sample_led:
        if p.doc_genre == "table_heavy":
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.90, (
        f"Genre accuracy {accuracy:.1%} < 90% on {total} sampled docs "
        f"({correct} correct). Adjust TABLE_HEAVY_THRESHOLD in genre.py."
    )
